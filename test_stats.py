"""Aggregation tests use synthetic journals only."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from retry_stats import summarize


class StatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'actions.jsonl'
        self.tz = timezone(timedelta(hours=8))
        self.now = datetime(2026, 10, 22, 0, 0, 1, tzinfo=self.tz).timestamp()

    def write(self, rows):
        self.path.write_text('\n'.join(json.dumps(row) for row in rows), encoding='utf-8')

    def row(self, status, key='chat:turn', message_id=None, at=None):
        return dict(status=status, key=key, at=self.now if at is None else at, message_id=message_id)

    def report(self, days=7):
        return summarize(self.path, days, self.now, self.tz)

    def test_empty_dates_are_zero_filled(self):
        data = self.report(30)
        self.assertEqual(len(data['days']), 30)
        self.assertEqual(data['days'][-1]['date'], '2026-10-22')
        self.assertEqual(data['total'], 0)

    def test_sending_sent_and_duplicates_count_once(self):
        self.write([self.row('sending'), self.row('sent', message_id='message'), self.row('sent', message_id='message')])
        data = self.report()
        self.assertEqual((data['today'], data['total'], data['unknown']), (1, 1, 0))

    def test_unknown_never_added_to_success_and_resolved_unknown_disappears(self):
        self.write([self.row('unknown'), self.row('sent', message_id='message'), self.row('unknown', key='other:turn')])
        data = self.report()
        self.assertEqual((data['today'], data['unknown']), (1, 1))
        self.assertEqual(data['days'][-1]['unknown'], 1)

    def test_pending_after_crash_and_baseline_are_not_sends(self):
        self.write([self.row('sending'), self.row('baseline', key='old:turn'), self.row('retryable', key='later:turn')])
        self.assertEqual(self.report()['unknown'], 1)
        self.assertEqual(self.report()['total'], 0)

    def test_local_midnight(self):
        self.write([self.row('sent', message_id='one', at=self.now - 2), self.row('sent', key='chat:second', message_id='two')])
        data = self.report()
        self.assertEqual(data['today'], 1)
        self.assertEqual(data['period'], 2)
        self.assertEqual(data['days'][-2]['sent'], 1)

    def test_malformed_or_partial_lines_are_reported_not_crashed(self):
        self.write([[], None, {}, self.row('sent', at=float('nan')), self.row('sent', message_id=[])])
        with self.path.open('a') as stream:
            stream.write('\n{"at":')
        self.assertEqual(self.report()['malformed'], 6)

    def test_history_outside_period_and_conversations_are_counted(self):
        self.write([self.row('sent', key='chat:one', at=self.now - 100 * 86400),
                    self.row('sent', key='chat:two'), self.row('sent', key='chat:three')])
        data = self.report()
        self.assertEqual((data['total'], data['period'], data['days'][-1]['chats']), (3, 2, 1))


if __name__ == '__main__':
    unittest.main()
