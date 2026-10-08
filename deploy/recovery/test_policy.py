import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent))
from policy import terminal_profile, plan_recovery, emulator_identity


def cfg(*times):
    return {str(i): {'scheduler': {'enable': True, 'next_run': t}}
            for i, t in enumerate(times)}


class PolicyTests(unittest.TestCase):
    def test_retry_is_not_terminal(self):
        for cause in ['GameStuckError or GameTooManyClickError','GamePageUnknownError','test']:
            self.assertIsNone(terminal_profile({'content': '<M1> '+cause}, ['M1']))
        self.assertEqual(terminal_profile({'content':'<M1> RequestHumanTakeover'}, ['M1']), 'M1')
        self.assertIsNone(terminal_profile({'content':'<M10> RequestHumanTakeover'}, ['M1']))

    def test_shared_pending_tasks_stay_in_one_batch(self):
        now=datetime(2026,10,9,1)
        configs={'M3':cfg('2026-10-08 18:00:00','2026-10-08 18:02:00'),
                 'M4':cfg('2026-10-08 18:10:00'),
                 'M1':cfg('2026-10-09 01:20:00','2026-10-09 01:22:00'),
                 'M2':cfg('2026-10-09 02:00:00')}
        changes,slots=plan_recovery(configs,['M3','M4'],now)
        self.assertEqual(slots,[('M3',now),('M4',now+timedelta(minutes=30)),
                                ('M1',now+timedelta(hours=1)),('M2',now+timedelta(minutes=90))])
        self.assertEqual([t for n,k,t in changes if n=='M3'],[now,now])
        self.assertEqual([t for n,k,t in changes if n=='M1'],
                         [now+timedelta(hours=1),now+timedelta(minutes=62)])

    def test_unrelated_future_tasks_unchanged(self):
        now=datetime(2026,10,9,1)
        c={'M3':cfg('2026-10-08 18:00:00'), 'M1':cfg('2026-10-09 02:00:00')}
        changes,slots=plan_recovery(c,['M3'],now)
        self.assertEqual(len(changes),1)
        self.assertEqual(slots,[('M3',now)])

    def test_no_overdue_task_does_not_replay_completed_task(self):
        c={'M3':cfg('2026-10-09 03:00:00')}
        self.assertEqual(plan_recovery(c,['M3'],datetime(2026,10,9,1)),([],[]))

    def test_identity_must_match_serial(self):
        self.assertEqual(emulator_identity({'emulatorinfo_name':'MuMuPlayer-15.0-4',
                                           'serial':'127.0.0.1:16512'}),('15',4))
        with self.assertRaises(ValueError):
            emulator_identity({'emulatorinfo_name':'MuMuPlayer-15.0-4','serial':'127.0.0.1:16384'})


if __name__=='__main__': unittest.main()
