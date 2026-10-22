"""Portable install, local-day, and fail-closed checks without real chat writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from doctor import schema_check
from monitor import Failure, HERE, Journal, Scanner, Sender
from overlay import message_image
from test_monitor import write_db, ERR


class PortabilityTests(unittest.TestCase):
    def test_missing_runtime_status_never_sends(self):
        failure = Failure('chat', 'turn', '', 0, '')
        for runtime in (None, {}, {'type': 'unknown'}, {'type': 'active'}):
            probe = {'state': {'id': 'chat', 'runtime': runtime,
                              'latest': [{'turnId': 'turn', 'status': 'failed', 'error': ERR}]}}
            self.assertFalse(Sender.state_matches(failure, probe))

    def test_daily_count_uses_supplied_local_day_across_midnight(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            zone = timezone(timedelta(hours=-7))
            clock = [datetime(2026, 10, 21, 23, 59, 59, tzinfo=zone).timestamp()]
            journal = Journal(Path(folder) / 'nested/actions.jsonl', clock=lambda: clock[0], tz=zone)
            journal.record(Failure('chat', 'turn', '', 0, ''), 'sent', 'one')
            self.assertEqual(journal.daily_count(), 1)
            clock[0] += 2
            self.assertEqual(journal.daily_count(), 0)

    def test_doctor_missing_home_is_read_only(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            home = Path(folder) / 'not-created'
            self.assertEqual(schema_check(home)[0]['status'], 'error')
            self.assertFalse(home.exists())

    def test_scanner_supports_state_schema_without_optional_name_column(self):
        with tempfile.TemporaryDirectory(prefix='portable-路径 ', dir=HERE) as folder:
            home = Path(folder)
            with write_db(home / 'state_5.sqlite') as db:
                db.execute('CREATE TABLE threads (id TEXT, title TEXT, rollout_path TEXT, source TEXT, archived INTEGER)')
                db.execute("INSERT INTO threads VALUES ('chat','title','','desktop',0)")
            with write_db(home / 'thread_history_1.sqlite') as db:
                db.execute('CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, status TEXT, error_json TEXT, started_at INTEGER, completed_at INTEGER, rollout_ordinal INTEGER)')
                db.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?,?)', ('chat', 'turn', 'failed', json.dumps(ERR), 1, 1, 1))
            self.assertEqual(Scanner(home).scan()[0].thread_id, 'chat')
            self.assertTrue(all(row['status'] == 'ok' for row in schema_check(home)))

    def test_toast_without_chinese_windows_fonts(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder, patch.dict('os.environ', {'WINDIR': folder}):
            image = message_image('Retried again! #1 today.', 1)
            self.assertGreater(image.width, 100)
            self.assertEqual(image.mode, 'RGBA')


if __name__ == '__main__':
    unittest.main()
