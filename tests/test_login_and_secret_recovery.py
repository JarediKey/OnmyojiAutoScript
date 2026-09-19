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

    def story(self, scene):
        task = SimpleNamespace(screenshot=self.frame, appear=lambda target: target in scene(self.now),
                               click=Mock(), I_SECRET_STORY='story', I_SECRET_STORY_SHANTU='shantu',
                               I_WQSE_FIRE='challenge', I_CHECK_SECRET_ZONES='zones', C_SECRET_CHAT='advance')
        return task

    def test_story_advances_until_challenge_is_confirmed(self):
        task = self.story(lambda now: {'story'} if now < 103 else {'challenge'})
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertTrue(task.click.called)
        self.assertLess(self.now, 106)
        self.assertGreaterEqual(self.now, 104)

    def test_unknown_page_is_not_clicked_or_treated_as_completion(self):
        task = self.story(lambda now: set())
        with self.assertRaisesRegex(GameStuckError, 'not confirmed'):
            method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        task.click.assert_not_called()
        self.assertLessEqual(self.now, 131)

    def test_story_never_ending_is_bounded(self):
        task = self.story(lambda now: {'story'})
        with self.assertRaises(GameStuckError):
            method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertLessEqual(self.now, 131)

    def test_shantu_dialogue_keeps_advancing_when_old_marker_is_missing(self):
        def scene(now):
            if now < 102:
                return {'story'}
            if now < 105:
                return {'shantu'}
            return {'zones'}
        task = self.story(scene)
        clicks = []
        task.click.side_effect = lambda *args, **kwargs: clicks.append((self.now, kwargs['interval']))
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertTrue(any(now >= 102 for now, _ in clicks))
        self.assertTrue(all(interval == 1.5 for _, interval in clicks))
        self.assertGreaterEqual(self.now, 106)

    def test_long_unrecognized_transition_does_not_finish_early(self):
        def scene(now):
            if now < 102:
                return {'story'}
            if now < 108:
                return set()
            return {'challenge'}
        task = self.story(scene)
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertGreaterEqual(self.now, 109)

    def test_visible_story_takes_precedence_over_background_destination(self):
        task = self.story(lambda now: {'shantu', 'challenge'} if now < 105 else {'challenge'})
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertTrue(task.click.called)
        self.assertGreaterEqual(self.now, 106)

    def test_brief_destination_detection_must_be_confirmed_again(self):
        task = self.story(lambda now: {'zones'} if now in (100.5, 101) or now >= 105 else set())
        method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
        self.assertGreaterEqual(self.now, 106)
        task.click.assert_not_called()

    def test_already_on_challenge_or_zone_list_finishes_without_clicks(self):
        for destination in ('challenge', 'zones'):
            with self.subTest(destination=destination):
                self.now = 100
                task = self.story(lambda now: {destination})
                method('tasks/WantedQuests/script_task.py', 'finish_secret_story')(task)
                task.click.assert_not_called()
                self.assertGreater(self.now, 101)
                self.assertLess(self.now, 103)

    def secret_task(self):
        task = Mock()
        task.screenshot.side_effect = self.frame
        task.appear.return_value = False
        task.appear_then_click.return_value = False
        task.wait_until_appear.return_value = True
        return task

    def test_missing_next_challenge_prevents_another_battle(self):
        task = self.secret_task()
        task.wait_until_appear.side_effect = [True, False]
        with self.assertRaisesRegex(GameStuckError, 'challenge did not appear'):
            method('tasks/WantedQuests/script_task.py', 'secret')(task, 'goto', 2)
        self.assertEqual(task.run_general_battle.call_count, 1)
        self.assertEqual(task.finish_secret_story.call_count, 1)
        self.assertTrue(all(call.kwargs['wait_time'] == 10 for call in task.wait_until_appear.call_args_list))
        task.ui_get_current_page.assert_not_called()

    def test_unresolved_story_stops_before_next_battle_or_navigation(self):
        task = self.secret_task()
        task.finish_secret_story.side_effect = GameStuckError('Unresolved story')
        with self.assertRaisesRegex(GameStuckError, 'Unresolved story'):
            method('tasks/WantedQuests/script_task.py', 'secret')(task, 'goto', 2)
        self.assertEqual(task.run_general_battle.call_count, 1)
        self.assertEqual(task.wait_until_appear.call_count, 1)
        task.ui_get_current_page.assert_not_called()

    def test_missing_zone_list_has_a_bounded_exit(self):
        task = self.secret_task()
        with self.assertRaisesRegex(GameStuckError, 'zone list did not appear'):
            method('tasks/WantedQuests/script_task.py', 'secret')(task, 'goto', 1)
        self.assertLessEqual(self.now, 122)
        task.ui_get_current_page.assert_not_called()

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
