"""Replay UI landmarks and ensure overlays cannot cause underlying repeated input."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from tasks.Component.Costume.assets import CostumeAssets
from tasks.Duel.assets import DuelAssets
from tasks.Duel.script_task import ScriptTask as DuelTask
from tasks.GameUi.assets import GameUiAssets
from tasks.WeeklyTrifles.assets import WeeklyTriflesAssets
from tasks.WantedQuests.script_task import ScriptTask as WantedTask


FIXTURES = Path(__file__).parent / 'fixtures/runtime_ui'


def frame(name, xy):
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    crop = cv2.cvtColor(cv2.imread(str(FIXTURES / name)), cv2.COLOR_BGR2RGB)
    x, y = xy
    h, w = crop.shape[:2]
    image[y:y+h, x:x+w] = crop
    return image


@pytest.mark.parametrize('rule,name,xy', [
    (DuelAssets.I_D_ENTRY_REWARD, 'duel_gift.png', (715, 480)),
    (CostumeAssets.I_MAIN_GOTO_TOWN_4, 'courtyard.png', (150, 190)),
    (CostumeAssets.I_MAIN_GOTO_EXPLORATION_4, 'courtyard.png', (150, 190)),
    (GameUiAssets.I_CHECK_MALL, 'mall_footer.png', (0, 630)),
])
def test_actual_incident_landmark_matches_without_lowering_threshold(rule, name, xy):
    assert rule.threshold == .8
    assert rule.match(frame(name, xy))
    for other, origin in [('duel_gift.png', (715,480)), ('courtyard.png', (150,190)),
                          ('mall_footer.png', (0,630))]:
        if other != name:
            assert not rule.match(frame(other, origin))


def test_duel_reuses_existing_acknowledgement_bitmap():
    assert Path(DuelAssets.I_D_ENTRY_REWARD.file).resolve() == Path(
        WeeklyTriflesAssets.I_WT_HAPPY_GET.file).resolve()


@pytest.mark.parametrize('battle', [DuelAssets.I_D_BATTLE, DuelAssets.I_D_BATTLE2,
                                   DuelAssets.I_D_BATTLE_PROTECT])
def test_matching_rechecks_overlay_after_each_start_click(battle):
    task = object.__new__(DuelTask)
    states = iter(['gift', 'main', 'gift', 'prepare'])
    state = ['']
    task.screenshot = lambda: state.__setitem__(0, next(states))
    task.appear = lambda rule, **kwargs: rule is task.I_D_ENTRY_REWARD and state[0] == 'gift'
    clicks = []

    def click(rule, **kwargs):
        if task.appear(rule) or (state[0] == 'main' and rule is battle):
            clicks.append((state[0], rule))
            return True
        return False

    task.appear_then_click = click
    task.is_in_battle_prepare = lambda: state[0] == 'prepare'
    task.is_in_real_battle = lambda: False
    task.is_battle_end = lambda: False
    task.enter_battle()
    assert clicks == [('gift', task.I_D_ENTRY_REWARD), ('main', battle),
                      ('gift', task.I_D_ENTRY_REWARD)]


def test_visible_duel_gift_blocks_underlying_input_during_click_cooldown():
    task = object.__new__(DuelTask)
    task.appear = lambda rule, **kwargs: rule is task.I_D_ENTRY_REWARD
    task.appear_then_click = Mock(return_value=False)
    assert task.check_and_get_reward() is True
    task.appear_then_click.assert_called_once_with(task.I_D_ENTRY_REWARD, interval=1)


def test_open_mysterious_detail_without_trace_button_closes_instead_of_reclicking_list():
    task = object.__new__(WantedTask)
    task.screenshot = Mock()
    task.appear = lambda rule, **kwargs: rule is task.I_WQ_TRACE_ONE_CHECK_OPENED
    task.click = Mock(side_effect=AssertionError('Already opened; do not click the list'))
    task.ui_click_until_smt_disappear = Mock()
    assert task.execute_mission(Mock(), 10, 130) is False
    task.ui_click_until_smt_disappear.assert_called_once_with(
        task.I_UI_BACK_RED, stop=task.I_WQ_TRACE_ONE_CHECK_OPENED, interval=1.5)


def wanted_row(text, y):
    return SimpleNamespace(ocr_text=text,
                           box=np.array([[20,y], [65,y], [65,y+18], [20,y+18]]))


@pytest.mark.parametrize('marker', ['?', '？'])
def test_unknown_counter_is_skipped_but_later_known_quest_remains_actionable(marker):
    task = object.__new__(WantedTask)
    task.O_WQ_TEXT_ALL = SimpleNamespace(
        roi=(12,119,88,393), detect_and_ocr=lambda image: [
            wanted_row(marker, 146), wanted_row('0/10', 188),
            wanted_row('悬赏封印', 220), wanted_row('2/12', 330)])
    current, remaining, total, area = task.find_wq(None)
    assert (current, remaining, total) == (2, 1, 12)
    assert area[1] == 449


def test_unknown_only_list_is_not_reported_as_completed():
    task = object.__new__(WantedTask)
    task.O_WQ_TEXT_ALL = SimpleNamespace(
        roi=(12,119,88,393), detect_and_ocr=lambda image: [
            wanted_row('？', 146), wanted_row('0/10', 188)])
    assert task.find_wq(None)[:3] == (-1, -1, -1)
