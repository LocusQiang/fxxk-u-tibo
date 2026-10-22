"""Real child lifecycle tests, isolated from Codex and production stop flags."""
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import Mock

from lifecycle import acquire_mutex, close_mutex, mutex_exists
from monitor import HERE
from retry_kitchen import KitchenApp
from supervisor import supervise


class SupervisorTests(unittest.TestCase):
    def test_restarts_nonzero_and_zero_exit_but_respects_manual_stop(self):
        with tempfile.TemporaryDirectory(prefix='supervisor-test-', dir=HERE) as folder:
            path = Path(folder)
            child = path / 'child.py'
            child.write_text("from pathlib import Path\np=Path('runs')\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nif n==3: Path('stop.request').write_text('stop')\nraise SystemExit(9 if n==1 else 0)\n", encoding='utf-8')
            worker = threading.Thread(target=supervise, args=([sys.executable, str(child)], path),
                                      kwargs={'worker_running':lambda:False, 'poll':.01, 'initial_delay':.03}, daemon=True)
            worker.start()
            worker.join(6)
            if worker.is_alive():
                (path/'stop.request').touch()
                worker.join(2)
                self.fail('Supervisor did not stop')
            self.assertEqual((path/'runs').read_text(), '3')

    def test_stop_file_prevents_any_launch(self):
        with tempfile.TemporaryDirectory(prefix='supervisor-test-', dir=HERE) as folder:
            Path(folder, 'stop.request').touch()
            supervise(['invalid-executable'], folder, worker_running=lambda:False)
            self.assertFalse(Path(folder, 'worker-stderr.log').exists())

    def test_existing_worker_is_adopted_without_duplicate(self):
        with tempfile.TemporaryDirectory(prefix='supervisor-test-', dir=HERE) as folder:
            def exists():
                Path(folder, 'stop.request').touch()
                return True
            supervise(['invalid-executable'], folder, worker_running=exists, poll=.01)
            self.assertFalse(Path(folder, 'worker-stderr.log').exists())

    def test_windows_singleton_released_on_close(self):
        name = 'Local\\CodexRetryTest-' + str(uuid.uuid4())
        self.assertFalse(mutex_exists(name))
        first = acquire_mutex(name)
        try:
            self.assertTrue(mutex_exists(name))
            self.assertIsNone(acquire_mutex(name))
        finally:
            close_mutex(first)
        self.assertFalse(mutex_exists(name))

    def test_shutdown_waits_for_inflight_worker_before_destroying_windows(self):
        app = KitchenApp.__new__(KitchenApp)
        app.root, app.projectile, app.message, app.worker = Mock(), Mock(), Mock(), Mock()
        app.worker.is_alive.return_value = True
        app.finish_shutdown()
        app.root.destroy.assert_not_called()
        app.root.after.assert_called_once_with(100, app.finish_shutdown)
        app.worker.is_alive.return_value = False
        app.finish_shutdown()
        app.root.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
