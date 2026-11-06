"""Shared-user workers own the emulator until scheduler idle, across task boundaries."""
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from types import SimpleNamespace
import unittest

from module.config.maintenance import WorkerLease, maintenance_idle


class SharedEmulatorOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        for name in ('M1', 'M2'):
            (self.root / 'config' / (name + '.json')).write_text('{}')
        self.errors = []

    def worker(self, name, serial, entered, release):
        try:
            with WorkerLease(self.root, name, shared_serial=serial).active():
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('Test release timed out')
        except BaseException as error:
            self.errors.append(error)

    def test_same_emulator_cannot_be_owned_by_two_profiles(self):
        first = Event(); second = Event(); release = Event(); immediate = Event(); immediate.set()
        one = Thread(target=self.worker, args=('M1', 'serial-1', first, release))
        two = Thread(target=self.worker, args=('M2', 'serial-1', second, immediate))
        one.start()
        try:
            self.assertTrue(first.wait(2))
            two.start()
            self.assertFalse(second.wait(.15))
        finally:
            release.set()
            one.join(3)
            if two.ident is not None:
                two.join(3)
        self.assertTrue(second.is_set())
        self.assertEqual(self.errors, [])

    def test_other_emulator_does_not_wait_for_shared_owner(self):
        first = Event(); second = Event(); release = Event(); immediate = Event(); immediate.set()
        one = Thread(target=self.worker, args=('M1', 'serial-1', first, release))
        two = Thread(target=self.worker, args=('M2', 'serial-2', second, immediate))
        one.start()
        try:
            self.assertTrue(first.wait(2))
            two.start()
            self.assertTrue(second.wait(2))
        finally:
            release.set();one.join(3)
            if two.ident is not None:two.join(3)
        self.assertEqual(self.errors, [])

    def test_idle_hands_over_and_wake_waits_for_the_new_owner(self):
        idle = Event(); wake = Event(); resumed = Event(); sibling = Event(); release = Event()
        def first():
            try:
                with WorkerLease(self.root, 'M1', shared_serial='serial-1').active() as lease:
                    with lease.idle(datetime.now() + timedelta(minutes=10)):
                        idle.set()
                        if not wake.wait(3):raise RuntimeError('Wake signal timed out')
                    resumed.set()
            except BaseException as error:self.errors.append(error)
        one=Thread(target=first)
        two=Thread(target=self.worker,args=('M2','serial-1',sibling,release))
        one.start()
        try:
            self.assertTrue(idle.wait(2));two.start()
            self.assertTrue(sibling.wait(2));wake.set()
            self.assertFalse(resumed.wait(.15))
        finally:
            wake.set();release.set();one.join(3)
            if two.ident is not None:two.join(3)
        self.assertTrue(resumed.is_set())
        self.assertEqual(self.errors, [])

    def test_shared_handoff_invalidates_the_previous_app_user(self):
        self.check_handoff_cache('serial-1', None)

    def test_unshared_handoff_retains_its_existing_cache(self):
        self.check_handoff_cache(None, (12, 'game'))

    def check_handoff_cache(self, serial, expected):
        class Worker:
            @maintenance_idle
            def wait(self, future):return True
        worker=Worker();worker.device=SimpleNamespace(_started_app_user=(12,'game'))
        with WorkerLease(self.root,'M1',shared_serial=serial).active() as lease:
            worker._maintenance_lease=lease
            self.assertTrue(worker.wait(datetime.now()+timedelta(minutes=10)))
            self.assertEqual(worker.device._started_app_user,expected)
