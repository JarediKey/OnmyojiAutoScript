import unittest
from types import SimpleNamespace
from unittest.mock import patch

from module.exception import TaskEnd
from tasks.FrogBoss.config import Strategy
from tasks.FrogBoss.script_task import ScriptTask


class RestTask(ScriptTask):
    def __init__(self, frames):
        self.frames = iter(frames)
        self.visible = set()
        self.now = 1.0
        self.bets = 0
        self.rescheduled = False
        self.config = SimpleNamespace(model=SimpleNamespace(frog_boss=SimpleNamespace(
            frog_boss_config=SimpleNamespace(strategy_frog=Strategy.AlwaysRed))))

    def enter_frog_boss(self):
        pass

    def screenshot(self):
        self.now, self.visible = next(self.frames)

    def appear(self, rule):
        return rule.name in self.visible

    def _try_next_competition_fallback(self, timer):
        return False

    def do_bet(self):
        self.bets += 1

    def next_run(self):
        self.rescheduled = True


class RestConfirmationTests(unittest.TestCase):
    def run_task(self, frames):
        task = RestTask(frames)
        with patch('module.base.timer.time.time', side_effect=lambda: task.now):
            with self.assertRaises(TaskEnd):
                task.run()
        self.assertTrue(task.rescheduled)
        return task

    def test_loading_recovers_to_betting_without_skipping(self):
        rest = {ScriptTask.I_FROG_BOSS_REST.name}
        betting = {ScriptTask.I_BET_LEFT.name, ScriptTask.I_BET_RIGHT.name}
        task = self.run_task([(1, rest), (3, rest), (4, betting), (5, {ScriptTask.I_BETTED.name})])
        self.assertEqual(task.bets, 1)

    def test_stable_rest_requires_time_and_three_fresh_screenshots(self):
        rest = {ScriptTask.I_FROG_BOSS_REST.name}
        task = self.run_task([(1, rest), (7, rest), (8, rest)])
        self.assertEqual(task.now, 8)
        self.assertEqual(task.bets, 0)

    def test_missing_rest_resets_confirmation(self):
        rest = {ScriptTask.I_FROG_BOSS_REST.name}
        task = self.run_task([(1, rest), (3, rest), (4, set()), (6, rest), (8, rest), (12, rest)])
        self.assertEqual(task.now, 12)
        self.assertEqual(task.bets, 0)

    def test_visible_betting_takes_priority_over_rest(self):
        rest = {ScriptTask.I_FROG_BOSS_REST.name}
        betting = {ScriptTask.I_BET_LEFT.name, ScriptTask.I_BET_RIGHT.name}
        task = self.run_task([(1, rest), (7, rest), (8, rest | betting), (9, {ScriptTask.I_BETTED.name})])
        self.assertEqual(task.bets, 1)


if __name__ == '__main__':
    unittest.main()
