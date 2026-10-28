"""Exercise configured name normalization and prefixed wanted-quest text."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks.WantedQuests.script_task import ScriptTask


@pytest.mark.parametrize('text,expected', [
    (None, []), ('', []), ('，, ', []),
    ('荒川之主, 跳跳哥哥，', ['荒川之主', '跳跳哥哥']),
])
def test_unwanted_names_are_reset_and_empty_entries_never_match_every_monster(text, expected):
    task = object.__new__(ScriptTask)
    task.unwanted_boss_name_list = ['previous-setting']
    task.config = SimpleNamespace(model=SimpleNamespace(wanted_quests=SimpleNamespace(
        wanted_quests_config=SimpleNamespace(unwanted_boss_names=text),
        switch_soul_config=SimpleNamespace(enable=True))))
    task.goto_page = Mock(side_effect=InterruptedError('Stop before game navigation'))
    with pytest.raises(InterruptedError):
        task.run()
    assert task.unwanted_boss_name_list == expected


def test_configured_monster_is_excluded_even_with_an_action_prefix():
    task = object.__new__(ScriptTask)
    task.unwanted_boss_name_list = ['荒川之主']
    task.device = SimpleNamespace(image=None)
    task.screenshot = Mock()
    task.appear = Mock(return_value=True)
    task.O_WQ_MONSTER_TYPE = Mock()
    task.O_WQ_MONSTER_TYPE.detect_text.return_value = '需要击败荒川之主'
    task.ui_click = Mock()
    assert task.execute_mission(Mock(), 2, 10) is False
    task.ui_click.assert_called_once_with(task.I_TRACE_TRUE, task.I_TRACE_FALSE)
