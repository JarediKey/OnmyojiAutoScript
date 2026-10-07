"""Deployment window uses the game timezone, independent of host timezone."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('safe_update', Path(__file__).resolve().parents[1] / 'deploy/safe_update.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeploymentWindowTests(unittest.TestCase):
    def test_utc_window_boundaries(self):
        self.assertFalse(module.in_window(datetime(2026, 10, 7, 0, 9, 59, tzinfo=timezone.utc)))
        self.assertTrue(module.in_window(datetime(2026, 10, 7, 0, 10, tzinfo=timezone.utc)))
        self.assertTrue(module.in_window(datetime(2026, 10, 7, 0, 49, 59, tzinfo=timezone.utc)))
        self.assertFalse(module.in_window(datetime(2026, 10, 7, 0, 50, tzinfo=timezone.utc)))


from datetime import timedelta
from types import SimpleNamespace
import tempfile
import os
from unittest.mock import Mock, patch
from module.config.maintenance import WorkerLease, DeploymentBusy


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/M1.json').write_text('{}')
        self.backup = self.root / 'backup'; self.backup.mkdir()
        self.settings = {'root': str(self.root), 'port': 22288,
                         'backend_pidfile': str(self.root / 'backend.pid')}
        self.observed = {'version': 1, 'backend_pid': 10, 'workers': {'M1': os.getpid()}}
        self.restored = []
        async def restore(port, names):
            self.restored.extend(names)
        self.mock_status = self.patch('status', return_value=self.observed)
        self.patch('in_window', return_value=True)
        self.patch('check_process', return_value=Mock())
        self.patch('git', side_effect=lambda root,*args: 'old' if args[0]=='rev-parse' else '')
        self.commands = self.patch('run', return_value=SimpleNamespace(stdout=''))
        self.stop = self.patch('stop_backend')
        self.start = self.patch('start_backend', return_value={'backend_pid': 20, 'workers': {}})
        self.patch('restore_workers', side_effect=restore)

    def patch(self, name, **kwargs):
        context = patch.object(module, name, **kwargs)
        result = context.start(); self.addCleanup(context.stop); return result

    def test_busy_worker_is_never_stopped(self):
        with WorkerLease(self.root, 'M1').active():
            with self.assertRaises(DeploymentBusy):
                module.activate(self.settings, 'old', 'new', self.backup)
        self.stop.assert_not_called()

    def test_success_restores_only_previously_live_workers(self):
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                module.activate(self.settings, 'old', 'new', self.backup)
        self.stop.assert_called_once()
        self.assertEqual(self.restored, ['M1'])

    def test_changed_roster_cancels_before_stopping(self):
        self.mock_status.side_effect = [self.observed, dict(self.observed, workers={})]
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaises(DeploymentBusy):
                    module.activate(self.settings, 'old', 'new', self.backup)
        self.stop.assert_not_called()

    def test_health_failure_rolls_back_and_restores_workers(self):
        self.start.side_effect = [RuntimeError('health failed'), {'backend_pid': 30, 'workers': {}}]
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaisesRegex(RuntimeError, 'health failed'):
                    module.activate(self.settings, 'old', 'new', self.backup)
        self.assertEqual(self.restored, ['M1'])
        self.assertTrue(any('checkout' in c.args[0] for c in self.commands.call_args_list))

    def test_worker_start_failure_does_not_rollback_active_new_source(self):
        async def fail(*args):
            raise RuntimeError('worker failed')
        module.restore_workers.side_effect = fail
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaisesRegex(RuntimeError, 'worker failed'):
                    module.activate(self.settings, 'old', 'new', self.backup)
        self.assertFalse(any('checkout' in c.args[0] for c in self.commands.call_args_list))
