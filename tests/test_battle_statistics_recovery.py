"""Recover the observed statistics overlay without fabricating battle results."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import tasks.Component.GeneralBattle.battle_wait as module
from module.exception import GameStuckError
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets as Assets
from tasks.Component.GeneralBattle.battle_wait import (
    BattleWait, BattleResult, HookSignal, OptionSuccessDefault, PerBattleSuccess,
)


def method(name):
    """Exercise hook bodies independently of their process-wide runtime wrapper."""
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BattleWait')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    namespace = vars(module).copy()
    exec(compile(ast.Module(body=[node], type_ignores=[]), module.__file__, 'exec'), namespace)
    return namespace[name]


def test_normal_page_is_never_clicked():
    owner = SimpleNamespace(I_BATTLE_STATISTICS_PAGE=Assets.I_BATTLE_STATISTICS_PAGE,
                            appear=Mock(return_value=False), click=Mock(), screenshot=Mock())
    assert BattleWait.close_battle_statistics(owner) is False
    owner.click.assert_not_called()
    owner.screenshot.assert_not_called()


def test_activity_reward_sampling_also_keeps_statistics_excluded():
    rule = method('exclude_click_activity')(Assets)
    assert rule.strategy == 'rejection'
    assert rule.distribution == 'uniform'
    assert tuple(Assets.C_END_ACTIVITY_REWARD.roi_back) in rule._excluded
    for region in [Assets.C_END_STATISTICS_TOP_LEFT, Assets.C_END_STATISTICS_BOTTOM_LEFT,
                   Assets.C_END_SOUL_DETAILS]:
        assert tuple(region.roi_back) in rule._excluded


def test_statistics_exit_is_confirmed_without_changing_count():
    visible = [True]
    owner = SimpleNamespace(I_BATTLE_STATISTICS_PAGE=Assets.I_BATTLE_STATISTICS_PAGE,
        C_STATISTICS_CLOSE=Assets.C_STATISTICS_CLOSE, current_count=10,
        appear=lambda _: visible[0], screenshot=Mock())
    owner.click = Mock(side_effect=lambda _: visible.__setitem__(0, False))
    assert BattleWait.close_battle_statistics(owner) is True
    owner.click.assert_called_once_with(Assets.C_STATISTICS_CLOSE)
    owner.screenshot.assert_called_once()
    assert owner.current_count == 10


def test_unresponsive_statistics_page_has_three_attempts(monkeypatch):
    class Timer:
        def __init__(self, limit):
            self.calls = 0

        def start(self):
            return self

        def reached(self):
            self.calls += 1
            return self.calls > 2

    monkeypatch.setattr(module, 'Timer', Timer)
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    owner = SimpleNamespace(I_BATTLE_STATISTICS_PAGE=Assets.I_BATTLE_STATISTICS_PAGE,
        C_STATISTICS_CLOSE=Assets.C_STATISTICS_CLOSE, appear=lambda _: True,
        click=Mock(), screenshot=Mock())
    with pytest.raises(GameStuckError, match='three attempts'):
        BattleWait.close_battle_statistics(owner)
    assert owner.click.call_count == 3
    assert owner.screenshot.call_count == 6


def test_reward_overlay_is_closed_before_reward_completion(monkeypatch):
    frame = ['reward']
    events = []
    snapshots = [0]
    owner = SimpleNamespace(I_BATTLE_STATISTICS_PAGE='statistics',
        C_STATISTICS_CLOSE='close-statistics', screenshot=None,
        appear_then_click=lambda *args, **kwargs: False)
    for name in ['WIN', 'GREED_GHOST', 'REWARD', 'REWARD_GOLD', 'REWARD_GOLD_SNAKE_SKIN',
                 'UI_GOTIT_SMALL', 'END_FIX_1', 'END_FIX_2']:
        setattr(owner, 'I_' + name, name)

    def screenshot():
        snapshots[0] += 1
        if snapshots[0] == 1:
            frame[0] = 'statistics'

    def appear(target, **kwargs):
        return target == ('statistics' if frame[0] == 'statistics' else 'REWARD' if frame[0] == 'reward' else None)

    def click(target, **kwargs):
        events.append(target)
        frame[0] = 'reward' if target == 'close-statistics' else 'done'

    owner.screenshot = screenshot
    owner.appear = appear
    owner.click = click
    owner.close_battle_statistics = lambda: BattleWait.close_battle_statistics(owner)
    pub = SimpleNamespace(per_battle=SimpleNamespace(success=None))
    pri = SimpleNamespace(per_battle=PerBattleSuccess(click_stage_1='victory', click_stage_2='reward'),
                          options=OptionSuccessDefault())
    monkeypatch.setattr(module.random, 'random', lambda: 1)
    monkeypatch.setattr(module.runtime, 'hook_enabled_update', lambda **kwargs: HookSignal.CONTINUE)
    assert method('_bw_success_default')(owner, pub, pri) == HookSignal.CONTINUE
    assert events == ['close-statistics', 'reward']
    assert pub.per_battle.success == BattleResult.SUCCESS


def test_statistics_guard_runs_before_completion_hook(monkeypatch):
    visible = [True]
    events = []
    owner = SimpleNamespace(I_BATTLE_STATISTICS_PAGE=Assets.I_BATTLE_STATISTICS_PAGE,
        C_STATISTICS_CLOSE=Assets.C_STATISTICS_CLOSE, appear=lambda _: visible[0],
        screenshot=lambda: events.append('frame'), _bw_setup_default=lambda: None,
        setup=lambda: None, setup_hook=lambda **kwargs: None)

    def click(_):
        events.append('close-statistics')
        visible[0] = False

    def _bw_completion_default():
        assert not visible[0]
        events.append('completion')
        return HookSignal.DONE

    owner.click = click
    owner._bw_completion_default = _bw_completion_default
    owner.close_battle_statistics = lambda: BattleWait.close_battle_statistics(owner)
    plan = SimpleNamespace(function_setup_name='setup', sequence_function_names=lambda: ['_bw_completion_default'])
    monkeypatch.setattr(module.runtime, 'hook_enabled_update', lambda **kwargs: None)
    monkeypatch.setattr(module.runtime, 'hook_enabled', lambda: ('completion',))
    monkeypatch.setattr(module.runtime, 'pub_ctx', SimpleNamespace(per_battle=SimpleNamespace(success=BattleResult.SUCCESS)))
    assert method('battle_wait_with_strategy')(owner, battle_wait_plan=plan) is True
    assert events.index('close-statistics') < events.index('completion')
