"""Check the actual login loop with simulated OCR and no game/device access."""

import ast
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
exceptions = runpy.run_path(str(ROOT / 'module/exception.py'))
GameTooManyClickError = exceptions['GameTooManyClickError']


class FakeTimer:
    def __init__(self, limit, count=0):
        self.confirm = bool(count)
        self.checks = 0

    def start(self):
        return self

    def reached(self):
        self.checks += 1
        return self.confirm and self.checks >= 2

    def reset(self):
        self.checks = 0


class LoginEntryRetriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = ast.parse((ROOT / 'tasks/Restart/login.py').read_text(encoding='utf-8'))
        handler = next(node for node in source.body if isinstance(node, ast.ClassDef))
        method = next(node for node in handler.body
                      if isinstance(node, ast.FunctionDef) and node.name == '_app_handle_login')
        namespace = dict(Timer=FakeTimer, logger=Mock(), **exceptions)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<login-loop>', 'exec'), namespace)
        cls.login = staticmethod(namespace['_app_handle_login'])

    def setUp(self):
        assets = patch.dict('sys.modules', {
            'tasks.Component.GeneralInvite.assets': SimpleNamespace(GeneralInviteAssets=Mock())})
        assets.start()
        self.addCleanup(assets.stop)
        self.task = Mock()
        self.task.O_LOGIN_ENTER_GAME_ORIGIN = SimpleNamespace(
            name='LOGIN_ENTER_GAME_ORIGIN', coord=lambda: (640, 600))
        self.task.O_LOGIN_ENTER_GAME = SimpleNamespace(
            name='LOGIN_ENTER_GAME', coord=lambda: (640, 600))
        self.task.appear.side_effect = lambda target, **kwargs: target is self.task.I_LOGIN_8
        self.task.appear_then_click.return_value = False
        self.task.ocr_appear.side_effect = self.recognize

    def recognize(self, target, **kwargs):
        # Alternate OCR variants so they cannot receive independent budgets.
        selected = (self.task.O_LOGIN_ENTER_GAME_ORIGIN, self.task.O_LOGIN_ENTER_GAME)[
            self.task.device.click.call_count % 2]
        return target is selected

    def test_thirty_actual_clicks_are_allowed_and_the_thirty_first_is_blocked(self):
        with self.assertRaisesRegex(GameTooManyClickError, '30 clicks'):
            self.login(self.task)
        self.assertEqual(self.task.device.click.call_count, 30)
        self.assertEqual(self.task.device.stuck_record_clear.call_count, 30)
        names = [call.kwargs['control_name'] for call in self.task.device.click.call_args_list]
        self.assertEqual(names.count('LOGIN_ENTER_GAME_ORIGIN'), 15)
        self.assertEqual(names.count('LOGIN_ENTER_GAME'), 15)
        for call in self.task.device.click.call_args_list:
            self.assertIs(call.kwargs['control_check'], False)
        for call in self.task.ocr_appear.call_args_list:
            self.assertEqual(call.kwargs['interval'], 3)
        self.assertEqual(self.task.wait_until_appear.call_count, 30)
        for call in self.task.wait_until_appear.call_args_list:
            self.assertEqual(call.kwargs['wait_time'], 5)

    def test_success_after_thirtieth_click_is_accepted_and_next_login_resets_budget(self):
        for attempt in range(2):
            baseline = self.task.device.click.call_count

            def appear(target, **kwargs):
                ready = self.task.device.click.call_count - baseline >= 30
                if ready:
                    return target in (self.task.I_BUFF_1, self.task.I_MAIN_GOTO_SHIKIGAMI_RECORDS)
                return target is self.task.I_LOGIN_8

            self.task.appear.side_effect = appear
            self.assertTrue(self.login(self.task))
            self.assertEqual(self.task.device.click.call_count, (attempt + 1) * 30)

    def test_missing_ocr_match_does_not_consume_a_click(self):
        checks = 0

        def recognize(target, **kwargs):
            nonlocal checks
            checks += 1
            if checks <= 20:
                return False
            return target is self.task.O_LOGIN_ENTER_GAME_ORIGIN

        self.task.ocr_appear.side_effect = recognize
        with self.assertRaises(GameTooManyClickError):
            self.login(self.task)
        self.assertEqual(self.task.device.click.call_count, 30)
        self.assertGreater(checks, 50)


if __name__ == '__main__':
    unittest.main()
