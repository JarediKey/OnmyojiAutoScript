"""Exercise sharing retries and continuation without game/device access."""

import ast
from pathlib import Path
import runpy
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
errors = runpy.run_path(str(ROOT / 'module/exception.py'))


def method(name, namespace):
    tree = ast.parse((ROOT / 'tasks/WeeklyTrifles/script_task.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<weekly-share>', 'exec'), namespace)
    return namespace[name]


class AreaShareTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        clock = patch('time.time', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.phase = 'detail'
        self.share_clicks = []
        self.entry_clicks = []
        self.day_clicks = []
        self.last_click = {}
        self.selector_after = None
        self.selector_delay = 0
        self.entry_opens = True
        self.return_works = True
        self.jade = True
        self.logger = Mock()
        self.task = Mock()
        for attr, name in [('I_WT_DAY_BATTLE', 'day'), ('I_CHECK_EXPLORATION', 'exploration'),
                           ('I_WT_AB_WECHAT', 'wechat'), ('I_WT_NO_DAY', 'no-day'),
                           ('I_WT_SHARE_AB', 'share'), ('C_WT_AB_CLICK', 'entry'),
                           ('I_WT_AB_JADE', 'jade'), ('I_UI_BACK_RED', 'red'),
                           ('I_UI_BACK_BLUE', 'blue'), ('I_UI_BACK_YELLOW', 'yellow')]:
            setattr(self.task, attr, name)
        self.task.screenshot.side_effect = self.screenshot
        self.task.appear.side_effect = self.appear
        self.task.ui_page_appear.side_effect = lambda page: self.phase == 'home'
        self.task.appear_then_click.side_effect = self.appear_then_click
        self.task.click.side_effect = self.click
        self.task.click_share.side_effect = self.complete_share
        namespace = dict(Timer=Timer, logger=self.logger, time=SimpleNamespace(sleep=self.sleep),
                         page_main='home', page_area_boss='area', **errors)
        self.share = method('_share_area_boss', namespace)
        self.run = method('run', namespace)

    def sleep(self, seconds):
        self.now += seconds

    def screenshot(self):
        self.now += 0.25
        if (self.phase == 'detail' and self.selector_after is not None
                and len(self.share_clicks) >= self.selector_after
                and self.now - self.share_clicks[-1] >= self.selector_delay):
            self.phase = 'selector'

    def appear(self, target):
        frames = {'detail': {'share', 'red'}, 'selector': {'wechat', 'red'},
                  'list': {'day'}, 'no-records': {'day', 'no-day'}, 'home': set(), 'unknown': set()}
        return target in frames[self.phase] or (target == 'jade' and self.phase == 'selector' and self.jade)

    def appear_then_click(self, target, interval=0):
        if not self.appear(target):
            return False
        return self.click(target, interval)

    def click(self, target, interval=0):
        if self.now - self.last_click.get(target, float('-inf')) < interval:
            return False
        self.last_click[target] = self.now
        if target == 'share':
            self.share_clicks.append(self.now)
        elif target == 'entry':
            self.entry_clicks.append(self.now)
            if self.entry_opens:
                self.phase = 'detail'
        elif target == 'day':
            self.day_clicks.append(self.now)
        elif target in ('red', 'blue', 'yellow') and self.return_works:
            self.phase = 'home'
        return True

    def complete_share(self, target):
        self.phase = 'home'
        return True

    def test_three_failed_share_clicks_skip_after_final_wait_and_return(self):
        self.share(self.task)
        self.assertEqual(len(self.share_clicks), 3)
        self.assertGreaterEqual(self.now - self.share_clicks[-1], 3)
        self.assertTrue(all(b - a >= 3 for a, b in zip(self.share_clicks, self.share_clicks[1:])))
        self.assertEqual(self.entry_clicks, [])
        self.task.click_share.assert_not_called()
        self.assertEqual(self.phase, 'home')
        self.assertIn('reward not confirmed', str(self.logger.warning.call_args_list))

    def test_success_on_third_click_is_detected_before_limit(self):
        self.selector_after = 3
        self.selector_delay = 3
        self.share(self.task)
        self.assertEqual(len(self.share_clicks), 3)
        self.task.click_share.assert_called_once_with('wechat')
        self.logger.warning.assert_not_called()

    def test_first_click_success_does_not_retry(self):
        self.selector_after = 1
        self.share(self.task)
        self.assertEqual(len(self.share_clicks), 1)
        self.task.click_share.assert_called_once_with('wechat')

    def test_selector_already_visible_needs_no_share_click(self):
        self.phase = 'selector'
        self.share(self.task)
        self.assertEqual(self.share_clicks, [])
        self.task.click_share.assert_called_once_with('wechat')

    def test_preparation_coordinates_and_day_tab_are_also_bounded(self):
        self.phase = 'list'
        self.entry_opens = False
        self.share(self.task)
        self.assertEqual(len(self.entry_clicks), 3)
        self.assertLessEqual(len(self.day_clicks), 3)
        self.assertEqual(self.share_clicks, [])
        self.task.click_share.assert_not_called()

    def test_failed_share_does_not_skip_remaining_weekly_steps(self):
        self.task.config.weekly_trifles.trifles = SimpleNamespace(
            share_collect=True, share_area_boss=True, share_secret=True, broken_amulet=100)
        self.task._share_area_boss = MethodType(self.share, self.task)
        with self.assertRaises(errors['TaskEnd']):
            self.run(self.task)
        self.task._share_collect.assert_called_once_with()
        self.task._share_secret.assert_called_once_with()
        self.task._broken_amulet.assert_called_once_with(100)
        self.task.set_next_run.assert_called_once_with(task='WeeklyTrifles', success=True, finish=True)
        self.task.click_share.assert_not_called()

    def test_absent_reward_marker_preserves_existing_already_obtained_flow(self):
        self.phase = 'selector'
        self.jade = False
        self.share(self.task)
        self.task.click_share.assert_not_called()
        self.assertEqual(self.phase, 'home')

    def test_no_daily_battle_record_does_not_attempt_sharing(self):
        self.phase = 'no-records'
        self.share(self.task)
        self.assertEqual(self.share_clicks, [])
        self.assertEqual(self.entry_clicks, [])
        self.task.click_share.assert_not_called()

    def test_unrecoverable_page_still_fails_instead_of_running_next_task_blindly(self):
        self.phase = 'unknown'
        self.task.click.return_value = False
        self.task.click.side_effect = None
        with self.assertRaisesRegex(errors['GameStuckError'], 'Cannot leave Area Boss sharing'):
            self.share(self.task)
        self.assertLessEqual(self.now, 151)
        self.task.click_share.assert_not_called()


if __name__ == '__main__':
    unittest.main()
