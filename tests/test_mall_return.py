"""Exercise the real return loop with simulated frames and the shared timer."""

import ast
import __future__
from pathlib import Path
import runpy
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
errors = runpy.run_path(str(ROOT / 'module/exception.py'))
GameStuckError = errors['GameStuckError']


def method(path, class_name, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec',
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace[name]


class MallReturnTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.started = self.now
        clock = patch('time.time', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        # The courtyard marker represents the marker after skin selection.
        self.mall = SimpleNamespace(check_button='mall')
        self.courtyard = SimpleNamespace(check_button='custom-courtyard')
        namespace = dict(Timer=Timer, GameStuckError=GameStuckError, logger=Mock(),
                         page_mall=self.mall, page_main=self.courtyard)
        self.back = method('tasks/RichMan/mall/navbar.py', 'MallNavbar', 'back_mall', namespace)
        self.matcher = method('tasks/GameUi/game_ui.py', 'GameUi', 'ui_page_appear', {})
        self.appear_click = method('tasks/base_task.py', 'BaseTask', 'appear_then_click', {})
        self.frame_at = lambda elapsed: 'subpage'
        self.clicks = []
        self.frame = None
        self.last_match = {}
        self.task = SimpleNamespace(
            I_UI_BACK_YELLOW=SimpleNamespace(name='yellow-back', coord=lambda: (40, 40)),
            ui_current=None, screenshot=self.screenshot,
            maybe_screenshot=lambda skip: None if skip else self.screenshot(),
            appear=self.appear,
            device=SimpleNamespace(click=lambda *args, **kwargs: self.clicks.append((self.now, self.frame))))
        self.task.ui_page_appear = MethodType(self.matcher, self.task)
        self.task.appear_then_click = MethodType(self.appear_click, self.task)
        self.task.back_mall = MethodType(self.back, self.task)

    def screenshot(self):
        self.now += 0.25
        self.frame = self.frame_at(self.now - self.started)

    def appear(self, target, interval=None, threshold=None):
        if target is self.task.I_UI_BACK_YELLOW:
            visible = self.frame in ('subpage', 'mall', 'custom-courtyard')
            key = target.name
        else:
            visible = self.frame == target
            key = target
        if visible and interval:
            if self.now - self.last_match.get(key, float('-inf')) < interval:
                return False
            self.last_match[key] = self.now
        return visible

    def test_starting_at_either_destination_does_not_click_visible_back_button(self):
        for frame, page in [('mall', self.mall), ('custom-courtyard', self.courtyard)]:
            with self.subTest(frame=frame):
                self.frame_at = lambda elapsed: frame
                self.task.back_mall()
                self.assertIs(self.task.ui_current, page)
                self.assertEqual(self.clicks, [])

    def test_return_to_mall_stops_before_another_back_click(self):
        self.frame_at = lambda elapsed: 'subpage' if elapsed < 1 else 'mall'
        self.task.back_mall()
        self.assertEqual(len(self.clicks), 1)
        self.assertIs(self.task.ui_current, self.mall)

    def test_return_directly_to_courtyard_finishes_without_waiting_for_mall(self):
        self.frame_at = lambda elapsed: 'subpage' if elapsed < 1 else 'custom-courtyard'
        self.task.back_mall()
        self.assertEqual(len(self.clicks), 1)
        self.assertIs(self.task.ui_current, self.courtyard)
        self.assertLess(self.now - self.started, 2)

    def test_delayed_transition_preserves_three_second_click_spacing(self):
        self.frame_at = lambda elapsed: 'subpage' if elapsed < 7 else 'mall'
        self.task.back_mall()
        self.assertEqual(len(self.clicks), 3)
        for earlier, later in zip(self.clicks, self.clicks[1:]):
            self.assertGreaterEqual(later[0] - earlier[0], 3)
        self.assertTrue(all(frame == 'subpage' for _, frame in self.clicks))

    def test_unknown_page_without_back_button_times_out_without_clicking(self):
        self.frame_at = lambda elapsed: 'unknown'
        with self.assertRaisesRegex(GameStuckError, '20 seconds'):
            self.task.back_mall()
        self.assertEqual(self.clicks, [])
        self.assertIsNone(self.task.ui_current)
        self.assertLessEqual(self.now - self.started, 20.5)

    def test_visible_back_button_with_no_progress_also_has_a_deadline(self):
        with self.assertRaises(GameStuckError):
            self.task.back_mall()
        self.assertEqual(len(self.clicks), 7)
        self.assertIsNone(self.task.ui_current)
        self.assertLessEqual(self.now - self.started, 20.5)

    def test_failed_return_does_not_schedule_rich_man_as_success(self):
        run = method('tasks/RichMan/script_task.py', 'ScriptTask', 'run',
                     dict(RichMan=object, TaskEnd=errors['TaskEnd']))
        task = Mock()
        task.execute_mall.side_effect = self.task.back_mall
        self.frame_at = lambda elapsed: 'unknown'
        with self.assertRaises(GameStuckError):
            run(task)
        task.set_next_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
