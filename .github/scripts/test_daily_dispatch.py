"""Exercise dispatch deduplication without GitHub or OS service mutations."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('daily_dispatch', Path(__file__).with_name('daily_dispatch.py'))
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)


class DispatchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.state = Path(folder.name)
        self.now = datetime(2026, 10, 16, 0, 10, tzinfo=timezone.utc)
        self.account = json.dumps({'login': 'JarediKey'})
        self.empty = json.dumps({'workflow_runs': []})
        self.existing = json.dumps({'workflow_runs': [
            {'id': 123, 'head_branch': 'master', 'display_title': 'OAS workflow_dispatch sync',
             'created_at': '2026-10-16T00:10:00Z'}]})

    def test_outside_window_does_not_contact_github(self):
        with patch.object(daily, 'run_cli') as cli:
            self.assertIsNone(daily.dispatch('gh', self.state, self.now.replace(hour=1)))
        cli.assert_not_called()

    def test_success_is_dispatched_once(self):
        with patch.object(daily, 'run_cli', side_effect=[self.account, self.empty, '']) as cli:
            self.assertEqual(daily.dispatch('gh', self.state, self.now)['status'], 'dispatched')
            self.assertIsNone(daily.dispatch('gh', self.state, self.now))
        self.assertEqual(cli.call_count, 3)
        self.assertEqual(cli.call_args.args[-4:], ('--ref', 'master', '--field', 'mode=sync'))

    def test_existing_remote_run_is_not_duplicated(self):
        with patch.object(daily, 'run_cli', side_effect=[self.account, self.existing]) as cli:
            result = daily.dispatch('gh', self.state, self.now)
        self.assertEqual(result['existing_run'], 123)
        self.assertEqual(cli.call_count, 2)

    def test_uncertain_response_is_reconciled_before_retry(self):
        with patch.object(daily, 'run_cli', side_effect=[self.account, self.empty,
                subprocess.TimeoutExpired('gh', 30)]):
            self.assertEqual(daily.dispatch('gh', self.state, self.now)['status'], 'blocked')
        with patch.object(daily, 'run_cli', side_effect=[self.account, self.existing]) as cli:
            self.assertEqual(daily.dispatch('gh', self.state, self.now)['status'], 'dispatched')
        self.assertEqual(cli.call_count, 2)

    def test_smoke_run_does_not_suppress_the_daily_sync(self):
        smoke = self.existing.replace('workflow_dispatch sync', 'workflow_dispatch ai-smoke')
        with patch.object(daily, 'run_cli', side_effect=[self.account, smoke, '']) as cli:
            self.assertEqual(daily.dispatch('gh', self.state, self.now)['status'], 'dispatched')
        self.assertEqual(cli.call_count, 3)

    def test_wrong_account_cannot_dispatch(self):
        with patch.object(daily, 'run_cli', return_value='{"login":"another-user"}') as cli:
            result = daily.dispatch('gh', self.state, self.now)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(cli.call_count, 1)

    def test_force_allows_reviewed_manual_dispatch(self):
        with patch.object(daily, 'run_cli', side_effect=[self.account, self.empty, '']):
            result = daily.dispatch('gh', self.state, self.now.replace(hour=12), force=True)
        self.assertEqual(result['status'], 'dispatched')


if __name__ == '__main__':
    unittest.main()
