"""Offline regression tests for the non-combat Demon Encounter workflow."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tasks.DemonEncounter.config import DemonEncounter
from tasks.DemonEncounter import script_task as module
from module.config.config_model import ConfigModel
from module.exception import TaskEnd


class SkipBattlesTests(unittest.TestCase):
    def make_task(self, enabled):
        task = object.__new__(module.ScriptTask)
        task.conf = DemonEncounter(encounter_options={'skip_all_battles': enabled})
        task.config = SimpleNamespace(demon_encounter=task.conf)
        return task

    def test_default_and_frontend_schema(self):
        cfg = DemonEncounter()
        self.assertFalse(cfg.encounter_options.skip_all_battles)
        data = ConfigModel.script_task(SimpleNamespace(demon_encounter=cfg), 'DemonEncounter')
        arg = data['encounter_options'][0]
        self.assertEqual(arg['name'], 'skip_all_battles')
        self.assertEqual(arg['description'], 'skip_all_battles_help')
        self.assertEqual(arg['type'], 'boolean')
        self.assertFalse(arg['value'])
        cfg.encounter_options.skip_all_battles = True
        self.assertTrue(DemonEncounter.model_validate_json(cfg.model_dump_json()).encounter_options.skip_all_battles)
        root = Path(__file__).resolve().parents[1]
        for lang in ['zh-CN', 'en-US']:
            strings = json.loads((root / f'assets/i18n/{lang}.json').read_text(encoding='utf-8'))
            for key in ['encounter_options', 'skip_all_battles', 'skip_all_battles_help']:
                self.assertTrue(strings[key])

    def test_all_combat_entry_points_return_before_ui_actions(self):
        for method in ['_battle', '_realm', '_boss', 'execute_boss']:
            task = self.make_task(True)
            task.screenshot = Mock(side_effect=AssertionError('Combat entry touched the UI'))
            task.click = Mock(side_effect=AssertionError('Combat entry clicked'))
            task.run_general_battle = Mock(side_effect=AssertionError('Combat started'))
            with self.subTest(method=method):
                args = () if method == 'execute_boss' else ('target',)
                getattr(task, method)(*args)
                task.screenshot.assert_not_called()
                task.click.assert_not_called()
                task.run_general_battle.assert_not_called()

    def test_enabled_returns_home_and_schedules_without_soul_switch(self):
        task = self.make_task(True)
        task.conf.demon_soul_config.enable = True
        task.conf.best_demon_soul_config.enable = True
        task.check_time = Mock(return_value=True)
        task.ui_get_current_page = Mock()
        task.ui_goto = Mock()
        task.checkout_soul = Mock()
        task.execute_lantern = Mock()
        task.set_next_run = Mock()
        with self.assertRaises(TaskEnd):
            task.run()
        task.checkout_soul.assert_not_called()
        task.execute_lantern.assert_called_once()
        self.assertEqual([c.args[0] for c in task.ui_goto.call_args_list],
                         [module.page_demon_encounter_realworld, module.page_main])
        task.set_next_run.assert_called_once_with(task='DemonEncounter', success=True, finish=False)

    def test_disabled_keeps_original_flow(self):
        task = self.make_task(False)
        task.conf.demon_soul_config.enable = True
        task.check_time = Mock(return_value=True)
        task.ui_get_current_page = Mock()
        task.ui_goto = Mock()
        task.checkout_soul = Mock()
        task.execute_lantern = Mock()
        task.execute_boss = Mock()
        task.set_next_run = Mock()
        with self.assertRaises(TaskEnd):
            task.run()
        task.checkout_soul.assert_called_once()
        task.execute_lantern.assert_called_once()
        task.execute_boss.assert_called_once()
        self.assertEqual([c.args[0] for c in task.ui_goto.call_args_list],
                         [module.page_shikigami_records, module.page_demon_encounter_realworld])
        task.set_next_run.assert_called_once_with(task='DemonEncounter', success=True, finish=False)

    def test_lantern_discoveries_rewards_and_noncombat_events_remain(self):
        kinds = module.LanternClass
        for events in ([kinds.BATTLE, kinds.REALM, kinds.BOSS, kinds.MAIL],
                       [kinds.BOX, kinds.MAIL, kinds.EMPTY, kinds.MYSTERY]):
            task = self.make_task(True)
            task.screenshot = Mock()
            task.device = SimpleNamespace(image=object())
            task.O_DE_COUNTER = SimpleNamespace(ocr=Mock(side_effect=[(1, 3, 4), (0, 4, 4)]))
            task.appear_then_click = Mock(return_value=True)
            task.appear = Mock(return_value=False)
            task.ui_get_reward = Mock()
            task.wait_until_appear = Mock()
            task.check_lantern = Mock(side_effect=events)
            task._box = Mock()
            task._mail = Mock()
            task._mystery = Mock()
            task.click = Mock(side_effect=AssertionError('Skipped lantern was opened'))
            task.run_general_battle = Mock(side_effect=AssertionError('Combat started'))
            with patch.object(module, 'Timer') as timer, patch.object(module.time, 'sleep'):
                timer.return_value.reached.return_value = True
                task.execute_lantern()
            task.appear_then_click.assert_called_once_with(task.I_DE_FIND, interval=2.5)
            task.ui_get_reward.assert_called_once_with(task.I_DE_RED_DHARMA)
            self.assertEqual(task.check_lantern.call_count, 4)
            self.assertEqual(task._box.call_count, events.count(kinds.BOX))
            self.assertEqual(task._mail.call_count, events.count(kinds.MAIL))
            self.assertEqual(task._mystery.call_count, events.count(kinds.MYSTERY))
            task.click.assert_not_called()
            task.run_general_battle.assert_not_called()


if __name__ == '__main__':
    unittest.main()
