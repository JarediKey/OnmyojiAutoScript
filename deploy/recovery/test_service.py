"""Regression checks for notification-only admission and bounded AI decisions."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parent))
from service import Store


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(str(Path(self.temp.name) / 'queue.sqlite'))

    def test_duplicate_terminal_events_do_not_spawn_duplicate_incidents(self):
        first = self.store.add('M1', {'content': 'terminal'})
        second = self.store.add('M1', {'content': 'terminal'})
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.rows()), 1)

    def test_new_event_is_required_after_recovery_started(self):
        key = self.store.add('M1', {})
        started = time.time()
        self.assertFalse(self.store.notified_since(key, started))
        self.store.add('M1', {})
        self.assertTrue(self.store.notified_since(key, started))

    def test_repeated_failure_enters_cooldown_and_ai_queue(self):
        key = self.store.add('M1', {})
        self.store.update(key, 'recovered', {})
        second = self.store.add('M1', {})
        self.assertNotEqual(key, second)
        self.assertEqual(self.store.rows(['needs_ai'])[0]['id'], second)

    def test_unfinished_queue_survives_process_restart(self):
        key = self.store.add('M1', {})
        self.store.update(key, 'waiting', {'not_before': 123})
        another = Store(self.store.path)
        self.assertEqual(another.rows(['waiting'])[0]['id'], key)


if __name__ == '__main__':
    unittest.main()
