"""Bounded UI recovery checks without a running game."""
import ast
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
Timer = runpy.run_path(str(ROOT / 'module/base/timer.py'))['Timer']
GameStuckError = runpy.run_path(str(ROOT / 'module/exception.py'))['GameStuckError']


def method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = dict(Timer=Timer, GameStuckError=GameStuckError, logger=Mock(), page_main='main')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
    return ns[name]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.clock = patch('time.time', side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def frame(self):
        self.now += .5

    def test_mail_entry_times_out_without_restarting_game(self):
        task = SimpleNamespace(screenshot=self.frame, appear=Mock(return_value=False),
                               appear_then_click=Mock(return_value=False),
                               appear_then_click_multi_scale=Mock(return_value=False))
        for name in ['READ_ALL_MAIL','MAIL_TOOLBAR','HARVEST_MAIL','HARVEST_MAIL_COPY']:
            setattr(task, 'I_'+name, name)
        self.assertFalse(method('tasks/Restart/login.py', 'harvest_mail')(task))
        self.assertLessEqual(self.now, 113)
        self.assertTrue(task.appear_then_click.called)

    def test_toolbar_then_collect_mail(self):
        task = SimpleNamespace(screenshot=self.frame, appear=lambda _: self.now >= 101,
                               appear_then_click=Mock(return_value=True),
                               appear_then_click_multi_scale=Mock(side_effect=AssertionError))
        for name in ['READ_ALL_MAIL','MAIL_TOOLBAR','HARVEST_MAIL','HARVEST_MAIL_COPY',
                     'HARVEST_MAIL_CONFIRM','HARVEST_MAIL_ALL','MAIL_RED_POINT']:
            setattr(task, 'I_'+name, name)
        task.ui_click_until_disappear = Mock()
        task.I_LOGIN_RED_CLOSE = 'close'
        self.assertTrue(method('tasks/Restart/login.py', 'harvest_mail')(task))
        self.assertEqual(task.appear_then_click.call_args_list[0].args[0], 'MAIL_TOOLBAR')

    def story(self, visible):
        task = SimpleNamespace(screenshot=self.frame, appear=visible,
                               click=Mock(), I_SECRET_STORY='story', C_SECRET_CHAT='advance')
        return task

    def test_story_advances_until_it_disappears(self):
        task = self.story(lambda _: self.now < 103)
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertTrue(task.click.called)
        self.assertLess(self.now, 106)

    def test_non_story_page_is_not_clicked(self):
        task = self.story(lambda _: False)
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        task.click.assert_not_called()

    def test_story_never_ending_is_bounded(self):
        task = self.story(lambda _: True)
        with self.assertRaises(GameStuckError):
            method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertLessEqual(self.now, 131)

    def test_store_return_uses_current_page_navigation(self):
        task = SimpleNamespace(ui_get_current_page=Mock(), ui_goto=Mock(),
             run_store_sign=Mock(), run_buy_sushi=Mock(),
             config=SimpleNamespace(daily_trifles=SimpleNamespace(
                 trifles_config=SimpleNamespace(store_sign=True,buy_sushi_count=0))))
        fn = method('tasks/DailyTrifles/script_task.py', 'run_store')
        fn.__globals__['page_mall'] = 'mall'
        fn(task)
        self.assertEqual(task.ui_goto.call_args.args, ('main',))


if __name__ == '__main__':
    unittest.main()
