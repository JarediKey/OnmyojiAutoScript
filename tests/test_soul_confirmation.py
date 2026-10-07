"""Exercise the production confirmation method with deterministic UI frames."""
import ast
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
GameStuckError = runpy.run_path(str(ROOT / 'module/exception.py'))['GameStuckError']
source = ast.parse((ROOT / 'tasks/Component/SwitchSoul/switch_soul.py').read_text(encoding='utf-8'))
cls = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'SwitchSoul')
method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_apply_soul_preset_by_name')
namespace = {'Timer': Timer, 'GameStuckError': GameStuckError, 'logger': Mock()}
exec(compile(ast.Module(body=[method], type_ignores=[]), '<production method>', 'exec'), namespace)
apply_preset = namespace['_apply_soul_preset_by_name']


class ConfirmationTests(unittest.TestCase):
    def run_frames(self, frames, clicks=None, found=True, visible=True, retries=True):
        self.now = 100.0
        self.index = -1
        self.confirm_clicks = 0
        task = SimpleNamespace(O_SS_TEAM_NAME=SimpleNamespace(), I_SOU_CLICK_PRESENT='apply',
                               I_SOU_SWITCH_SURE='confirm', I_SOU_CHECK_IN='records')
        def screenshot():
            self.now += 0.3
            self.index += 1
        def appear(target):
            dialog, records = frames[min(self.index, len(frames) - 1)]
            return dialog if target == 'confirm' else records
        def click(*args, **kwargs):
            self.confirm_clicks += 1
            return True if clicks is None else clicks[min(self.confirm_clicks - 1, len(clicks) - 1)]
        task.screenshot = screenshot
        task.appear = appear
        task.appear_then_click = click
        task.ocr_appear = Mock(return_value=visible)
        task.ocr_appear_click_by_rule = Mock(
            side_effect=([True] + [retries] * 30) if found else None, return_value=False)
        self.task = task
        with patch('time.time', side_effect=lambda: self.now):
            return apply_preset(task, 'target')

    def test_delayed_dialog_and_disappearing_name(self):
        self.assertTrue(self.run_frames([(False, True)] * 7 + [(True, False)] * 2 + [(False, True)] * 5))

    def test_retry_confirmation(self):
        self.assertTrue(self.run_frames([(False, True)] + [(True, False)] * 5 + [(False, True)] * 5))
        self.assertEqual(self.confirm_clicks, 5)

    def test_click_cooldown_is_not_dialog_closure(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(True, True)], clicks=[True, False])

    def test_one_missed_frame_does_not_finish(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(True, False)] * 3 + [(False, True)] + [(True, False)] * 20)

    def test_already_applied_without_dialog(self):
        self.assertTrue(self.run_frames([(False, True)]))
        self.assertEqual(self.task.ocr_appear_click_by_rule.call_count, 3)
        self.assertEqual(self.confirm_clicks, 0)
        self.assertGreaterEqual(self.now, 105)

    def test_no_dialog_unknown_page(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(False, False)])

    def test_no_dialog_missing_target(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(False, True)], visible=False)

    def test_no_dialog_failed_retries(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(False, True)], retries=False)

    def test_dialog_never_clicked_is_not_noop(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(True, True)] * 3 + [(False, True)] * 20, clicks=[False])

    def test_late_dialog_still_requires_confirmation(self):
        self.assertTrue(self.run_frames([(False, True)] * 11 + [(True, False)] + [(False, True)] * 8))

    def test_unknown_page_after_confirm_is_not_success(self):
        with self.assertRaisesRegex(GameStuckError, 'Confirm'):
            self.run_frames([(True, False)] * 3 + [(False, False)] * 20)

    def test_missing_name_times_out(self):
        with self.assertRaisesRegex(GameStuckError, 'Apply'):
            self.run_frames([(False, True)], found=False)


if __name__ == '__main__':
    unittest.main()
