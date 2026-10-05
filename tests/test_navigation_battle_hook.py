"""Check navigation's active-battle handler for combat and navigation-only tasks."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.GameUi.default_pages import handle_battle_page


class NavigationBattleHookTests(unittest.TestCase):
    def test_existing_task_keeps_its_battle_override(self):
        class ExistingBattle(GeneralBattle):
            def __init__(self):
                self.calls = 0
            def run_general_battle(self):
                self.calls += 1
                return False
        task = ExistingBattle()
        self.assertFalse(handle_battle_page(task))
        self.assertEqual(task.calls, 1)

    def test_navigation_only_task_uses_same_config_and_device(self):
        task = SimpleNamespace(config=object(), device=object())
        with patch('tasks.Component.GeneralBattle.general_battle.GeneralBattle') as battle:
            battle.return_value.run_general_battle.return_value = True
            # A mocked class cannot participate in isinstance; use a real stub type.
            class Adapter:
                def __init__(self, config, device):
                    battle(config, device)
                def run_general_battle(self):
                    return battle.return_value.run_general_battle()
            with patch('tasks.Component.GeneralBattle.general_battle.GeneralBattle', Adapter):
                self.assertTrue(handle_battle_page(task))
            battle.assert_called_once_with(task.config, task.device)
            battle.return_value.run_general_battle.assert_called_once_with()
