"""Deployment admission must never treat an active or stale worker as idle."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from module.config.maintenance import WorkerLease, DeploymentBusy, acquire_idle_workers


class MaintenanceLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/M1.json').write_text('{}')
        self.workers = {'M1': os.getpid()}

    def test_active_worker_blocks_deployment_without_waiting(self):
        with WorkerLease(self.root, 'M1').active():
            with self.assertRaises(DeploymentBusy):
                with acquire_idle_workers(self.root, self.workers):
                    self.fail('Active worker was admitted')

    def test_idle_worker_can_be_reserved(self):
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with acquire_idle_workers(self.root, self.workers):
                    pass

    def test_changed_configuration_or_stale_pid_blocks_update(self):
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaises(DeploymentBusy):
                    with acquire_idle_workers(self.root, {'M1': os.getpid() + 1}):
                        pass
                (self.root / 'config/M1.json').write_text('{"changed":true}')
                with self.assertRaises(DeploymentBusy):
                    with acquire_idle_workers(self.root, self.workers):
                        pass

    def test_imminent_task_blocks_update(self):
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(seconds=60)):
                with self.assertRaises(DeploymentBusy):
                    with acquire_idle_workers(self.root, self.workers):
                        pass

    def test_current_schedule_cannot_be_hidden_by_cached_wake(self):
        due = (datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None) + timedelta(seconds=60)).isoformat()
        (self.root / 'config/M1.json').write_text(json.dumps({'task': {'scheduler': {'enable': True, 'next_run': due}}}))
        with WorkerLease(self.root, 'M1').active() as lease:
            with lease.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaises(DeploymentBusy):
                    with acquire_idle_workers(self.root, self.workers):
                        pass

    def test_legacy_worker_without_acknowledgment_is_rejected(self):
        with self.assertRaises(DeploymentBusy):
            with acquire_idle_workers(self.root, self.workers):
                pass

    def test_controller_releases_earlier_locks_when_another_worker_is_busy(self):
        (self.root / 'config/M2.json').write_text('{}')
        with WorkerLease(self.root, 'M1').active() as first, WorkerLease(self.root, 'M2').active():
            with first.idle(datetime.now() + timedelta(minutes=10)):
                with self.assertRaises(DeploymentBusy):
                    with acquire_idle_workers(self.root, dict(self.workers, M2=os.getpid())):
                        pass
                probe = WorkerLease(self.root, 'M1').lock
                with probe.acquire(timeout=0):
                    pass

    def test_worker_cannot_leave_idle_while_controller_holds_reservation(self):
        idle = threading.Event(); leave = threading.Event(); resumed = threading.Event()
        def worker():
            with WorkerLease(self.root, 'M1').active() as lease:
                with lease.idle(datetime.now() + timedelta(minutes=10)):
                    idle.set(); leave.wait(3)
                resumed.set()
        thread = threading.Thread(target=worker)
        thread.start()
        self.addCleanup(lambda: thread.join(4))
        self.assertTrue(idle.wait(2))
        with acquire_idle_workers(self.root, self.workers):
            leave.set()
            self.assertFalse(resumed.wait(.15))
        self.assertTrue(resumed.wait(2))


if __name__ == '__main__':
    unittest.main()
