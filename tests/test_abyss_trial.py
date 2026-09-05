"""Offline checks for the ported trial, without game/device access."""

import ast
import json
from pathlib import Path
import copy
import os
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
        from tasks.GameUi.assets import GameUiAssets
        env = dict(Code=Code, EnemyType=EnemyType, MAX_BATTLE_COUNT=2, MAX_BATTLE_WAIT=300,
                   MAX_ENTRY_WAIT=30, GameUiAssets=GameUiAssets,
                   logger=Mock(), Timer=FakeTimer, RequestHumanTakeover=RequestHumanTakeover)
        methods = [n for n in task.body if isinstance(n, ast.FunctionDef) and n.name in (
            'execute', 'run_battle', 'quit_battle', 'battle_entry_state', 'enter_battle',
            'attack_enemy', 'exit_abyss_records', 'switch_soul_in_as')]
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
        self.obj.request_takeover.side_effect = self.takeover('Test takeover')
        self.obj.cur_preset = None
        self.obj.switch_soul_done = False

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
        self.assertTrue(cfg.process_manage.lock_team_enable)
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

    def entry_frames(self, frames, locked=True):
        cfg = self.config_type()
        cfg.process_manage.lock_team_enable = locked
        self.obj.config.model.abyss_shadows = cfg
        visible = set()
        stream = iter(frames)
        def screenshot():
            visible.clear()
            visible.update(next(stream))
        self.obj.screenshot.side_effect = screenshot
        self.obj.appear.side_effect = lambda button, **kw: button in visible
        self.obj.appear_then_click.side_effect = lambda button, **kw: button in visible
        self.obj.battle_entry_state.side_effect = lambda: self.methods['battle_entry_state'](self.obj)

    def battle_markers(self):
        return {self.obj.I_BATTLE_INFO, self.obj.I_EXIT}

    def test_locked_team_auto_entry_never_selects_or_clicks_prepare(self):
        self.entry_frames([self.battle_markers()])
        self.methods['enter_battle'](self.obj, self.code)
        self.obj.switch_preset_team_with_str.assert_not_called()
        self.obj.appear_then_click.assert_not_called()

    def test_prepare_with_exit_button_still_retries_until_battle(self):
        prepare = {self.obj.I_PREPARE_HIGHLIGHT, self.obj.I_EXIT}
        self.entry_frames([prepare, prepare, self.battle_markers()])
        self.methods['enter_battle'](self.obj, self.code)
        self.assertEqual(self.obj.appear_then_click.call_count, 2)
        self.obj.switch_preset_team_with_str.assert_not_called()
        self.obj.appear_then_click.assert_called_with(self.obj.I_PREPARE_HIGHLIGHT, interval=0.6)

    def test_exit_only_and_dark_prepare_do_not_prove_battle(self):
        self.entry_frames([{self.obj.I_EXIT}, {self.obj.I_PREPARE_DARK, self.obj.I_EXIT}, self.battle_markers()])
        self.methods['enter_battle'](self.obj, self.code)
        self.assertEqual(self.obj.screenshot.call_count, 3)
        self.obj.appear_then_click.assert_not_called()

    def test_unlocked_preset_waits_for_panel_to_close_before_prepare(self):
        prepare = {self.obj.I_PREPARE_HIGHLIGHT}
        self.entry_frames([prepare, prepare | {self.obj.I_PRESET_ENSURE}, prepare, self.battle_markers()], locked=False)
        self.methods['enter_battle'](self.obj, self.code)
        self.obj.switch_preset_team_with_str.assert_called_once_with('6,1')
        self.obj.appear_then_click.assert_called_once_with(self.obj.I_PREPARE_HIGHLIGHT, interval=0.6)
        self.assertEqual(self.obj.cur_preset, '6,1')

    def test_already_fighting_never_changes_even_an_unlocked_preset(self):
        self.entry_frames([self.battle_markers()], locked=False)
        self.methods['enter_battle'](self.obj, self.code)
        self.obj.switch_preset_team_with_str.assert_not_called()

    def test_result_on_entry_is_left_to_battle_result_handler(self):
        self.entry_frames([{self.obj.I_WIN}])
        self.methods['enter_battle'](self.obj, self.code)
        self.obj.appear_then_click.assert_not_called()

    def test_entry_timeout_preserves_stage_and_does_not_click(self):
        self.entry_frames([{self.obj.I_EXIT}])
        FakeTimer.expired = True
        with self.assertRaises(self.takeover):
            self.methods['enter_battle'](self.obj, self.code)
        self.assertEqual(self.obj.request_takeover.call_args.args[0], 'entry')
        self.obj.appear_then_click.assert_not_called()

    def test_challenge_accepts_auto_entry_without_prepare(self):
        self.entry_frames([self.battle_markers()])
        self.methods['attack_enemy'](self.obj)
        self.obj.appear_then_click.assert_not_called()

    def test_records_return_stops_on_map_even_with_yellow_back(self):
        back = self.obj.I_RECORD_SOUL_BACK
        self.entry_frames([{self.obj.I_ABYSS_NAVIGATION, self.obj.I_ABYSS_SHIKI, back}])
        self.methods['exit_abyss_records'](self.obj)
        self.obj.appear_then_click.assert_not_called()

    def test_records_return_does_not_click_during_transition(self):
        back = self.obj.I_RECORD_SOUL_BACK
        self.entry_frames([{self.obj.I_SOU_CHECK_IN, back}, {back},
                           {self.obj.I_ABYSS_NAVIGATION, self.obj.I_ABYSS_SHIKI, back}])
        self.methods['exit_abyss_records'](self.obj)
        self.obj.appear_then_click.assert_called_once_with(back, interval=2)

    def test_records_unknown_state_times_out_without_blind_return(self):
        self.entry_frames([set()])
        FakeTimer.expired = True
        with self.assertRaises(self.takeover):
            self.methods['exit_abyss_records'](self.obj)
        self.obj.appear_then_click.assert_not_called()

    def test_locked_team_does_not_disable_soul_preload(self):
        cfg = self.config_type()
        process = cfg.process_manage
        process.lock_team_enable = True
        process.enable_switch_soul_in_as = True
        process.preset_boss = process.preset_general = process.preset_elite = '6,1'
        self.obj.config.model.abyss_shadows = cfg
        self.methods['switch_soul_in_as'](self.obj)
        self.obj.run_switch_soul.assert_called_once_with((6, 1))
        self.obj.exit_abyss_records.assert_called_once()
        self.assertTrue(self.obj.switch_soul_done)
        self.methods['switch_soul_in_as'](self.obj)
        self.assertEqual(self.obj.run_switch_soul.call_count, 1)

    def test_four_account_routes_and_presets(self):
        data = json.loads((self.root / 'deploy/examples/abyss-trial-accounts.json').read_text(encoding='utf-8'))
        presets = ('7,2', '7,1', '6,1', '2,1')
        for i in range(1, 5):
            cfg = self.config_type.model_validate(data[f'abyss-trial-{i}']['abyss_shadows'])
            primary, backup = ('AB', 'DC') if i <= 2 else ('CD', 'BA')
            expected = [f'{area}-{n}' for area in primary for n in (4,5,6,2,3,1)]
            expected += [f'{area}-{n}' for group in ((1,), (2,3), (4,5,6)) for area in backup for n in group]
            actual = self.CodeList(cfg.process_manage.attack_order)
            self.assertEqual(actual, expected)
            self.assertEqual(len(set(actual)), 24)
            self.assertTrue(cfg.process_manage.lock_team_enable)
            for kind in ('boss', 'general', 'elite'):
                self.assertEqual(getattr(cfg.process_manage, f'preset_{kind}'), presets[i-1])

    def test_action_intervals_are_scoped_and_doubled_once(self):
        tree = ast.parse((self.root / 'tasks/AbyssShadows/script_task.py').read_text(encoding='utf-8'))
        source = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ScriptTask')
        wrappers = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ('click', 'swipe', 'appear_then_click')]
        class Parent:
            def click(self, target, interval=None):
                return interval
            def swipe(self, target, interval=None):
                return interval
            def appear_then_click(self, target, **kw):
                return kw['interval']
        node = ast.ClassDef(name='Intervals', bases=[ast.Name(id='Parent', ctx=ast.Load())],
                            keywords=[], body=wrappers, decorator_list=[])
        env = {'Parent': Parent}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<intervals>', 'exec'), env)
        obj = env['Intervals']()
        for name in ('click', 'swipe', 'appear_then_click'):
            for original in (None, 0, 0.2, 0.6, 1, 2, 3.5):
                self.assertEqual(getattr(obj, name)('button', interval=original), original * 2 if original else original)
        self.assertEqual(Parent().click('button', interval=1), 1)

    @unittest.skipUnless(os.environ.get('ABYSS_RECORDING_FRAMES'), 'Private recording frames are not bundled')
    def test_recorded_frames_classify_preparation_battle_and_records(self):
        import cv2
        from tasks.AbyssShadows.assets import AbyssShadowsAssets
        from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
        from tasks.Component.SwitchSoul.assets import SwitchSoulAssets
        from tasks.Component.Costume.costume_base import CostumeBase
        from tasks.Component.Costume.config import BattleType, ShikigamiType
        from module.atom.image import RuleImage
        class Assets(CostumeBase, AbyssShadowsAssets, GeneralBattleAssets, SwitchSoulAssets):
            pass
        folder = Path(os.environ['ABYSS_RECORDING_FRAMES'])
        checked = 0
        for account in range(1, 5):
            obj = Assets()
            # Production uses separate processes. Isolate mutable asset objects
            # before applying the same global skin mapping in this offline test.
            for name in dir(obj):
                asset = getattr(obj, name)
                if isinstance(asset, RuleImage):
                    setattr(obj, name, copy.deepcopy(asset))
            if account == 1:
                obj.check_costume_battle(BattleType.COSTUME_BATTLE_5)
                obj.check_costume_shikigami(ShikigamiType.COSTUME_SHIKIGAMI_1)
            for sec in (40, 50, 60, 90, 170, 180, 190, 220, 230, 240, 250):
                path = folder / f'account-{account}-{sec:04d}.png'
                frame = cv2.imread(str(path))
                self.assertIsNotNone(frame, str(path))
                self.assertEqual(frame.shape, (720, 1280, 3))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                obj.appear = lambda rule: rule.match(frame)
                state = self.methods['battle_entry_state'](obj)
                in_records = obj.appear(obj.I_SOU_CHECK_IN)
                expected_records = (account in (1,2) and sec == 60) or (account in (3,4) and sec == 50)
                self.assertEqual(in_records, expected_records, path.name)
                if sec == 250 or (sec == 240 and account != 1):
                    self.assertEqual(state, 'battle', path.name)
                elif (sec in (220,230,240) and account == 1 and sec != 220) or (sec in (220,230) and account != 1):
                    self.assertIn(state, ('prepare', 'preset'), path.name)
                else:
                    self.assertNotEqual(state, 'battle', path.name)
                checked += 1
        self.assertEqual(checked, 44)


if __name__ == '__main__':
    unittest.main()
