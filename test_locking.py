"""Lock/unlock regression tests; no live Codex messages or desktop locking."""
from collections import deque
from pathlib import Path
import queue
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from desktop_state import desktop_available

from monitor import HERE
from retry_kitchen import KitchenApp
from test_concurrency import Scenario


class LockTests(unittest.TestCase):
    def setUp(self):
        self.available = True
        self.app = KitchenApp.__new__(KitchenApp)
        self.app.args = SimpleNamespace(demo=True, ui_smoke=True)
        self.app.desktop_check = lambda: self.available
        self.app.visual_allowed = True
        self.app.root = Mock()
        self.app.notifications = deque()
        self.app.events = queue.Queue()
        self.app.active = None
        self.app.projectile = SimpleNamespace(visible=False)
        self.app.message = SimpleNamespace(visible=False)
        self.app.hide = Mock()
        self.app.begin = Mock()

    def notice(self, count=1):
        return {'kind': 'sent', 'thread_id': 'test-chat', 'count': count}

    def test_locked_disconnected_or_unknown_session_never_shows_visuals(self):
        for state in ((0, 0), (4, 1), None):
            with self.subTest(state=state), patch('desktop_state.session_state', return_value=state):
                self.assertFalse(desktop_available())

    def test_render_error_does_not_end_animation_scheduling(self):
        self.app.notifications.append(self.notice())
        self.app.begin.side_effect = OSError('desktop switched during rendering')
        with self.assertLogs(level='ERROR'):
            self.app.animate()
        self.app.hide.assert_called_once()
        self.app.root.after.assert_called_once_with(100, self.app.animate)

    def test_lock_hides_active_flight_and_discards_pending_visuals(self):
        a = self.app
        a.active = self.notice()
        a.notifications.append(self.notice(2))
        a.notify(self.notice(3))
        self.available = False
        a.pump()
        a.animate()
        a.hide.assert_called_once()
        a.begin.assert_not_called()
        self.assertFalse(a.notifications)
        self.assertTrue(a.events.empty())

    def test_locked_confirmation_never_replays_even_if_pump_runs_after_unlock(self):
        self.available = False
        self.app.notify(self.notice())
        self.available = True
        self.app.pump()
        self.assertFalse(self.app.notifications)

    def test_unlock_allows_only_new_visuals(self):
        self.available = False
        self.app.notify(self.notice())
        self.app.pump()
        self.available = True
        self.app.pump()
        self.app.notify(self.notice(2))
        self.app.pump()
        self.app.animate()
        self.app.begin.assert_called_once()
        self.assertEqual(self.app.begin.call_args.args[0]['count'], 2)

    def test_unavailable_desktop_does_not_stop_sixteen_sends_or_counting(self):
        self.available = False
        with tempfile.TemporaryDirectory(prefix='lock-test-', dir=HERE) as folder:
            s = Scenario(Path(folder), lambda: 1792569600.0)
            s.unreachable.clear()
            s.ambiguous.clear()
            s.recovered.clear()
            for index in range(9, 16):
                s.add_turn(index, 2, 'failed')
            s.engine.notify = self.app.notify
            errors = []
            def send_all():
                try:
                    s.engine.tick()
                    s.engine.tick()
                except Exception as error:
                    errors.append(error)
            worker = threading.Thread(target=send_all, daemon=True)
            worker.start()
            worker.join(5)  # No UI pump runs during sending.
            self.assertFalse(worker.is_alive())
            self.assertFalse(errors)
            self.assertEqual(len(s.calls), 16)
            self.assertEqual(s.journal.daily_count(), 16)
            self.app.pump()
            self.assertFalse(self.app.notifications)
            self.assertTrue(self.app.events.empty())
            self.available = True
            self.app.pump()
            self.app.animate()
            self.app.begin.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
