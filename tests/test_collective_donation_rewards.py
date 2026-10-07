"""Exercise the actual donation state machine with deterministic UI frames."""
import ast
import re
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
GameStuckError = runpy.run_path(str(ROOT / 'module/exception.py'))['GameStuckError']
SOURCE = ROOT / 'tasks/CollectiveMissions/script_task.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ScriptTask')
node = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
            and n.name == '_submit_and_collect_rewards')
ns = dict(re=re, Timer=Timer, GameStuckError=GameStuckError, logger=Mock())
exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), ns)
collect = ns['_submit_and_collect_rewards']


class DonationRewardsTests(unittest.TestCase):
    def run_frames(self, frames, clicks=None, soul=False, text="将提交30次任务"):
        self.now = 100.
        self.index = -1
        task = SimpleNamespace(I_UI_REWARD='reward', I_CM_RECORDS='list',
                               device=SimpleNamespace(image=None),
                               O_SL_NUMBER=SimpleNamespace(ocr=Mock(return_value=text)))
        task.click = Mock(return_value=True)
        def screenshot():
            self.now += .5
            self.index += 1
        def appear(target, **kwargs):
            return target in frames[min(self.index, len(frames)-1)]
        task.screenshot = screenshot
        task.appear = appear
        task.ui_reward_appear_click = Mock(
            side_effect=clicks, return_value=True)
        task.appear_then_click = Mock(return_value=True)
        self.task = task
        with patch('time.time', side_effect=lambda: self.now):
            collect(task, 'submit', dismiss_soul_details=soul)

    def test_single_reward_returns_without_waiting_for_second(self):
        self.run_frames([{'submit'}, {'reward'}, {'list'}])
        self.assertEqual(self.task.ui_reward_appear_click.call_count, 1)
        self.assertGreaterEqual(self.now, 104)
        self.assertLess(self.now, 110)

    def test_second_reward_after_list_gap_is_collected(self):
        self.run_frames([{'reward'}] + [{'list'}]*5 + [{'reward'}, {'list'}])
        self.assertEqual(self.task.ui_reward_appear_click.call_count, 2)

    def test_three_rewards_are_not_truncated_at_two(self):
        self.run_frames([{'reward'}, set(), {'reward'}, set(), {'reward'}, {'list'}])
        self.assertEqual(self.task.ui_reward_appear_click.call_count, 3)

    def test_click_cooldown_and_visible_list_do_not_finish(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'reward', 'list'}], clicks=lambda _: False)

    def test_persistent_reward_times_out_even_with_successful_clicks(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'reward', 'list'}])
        self.assertLessEqual(self.now, 121)

    def test_unknown_page_after_reward_is_not_success(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'reward'}, set()])

    def test_list_without_reward_does_not_claim_success(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'list'}])

    def test_submission_retry_is_bounded(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'submit'}])
        self.assertGreater(self.task.appear_then_click.call_count, 1)
        self.assertLessEqual(self.now, 121)

    def test_no_resubmission_after_reward(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'reward'}, {'submit', 'list'}])
        self.task.appear_then_click.assert_not_called()

    def test_interrupted_list_stability_restarts_wait(self):
        self.run_frames([{'reward'}] + [{'list'}]*4 + [set()] + [{'list'}]*8)
        self.assertGreater(self.now, 106)

    def test_soul_details_click_count_then_submit_and_collect(self):
        self.run_frames([{'details'}, {'submit'}, {'reward'}, {'list'}], soul=True)
        self.task.click.assert_called_once_with(self.task.O_SL_NUMBER, interval=3)
        self.task.appear_then_click.assert_called_once_with('submit', interval=1)

    def test_visible_soul_submit_does_not_click_title(self):
        self.run_frames([{'submit'}, {'reward'}, {'list'}], soul=True)
        self.task.click.assert_not_called()

    def test_invalid_or_zero_count_does_not_click_or_finish(self):
        for text in ('', '0', '将提交0次任务', '其他30次任务'):
            with self.subTest(text=text), self.assertRaises(GameStuckError):
                self.run_frames([{'details'}], soul=True, text=text)
            self.task.click.assert_not_called()

    def test_persistent_details_cannot_claim_success(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'details'}], soul=True)
        self.task.appear_then_click.assert_not_called()
        self.assertLessEqual(self.now, 121)

    def test_soul_title_not_clicked_after_reward(self):
        with self.assertRaises(GameStuckError):
            self.run_frames([{'reward'}, {'details'}], soul=True)
        self.task.click.assert_not_called()

    def test_soul_path_uses_verified_completion(self):
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_soul')
        call = next(n for n in ast.walk(method) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == '_submit_and_collect_rewards')
        self.assertEqual(call.args[0].attr, 'I_SL_SUBMIT')
        self.assertEqual(call.keywords[0].arg, 'dismiss_soul_details')
        self.assertTrue(call.keywords[0].value.value)

    def test_material_and_feed_paths_share_completion_logic(self):
        for name,button in [('_donate','I_CM_PRESENT'),('_feed','I_FEED_SUBMIT')]:
            method = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
            calls=[n for n in ast.walk(method) if isinstance(n,ast.Call)
                   and isinstance(n.func,ast.Attribute) and n.func.attr=='_submit_and_collect_rewards']
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0].args[0].attr,button)


if __name__ == '__main__':
    unittest.main()
