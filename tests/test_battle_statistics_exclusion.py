"""Validate statistics exclusions across post-battle click phases and samplers."""

import pytest

from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBattle.battle_wait import (
    OptionSuccessDefault, PerBattleSuccess,
)


PROTECTED = [(44, 32, 72, 72), (383, 559, 52, 49)]


def intersects(first, second):
    x, y, w, h = first
    a, b, c, d = second
    return x < a + c and a < x + w and y < b + d and b < y + h


@pytest.mark.parametrize('areas', [
    None, [], ['C_END_MESSAGE_RIGHT_TOP'],
    OptionSuccessDefault().excludes_1, OptionSuccessDefault().excludes_2,
])
def test_all_post_battle_allowed_rectangles_avoid_both_statistics_buttons(areas):
    rule = PerBattleSuccess.reward_exclude_click(GeneralBattleAssets, areas)
    for allowed in rule._allowed:
        assert not any(intersects(allowed, blocked) for blocked in PROTECTED)
    assert rule._allowed


@pytest.mark.parametrize('strategy', ['rejection', 'complement'])
@pytest.mark.parametrize('distribution', ['normal', 'uniform'])
def test_all_sampling_modes_avoid_statistics_regions(strategy, distribution):
    rule = PerBattleSuccess.reward_exclude_click(GeneralBattleAssets, [])
    rule.strategy = strategy
    rule.distribution = distribution
    for _ in range(1000):
        x, y = rule.coord()
        assert not any(a <= x < a + w and b <= y < b + h for a, b, w, h in PROTECTED)


def test_custom_exclusions_still_apply_and_unknown_names_fail():
    rule = PerBattleSuccess.reward_exclude_click(GeneralBattleAssets, ['C_END_1_1'])
    assert tuple(GeneralBattleAssets.C_END_1_1.roi_back) in rule._excluded
    with pytest.raises(ValueError, match='Unknown success exclusion'):
        PerBattleSuccess.reward_exclude_click(GeneralBattleAssets, ['MISSING'])
