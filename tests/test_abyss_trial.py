"""Offline checks for the ported trial, without game/device access."""

import ast
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

import test_ocr_color_filter as ocr_checks


class FakeTimer:
    expired = False

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return self

    def reached(self):
        return self.expired


class AbyssTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ocr_checks.OcrPipelineTests.setUpClass()
        from tasks.AbyssShadows.config import AbyssShadows, Code, Condition, CodeList
        from module.exception import RequestHumanTakeover
        cls.config_type = AbyssShadows
        cls.Code = Code
        cls.Condition = Condition
        cls.CodeList = CodeList
        cls.takeover = RequestHumanTakeover
        cls.root = Path(__file__).resolve().parents[1]
        tree = ast.parse((cls.root / 'tasks/AbyssShadows/script_task.py').read_text(encoding='utf-8'))
        task = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ScriptTask')
        from tasks.AbyssShadows.config import EnemyType
        env = dict(Code=Code, EnemyType=EnemyType, MAX_BATTLE_COUNT=2, MAX_BATTLE_WAIT=300,
                   logger=Mock(), Timer=FakeTimer, RequestHumanTakeover=RequestHumanTakeover)
        methods = [n for n in task.body if isinstance(n, ast.FunctionDef) and n.name in ('execute', 'run_battle', 'quit_battle')]
        exec(compile(ast.Module(body=methods, type_ignores=[]), '<abyss-trial>', 'exec'), env)
        cls.methods = env

    @classmethod
    def tearDownClass(cls):
        ocr_checks.OcrPipelineTests.tearDownClass()

    def setUp(self):
        FakeTimer.expired = False
        self.obj = Mock()
        self.obj.done_list = self.CodeList('')
        self.obj.failed_list = self.CodeList('')
        self.obj.unavailable_list = self.CodeList('')
        self.obj.change_area.return_value = True
        self.obj.goto_enemy.return_value = True
        self.code = self.Code('A-1')

    def test_failed_attempts_are_not_completed(self):
        self.obj.run_battle.return_value = False
        self.assertFalse(self.methods['execute'](self.obj, self.code))
        self.assertEqual(self.obj.run_battle.call_count, 2)
        self.assertEqual(self.obj.done_list, [])
        self.assertEqual(self.obj.failed_list, [self.code])

    def test_success_stops_retrying_and_records_completion(self):
        self.obj.run_battle.side_effect = [False, True]
        self.assertTrue(self.methods['execute'](self.obj, self.code))
        self.assertEqual(self.obj.done_list, [self.code])
        self.assertEqual(self.obj.failed_list, [])

    def test_failed_navigation_is_not_proof_of_death(self):
        self.obj.goto_enemy.return_value = False
        self.assertFalse(self.methods['execute'](self.obj, self.code))
        self.assertEqual(self.obj.failed_list, [self.code])
        self.assertEqual(self.obj.unavailable_list, [])
        self.obj.run_battle.assert_not_called()

    def configure_frames(self, frames):
        cfg = self.config_type()
        cfg.process_manage.preset_boss = ''
        cfg.process_manage.mark_main = 'NONE'
        self.obj.config.model.abyss_shadows = cfg
        self.obj.wait_until_appear.return_value = True
        self.obj.ui_click.return_value = True
        current = {'frame': None}
        iterator = iter(frames)
        self.obj.screenshot.side_effect = lambda: current.update(frame=next(iterator))
        self.obj.appear.side_effect = lambda button: (
            (current['frame'] == 'failure' and button == self.obj.I_FALSE) or
            (current['frame'] == 'map' and button == self.obj.I_ABYSS_NAVIGATION))
        self.obj.appear_then_click.side_effect = lambda button, **kwargs: (
            current['frame'] == 'win' and button == self.obj.I_WIN)

    def test_natural_battle_waits_for_win_and_map(self):
        self.configure_frames(['battle', 'win', 'map'])
        self.assertTrue(self.methods['run_battle'](self.obj, self.code))
        self.obj.quit_battle.assert_not_called()
        self.assertEqual(self.obj.device.screenshot_interval_set.call_args.args, ())

    def test_defeat_returns_false_and_restores_screenshot_rate(self):
        self.configure_frames(['failure'])
        self.assertFalse(self.methods['run_battle'](self.obj, self.code))
        self.obj.quit_battle.assert_called_once()
        self.assertEqual(self.obj.device.screenshot_interval_set.call_args.args, ())

    def test_unconfirmed_map_return_is_not_victory(self):
        self.configure_frames(['map'])
        self.assertFalse(self.methods['run_battle'](self.obj, self.code))

    def test_timeout_requests_human_without_surrender(self):
        self.configure_frames(['battle'])
        FakeTimer.expired = True
        with self.assertRaises(self.takeover):
            self.methods['run_battle'](self.obj, self.code)
        self.obj.quit_battle.assert_not_called()
        self.assertEqual(self.obj.device.screenshot_interval_set.call_args.args, ())

    def test_trial_config_has_no_unrequested_actions(self):
        data = json.loads((self.root / 'deploy/examples/abyss-trial.json').read_text(encoding='utf-8'))['abyss_shadows']
        cfg = self.config_type.model_validate(data)
        self.assertTrue(cfg.process_manage.trial_mode)
        self.assertFalse(cfg.abyss_shadows_time.try_start_abyss_shadows)
        self.assertFalse(cfg.process_manage.enable_switch_soul_in_as)
        self.assertEqual(cfg.process_manage.attack_order, 'A')
        for kind in ('boss', 'general', 'elite'):
            self.assertEqual(getattr(cfg.process_manage, 'preset_' + kind), '')
            self.assertEqual(getattr(cfg.process_manage, 'strategy_' + kind), 'FALSE')

    def test_invalid_trial_settings_fail_validation(self):
        for field, value in (('attack_order', 'Z-8'), ('preset_boss', '9,1'),
                             ('strategy_boss', 'bad'), ('strategy_elite', '')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.config_type.model_validate({'process_manage': {field: value}})

    def test_damage_threshold_includes_equality(self):
        self.assertTrue(self.Condition('1000').is_valid(1000))
        self.assertFalse(self.Condition('FALSE').is_valid(999999999))


if __name__ == '__main__':
    unittest.main()
