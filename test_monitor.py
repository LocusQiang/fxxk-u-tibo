import dataclasses
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from monitor import Failure, HERE, Journal, Scanner, Sender, LiveFilter, is_unavailable

ERR = {'message': 'Selected model is at capacity. Please try a different model.', 'codexErrorInfo': 'serverOverloaded'}

@contextmanager
def write_db(path):
    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()

class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='retry-test-', dir=HERE)
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        with write_db(self.home / 'state_5.sqlite') as db:
            db.execute('CREATE TABLE threads (id TEXT, title TEXT, name TEXT, rollout_path TEXT, source TEXT, archived INTEGER)')
        with write_db(self.home / 'thread_history_1.sqlite') as db:
            db.execute('CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, rollout_ordinal INTEGER, status TEXT, error_json TEXT, started_at INTEGER, completed_at INTEGER)')
        self.scanner = Scanner(self.home)

    def chat(self, id, source='vscode', path='', archived=0):
        with write_db(self.home / 'state_5.sqlite') as db:
            db.execute('INSERT INTO threads VALUES (?,?,?,?,?,?)', (id, '服务不可用仅作为正文标题', None, path, source, archived))

    def turn(self, id, turn, ordinal, status, error=None):
        with write_db(self.home / 'thread_history_1.sqlite') as db:
            db.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?,?)', (id, turn, ordinal, status, json.dumps(error), ordinal, ordinal))

    def test_multiple_chats_latest_only_and_prose_not_triggered(self):
        for chat in ('failed-a', 'failed-b', 'resumed', 'done', 'manual', 'unrelated'):
            self.chat(chat)
        self.chat('agent', source='subagent')
        self.chat('archived', archived=1)
        for chat in ('failed-a', 'failed-b', 'resumed', 'done', 'agent', 'archived'):
            self.turn(chat, 'old', 1, 'failed', ERR)
        self.turn('resumed', 'new', 2, 'inProgress')
        self.turn('done', 'new', 2, 'completed')
        self.turn('manual', 'new', 2, 'interrupted')
        self.turn('unrelated', 'new', 2, 'failed', {'message': '404 not found'})
        self.assertEqual({f.thread_id for f in self.scanner.scan()}, {'failed-a', 'failed-b'})

    def test_rebuilt_history_maps_to_ui_id(self):
        ui = '00000000-0000-0000-0000-000000000001'
        alias = '00000000-0000-0000-0000-000000000002'
        self.chat(ui, path=str(self.home / ('rollout-' + ui + '_' + alias + '.jsonl')))
        self.turn(ui, 'old', 1, 'completed')
        self.turn(alias, 'new', 2, 'failed', ERR)
        failure, = self.scanner.scan()
        self.assertEqual((failure.thread_id, failure.turn_id), (ui, 'new'))

    def test_error_classes(self):
        for error in ({'message': '服务不可用'}, {'message': '服务暂时不可用'}, {'message': 'Service Unavailable'}, {'message': 'HTTP 503'}, {'message': 'Our servers are currently overloaded'}, {'codexErrorInfo': {'httpConnectionFailed': {'httpStatusCode': 503}}}, ERR):
            self.assertTrue(is_unavailable(error), error)
        for error in (None, '服务不可用', {'message': 'stream disconnected before completion'}, {'message': '401 unauthorized'}, {'message': 'HTTP 404'}, {'message': 'user cancelled'}):
            self.assertFalse(is_unavailable(error), error)

    def test_legacy_events_are_never_a_send_candidate(self):
        path = self.home / 'legacy.jsonl'
        self.chat('legacy', path=str(path))
        events = [
            {'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 't1'}},
            {'type': 'response_item', 'payload': {'message': '服务不可用'}},
            {'type': 'event_msg', 'payload': {'type': 'error', 'message': '服务不可用', 'will_retry': True}},
        ]
        def write():
            path.write_text('\n'.join(json.dumps(e) for e in events) + '\n', encoding='utf-8')
        write()
        self.assertEqual(self.scanner.scan(), [])
        events.append({'type': 'event_msg', 'payload': {'type': 'error', 'message': '服务不可用', 'will_retry': False}})
        write()
        self.assertEqual(self.scanner.scan(), [])
        events.append({'type': 'event_msg', 'payload': {'type': 'task_started', 'turn_id': 't2'}})
        write()
        self.assertEqual(self.scanner.scan(), [])

    def prepare_sender(self, invoke):
        self.chat('actual-chat')
        self.turn('actual-chat', 'failed-turn', 1, 'failed', ERR)
        failure = self.scanner.scan()[0]
        journal = Journal(self.home / 'actions.jsonl')
        sender = Sender(self.scanner, journal, invoke=invoke)
        return sender, journal, failure

    def probe(self, active=False, runtime=None):
        return {'ok': True, 'state': {'id': 'actual-chat', 'runtime': {'type': runtime or ('active' if active else 'idle')}, 'latest': [{'turnId': 'failed-turn', 'status': 'failed', 'error': ERR}]}}

    def test_click_routes_exact_id_and_survives_restart_without_duplicate(self):
        calls = []
        def invoke(*args):
            calls.append(args)
            return self.probe() if args[0] == '--probe' else {
                'ok': True, 'sent': True, 'threadId': args[1],
                'clientUserMessageId': args[3], 'turnId': 'new-turn'}
        sender, journal, failure = self.prepare_sender(invoke)
        self.assertEqual(sender.send(failure)[0], 'sent')
        self.assertEqual(calls[1][:3], ('--continue', 'actual-chat', 'failed-turn'))
        self.assertEqual(len(calls[1][3]), 36)
        sender.journal = Journal(journal.path)
        self.assertEqual(sender.send(failure)[0], 'stale')
        self.assertEqual(len(calls), 2)

    def test_active_state_never_sends(self):
        calls = []
        def invoke(*args):
            calls.append(args)
            return self.probe(active=True)
        sender, journal, failure = self.prepare_sender(invoke)
        self.assertEqual(sender.send(failure)[0], 'stale')
        self.assertEqual(len(calls), 1)

    def test_system_error_state_can_send_exact_unavailable_failure(self):
        calls = []
        def invoke(*args):
            calls.append(args)
            return self.probe(runtime='systemError') if args[0] == '--probe' else {
                'ok': True, 'sent': True, 'threadId': args[1],
                'clientUserMessageId': args[3], 'turnId': 'new-turn'}
        sender, journal, failure = self.prepare_sender(invoke)
        self.assertEqual(sender.send(failure)[0], 'sent')
        self.assertEqual(calls[1][:3], ('--continue', 'actual-chat', 'failed-turn'))

    def test_timeout_is_unknown_and_not_retried(self):
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[0] == '--probe':
                return self.probe()
            raise subprocess.TimeoutExpired('node', 50)
        sender, journal, failure = self.prepare_sender(invoke)
        with self.assertLogs(level='ERROR'):
            self.assertEqual(sender.send(failure)[0], 'unknown')
        self.assertEqual(sender.send(failure)[0], 'stale')
        self.assertEqual(len(calls), 2)

    def test_safe_preflight_failure_can_retry(self):
        sender, journal, failure = self.prepare_sender(lambda *args: {'ok': False, 'error': 'pipe not available'})
        with self.assertLogs(level='WARNING'):
            self.assertEqual(sender.send(failure)[0], 'error')
        self.assertFalse(journal.blocked(failure))

    def test_double_click_busy_guard(self):
        sender, journal, failure = self.prepare_sender(lambda *args: self.fail('must not invoke'))
        sender.lock.acquire()
        try:
            self.assertEqual(sender.send(failure)[0], 'busy')
        finally:
            sender.lock.release()

    def test_live_filter_hides_recovered_chats_without_losing_unopened_chats(self):
        f = Failure('actual-chat', 'failed-turn', 'title', 1, '服务不可用')
        self.assertEqual(LiveFilter(lambda *args: self.probe(True)).filter([f]), [])
        self.assertEqual(LiveFilter(lambda *args: self.probe()).filter([f]), [f])
        self.assertEqual(LiveFilter(lambda *args: {'ok': False, 'error': 'no-client-found'}).filter([f]), [f])

    def test_sending_journal_is_durable_before_submission(self):
        def invoke(*args):
            if args[0] == '--probe':
                return self.probe()
            self.assertTrue(Journal(journal.path).blocked(failure))
            return {'ok': False, 'submitted': False, 'error': 'STALE: changed'}
        sender, journal, failure = self.prepare_sender(invoke)
        self.assertEqual(sender.send(failure)[0], 'stale')

    def test_missing_history_disables_scanning_and_does_not_create_database(self):
        path = self.home / 'thread_history_1.sqlite'
        path.unlink()
        with self.assertRaises(sqlite3.OperationalError):
            self.scanner.scan()
        self.assertFalse(path.exists())

    def test_initial_baseline_skips_old_failures_and_persists_but_allows_new_turns(self):
        self.chat('chat')
        self.turn('chat', 'old', 1, 'failed', ERR)
        old = self.scanner.scan()[0]
        journal = Journal(self.home / 'private/actions.jsonl')
        journal.initialize_baseline(self.scanner)
        self.assertTrue(journal.blocked(old))
        self.assertEqual(journal.daily_count(), 0)
        self.turn('chat', 'new', 2, 'failed', ERR)
        journal = Journal(journal.path)
        journal.initialize_baseline(self.scanner)
        self.assertTrue(journal.blocked(old))
        self.assertFalse(journal.blocked(self.scanner.scan()[0]))

    def test_baseline_read_failure_and_changed_home_fail_closed(self):
        journal = Journal(self.home / 'private/actions.jsonl')
        with patch.object(self.scanner, 'scan', side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):
                journal.initialize_baseline(self.scanner)
        self.assertFalse(journal.path.with_name('baseline.json').exists())
        journal.initialize_baseline(self.scanner)
        with self.assertRaisesRegex(RuntimeError, 'different Codex home'):
            journal.initialize_baseline(Scanner(self.home / 'other'))

    def test_unknown_protocol_does_not_permanently_mark_failure_stale(self):
        def invoke(*args):
            self.assertEqual(args[0], '--probe')
            probe = self.probe()
            probe['state']['runtime'] = {'type': 'new-unknown-protocol'}
            return probe
        sender, journal, failure = self.prepare_sender(invoke)
        with self.assertLogs(level='WARNING'):
            self.assertEqual(sender.send(failure)[0], 'error')
        self.assertFalse(journal.blocked(failure))

    def test_unverified_send_acknowledgement_never_counts_or_repeats(self):
        def invoke(*args):
            return self.probe() if args[0] == '--probe' else {'ok': True, 'sent': True}
        sender, journal, failure = self.prepare_sender(invoke)
        with self.assertLogs(level='WARNING'):
            self.assertEqual(sender.send(failure)[0], 'unknown')
        self.assertEqual(journal.daily_count(), 0)
        self.assertTrue(Journal(journal.path).blocked(failure))

if __name__ == '__main__':
    unittest.main(verbosity=2)
