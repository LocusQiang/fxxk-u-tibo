"""Isolated 16-project routing and burst tests. No live Codex IPC or databases."""
from pathlib import Path
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from monitor import AutoRetry, HERE, Journal, Scanner, Sender
from retry_kitchen import flight_duration

ERROR = {'message': '服务不可用', 'codexErrorInfo': 'serverOverloaded'}


class Scenario:
    def __init__(self, folder, clock):
        self.folder, self.clock = Path(folder), clock
        self.live = {}
        self.calls, self.notices = [], []
        self.unreachable = {'project-06'}
        self.ambiguous = {'project-07'}
        self.recovered = {'project-08'}
        with closing(sqlite3.connect(self.folder/'state_5.sqlite')) as db, db:
            db.execute('CREATE TABLE threads (id TEXT, title TEXT, name TEXT, rollout_path TEXT, source TEXT, archived INTEGER DEFAULT 0)')
            for i in range(16):
                id = f'project-{i:02}'
                db.execute('INSERT INTO threads VALUES (?,?,?,?,?,0)', (id, id, None, '', 'vscode'))
        with closing(sqlite3.connect(self.folder/'thread_history_1.sqlite')) as db, db:
            db.execute('CREATE TABLE thread_turns (thread_id TEXT, turn_id TEXT, rollout_ordinal INTEGER, status TEXT, error_json TEXT, started_at INTEGER, completed_at INTEGER)')
        for i in range(16):
            self.add_turn(i, 1, 'failed' if i < 9 else 'inProgress')
        self.journal = Journal(self.folder/'actions.jsonl', clock=clock)
        self.scanner = Scanner(self.folder)
        self.sender = Sender(self.scanner, self.journal, invoke=self.invoke,
                             opener=lambda _: (_ for _ in ()).throw(AssertionError('No real opener')))
        self.engine = AutoRetry(self.scanner, self.journal, self.sender, self.notices.append, clock=clock)

    def add_turn(self, index, ordinal, status):
        id = f'project-{index:02}'
        turn = f'{id}-turn-{ordinal}'
        self.live[id] = (turn, status)
        with closing(sqlite3.connect(self.folder/'thread_history_1.sqlite')) as db, db:
            db.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?,?)',
                       (id, turn, ordinal, status, json.dumps(ERROR) if status=='failed' else None,
                        ordinal*100+index, ordinal*100+index))

    def invoke(self, *args):
        mode, id = args[:2]
        if mode == '--probe':
            if id in self.unreachable:
                return {'ok':False, 'error':'simulated disconnected owner'}
            turn, status = self.live[id]
            return {'ok':True, 'state': {'id':id,
                    'runtime': {'type':'active' if id in self.recovered or status=='inProgress' else 'idle'},
                    'latest':[{'turnId':turn, 'status':status, 'error':ERROR}]}}
        assert mode == '--continue'
        assert args[2] == self.live[id][0]
        self.calls.append(args)
        if id in self.ambiguous:
            return {'ok':False, 'submitted':True, 'error':'simulated acknowledgement lost'}
        return {'ok':True, 'sent':True, 'threadId':id, 'clientUserMessageId':args[3], 'turnId':'new-'+args[2]}


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='concurrency-', dir=HERE)
        self.addCleanup(tmp.cleanup)
        self.now = [1792569600.0]
        self.scenario = Scenario(tmp.name, lambda:self.now[0])

    def test_sixteen_projects_mixed_outcomes_and_later_failures(self):
        s = self.scenario
        s.engine.tick()
        self.assertEqual(s.journal.daily_count(),6)
        self.assertEqual(len(s.calls),7)  # 6 confirmed + 1 unknown, never active projects
        self.assertEqual([n['count'] for n in s.notices if n['kind']=='sent'],list(range(1,7)))
        self.assertEqual(sum(n['kind']=='unknown' for n in s.notices),1)
        self.assertEqual({a[1] for a in s.calls},{f'project-{i:02}' for i in (*range(6),7)})
        s.engine.tick()
        self.assertEqual(len(s.calls),7)
        # Three still-running projects later fail. Earlier candidates remain in history.
        for i in (9,10,11):
            s.add_turn(i,2,'failed')
        self.now[0] += 2
        s.engine.tick()
        self.assertEqual(s.journal.daily_count(),9)
        s.unreachable.clear()
        self.now[0] += 4
        s.engine.tick()
        self.assertEqual(s.journal.daily_count(),10)
        self.assertEqual([n['count'] for n in s.notices if n['kind']=='sent'],list(range(1,11)))
        self.assertEqual(len({(a[1],a[2]) for a in s.calls}),11)
        self.assertEqual(len({a[3] for a in s.calls}),11)
        self.assertEqual(sum(a[1]=='project-07' for a in s.calls),1)
        self.assertTrue(all(n['title']==n['thread_id'] for n in s.notices))
        # Restart must not repeat confirmed, uncertain or now-stale submissions.
        journal = Journal(s.journal.path,clock=lambda:self.now[0])
        s.sender.journal = journal
        AutoRetry(s.scanner,journal,s.sender,s.notices.append,clock=lambda:self.now[0]).tick()
        self.assertEqual(len(s.calls),11)

    def test_slow_failure_backoff_starts_when_failure_returns(self):
        s = self.scenario
        calls=[]
        class SlowSender:
            def send(inner, failure):
                calls.append(failure)
                self.now[0]+=20
                return 'error','slow connection'
        s.scanner.scan=lambda:[next(f for f in Scanner(s.folder).scan() if f.thread_id=='project-00')]
        engine=AutoRetry(s.scanner,s.journal,SlowSender(),s.notices.append,clock=lambda:self.now[0])
        engine.tick()
        self.now[0]+=4
        engine.tick()
        self.assertEqual(len(calls),1)
        self.now[0]+=1
        engine.tick()
        self.assertEqual(len(calls),2)

    def test_burst_drains_faster_but_preserves_toast_reading_time(self):
        durations=[flight_duration(pending) for pending in range(15,-1,-1)]
        self.assertTrue(all(d>1.15 for d in durations))
        self.assertLess(sum(durations),30)
        self.assertGreaterEqual(durations[-1],3.6)


if __name__=='__main__':
    unittest.main(verbosity=2)
