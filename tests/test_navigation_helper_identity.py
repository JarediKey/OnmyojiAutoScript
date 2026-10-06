"""Validate actual shared-helper initialization while keeping entry checks strict."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from module.exception import ScriptError
from tasks.Component.Costume.config import CostumeConfig
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.CollectiveMissions.script_task import ScriptTask
from tasks.GameUi.default_pages import handle_login_page, handle_battle_page
from tasks.Restart.login import LoginHandler


def config(name):
    return SimpleNamespace(model=SimpleNamespace(running_task=name),
                           global_game=SimpleNamespace(costume_config=CostumeConfig()),
                           restart=SimpleNamespace(login_character_config=SimpleNamespace(character='test')))


def test_collective_login_hook_constructs_real_login_helper():
    task = SimpleNamespace(config=config('CollectiveMissions'), device=object())
    with patch.object(LoginHandler, 'app_handle_login', return_value=True) as login:
        assert handle_login_page(task) is True
        login.assert_called_once_with()


def test_goto_main_battle_hook_constructs_real_battle_helper():
    task = SimpleNamespace(config=config('GotoMain'), device=object())
    with patch.object(GeneralBattle, 'run_general_battle', return_value=True) as battle:
        assert handle_battle_page(task) is True
        battle.assert_called_once_with()


def test_entry_script_still_rejects_wrong_scheduled_name():
    task = object.__new__(ScriptTask)
    task.config = config('Restart')
    with pytest.raises(ScriptError, match='Task name mismatch'):
        task.get_task_name()


def test_entry_script_accepts_correct_scheduled_name():
    task = object.__new__(ScriptTask)
    task.config = config('CollectiveMissions')
    assert task.get_task_name() == 'CollectiveMissions'
