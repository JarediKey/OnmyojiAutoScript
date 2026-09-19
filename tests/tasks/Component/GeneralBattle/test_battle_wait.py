import pytest

from tasks.Component.GeneralBattle.battle_wait import (
    BattleWait,
    BattleWaitPlan,
    HookSignal,
    runtime,
    battle_wait_options,
    battle_wait_strategy,
    BattleResult, PerTaskState, PerBattleState, OptionSuccessDefault,
    OptionCompletionDefault, OptionSetupDefault, OptionPrepareDefault,
)


@pytest.fixture(autouse=True)
def reset_battle_wait_plan(monkeypatch):
    monkeypatch.setattr(battle_wait_strategy, 'battle_wait_plan', None)
    monkeypatch.setattr(battle_wait_options, 'options', {})
    monkeypatch.setattr(battle_wait_options, '_context_overrides', {})
    runtime.task_owner = None
    runtime.pub_ctx = None
    runtime.pri_ctx = {}


def test_default_plan_contains_default_hooks_and_sequence():
    plan = BattleWaitPlan()

    assert all(getattr(plan, hook) == 'default' for hook in BattleWaitPlan.HOOKS_DEFAULT)
    assert plan.sequence.split('>') == [
        'completion', 'interrupt', 'prepare', 'preset', 'green', 'red', 'echo',
        'success', 'failure', 'idle']
    assert plan.function_setup_name == '_bw_setup_default'


def test_decorator_passes_its_plan_to_the_wrapped_function():
    strategy = battle_wait_strategy('reserve_default', 'idle_default', failure='custom')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    plan = battle_wait(object())

    assert plan.reserve == 'default'
    assert plan.idle == 'default'
    assert plan.failure == 'custom'


def test_with_context_uses_a_temporary_plan_and_restores_the_default_plan():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    default_plan = battle_wait_strategy.battle_wait_plan

    with battle_wait_strategy('success_default', failure='custom'):
        temporary_plan = battle_wait(object())
        assert temporary_plan.failure == 'custom'

    assert battle_wait_strategy.battle_wait_plan is default_plan
    assert battle_wait(object()) is default_plan


def test_event_and_strategy_can_be_configured_with_both_supported_forms():
    plan = BattleWaitPlan('yyy_default', abcd='edf')

    assert plan.yyy == 'default'
    assert plan.abcd == 'edf'
    assert plan.sequence_function_names()[-3:-1] == [
        '_bw_yyy_default',
        '_bw_abcd_edf',
    ]


def test_an_event_cannot_be_configured_with_two_strategies():
    with pytest.raises(ValueError, match="configured more than once"):
        BattleWaitPlan('success_default', success='custom')


def test_setup_runs_before_the_wait_loop():
    class OrderedBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            self.events.append('screenshot')
            runtime.hook_enabled_update(enable=('completion',), disable=())

        def _bw_setup_record(self, pub, pri):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_completion_finish(self, pub, pri):
            self.events.append('completion')
            pub.per_battle.success = BattleResult.SUCCESS
            return HookSignal.DONE

    battle_wait = OrderedBattleWait()
    plan = BattleWaitPlan('setup_record', 'completion_finish')

    assert battle_wait.battle_wait_with_strategy(battle_wait_plan=plan) is True
    assert battle_wait.events == ['setup', 'screenshot', 'completion']


def test_custom_hook_is_resolved_and_executed_in_the_configured_sequence():
    class CustomBattleWait(BattleWait):
        def __init__(self):
            self.events = []

        def screenshot(self):
            runtime.hook_enabled_update(enable=('completion',), disable=())

        def _bw_setup_record(self, pub, pri):
            self.events.append('setup')
            return HookSignal.DONE

        def _bw_yyy_record(self, pub, pri):
            self.events.append('yyy')
            return HookSignal.CONTINUE

        def _bw_completion_finish(self, pub, pri):
            self.events.append('completion')
            pub.per_battle.success = BattleResult.SUCCESS
            return HookSignal.DONE

    battle_wait = CustomBattleWait()
    plan = BattleWaitPlan(
        'setup_record',
        'yyy_record',
        'completion_finish',
        sequence='yyy > completion > interrupt > prepare > preset > green > red > echo > success > failure > idle',
    )

    assert battle_wait.battle_wait_with_strategy(battle_wait_plan=plan) is True
    assert battle_wait.events == ['setup', 'yyy', 'completion']


def test_custom_sequence_controls_hook_order():
    plan = BattleWaitPlan(
        'yyy_default',
        sequence='failure > yyy > completion > interrupt > prepare > preset > green > red > echo > success > idle',
    )

    assert plan.sequence_function_names() == [
        '_bw_failure_default',
        '_bw_yyy_default',
        '_bw_completion_default',
        '_bw_interrupt_default',
        '_bw_prepare_default',
        '_bw_preset_default',
        '_bw_green_default',
        '_bw_red_default',
        '_bw_echo_default',
        '_bw_success_default',
        '_bw_idle_default',
    ]


def test_custom_events_without_sequence_are_inserted_before_idle_in_argument_order():
    plan = BattleWaitPlan('yyy_default', 'abcd_edf')

    assert plan.sequence.endswith('success>failure>yyy>abcd>idle')


def test_dynamic_override_does_not_modify_the_default_plan():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    default_plan = battle_wait_strategy.battle_wait_plan

    overridden_plan = battle_wait(object(), random_click_swipt_enable=True)

    assert overridden_plan is not default_plan
    assert overridden_plan.randomclick == 'default'
    assert not hasattr(default_plan, 'randomclick')
    assert battle_wait_strategy.battle_wait_plan is default_plan


def test_dynamic_override_is_only_valid_for_the_current_call():
    strategy = battle_wait_strategy('success_default')

    @strategy
    def battle_wait(owner, *, battle_wait_plan, options=None):
        return battle_wait_plan

    battle_wait(object(), random_click_swipt_enable=True)
    plan_without_override = battle_wait(object(), random_click_swipt_enable=False)

    assert not hasattr(plan_without_override, 'randomclick')


# options 与 plan 同语义: 装饰器覆盖全局, with 临时覆盖并在退出时还原。
# 本测试锁定新拆分 API —— 策略装饰器只注入 plan, options 由 battle_wait_options
# 各自负责(装饰器=整份覆盖并跨调用还原, with=进入时 merge、退出还原)。

def test_context_overrides_decorator_and_restores_on_exception():
    original = battle_wait_options.options
    @battle_wait_options(success={'excludes_1': ['decorator']})
    @battle_wait_strategy()
    def call(owner, *, battle_wait_plan, options):
        return options

    assert call(object())['success'].excludes_1 == ['decorator']
    with battle_wait_options(success={'excludes_1': ['outer']}):
        outer = battle_wait_options.options
        assert call(object())['success'].excludes_1 == ['outer']
        assert battle_wait_options.options is outer
        with pytest.raises(RuntimeError):
            with battle_wait_options(success={'excludes_1': ['inner']}):
                assert call(object())['success'].excludes_1 == ['inner']
                raise RuntimeError('exit')
        assert call(object())['success'].excludes_1 == ['outer']
    assert battle_wait_options.options is original
    assert call(object())['success'].excludes_1 == ['decorator']
    assert call(object())['success'].excludes_2 == OptionSuccessDefault().excludes_2


def test_option_decorator_restores_call_time_state_on_failure():
    @battle_wait_options(prepare={'lock_team': True})
    def fail(owner):
        raise ValueError('test')
    with battle_wait_options(success={'excludes_1': ['active']}):
        previous = battle_wait_options.options
        with pytest.raises(ValueError):
            fail(object())
        assert battle_wait_options.options is previous


def test_cross_task_options_do_not_leak():
    @battle_wait_options(prepare={'lock_team': True})
    @battle_wait_strategy()
    def first(owner, *, battle_wait_plan, options):
        return options
    @battle_wait_options(preset={'preset_enable': True})
    @battle_wait_strategy()
    def second(owner, *, battle_wait_plan, options):
        return options
    assert first(object())['prepare'].lock_team
    assert not second(object())['prepare'].lock_team
    assert second(object())['preset'].preset_enable
    assert battle_wait_options.options == {}


def make_probe():
    class Probe(BattleWait):
        def _bw_setup_probe(self, pub, pri):
            return pub, pri
        def _bw_completion_probe(self, pub, pri):
            return pub, pri
    return Probe.__new__(Probe)


def test_runtime_injects_shared_public_and_separate_private_contexts():
    probe = make_probe()
    pub, first = probe._bw_setup_probe()
    other_pub, second = probe._bw_completion_probe()
    assert pub is other_pub is runtime.pub_ctx
    assert first is not second
    assert probe._bw_setup_probe.__name__ == '_bw_setup_probe'
    assert '_bw_setup_probe' in str(type(probe)._bw_setup_probe)


def test_runtime_resets_task_and_battle_state_at_their_boundaries():
    probe = make_probe()
    pub, pri = probe._bw_setup_probe()
    pub.cross['keep'] = 1
    pub.per_task.count = 4
    pri.per_task.marker = 2
    pub.per_battle.success = BattleResult.SUCCESS
    pri.per_battle.marker = 3
    runtime.reset_per_battle()
    assert pub.per_task.count == 4
    assert pri.per_task.marker == 2
    assert pub.per_battle == PerBattleState()
    assert not hasattr(pri.per_battle, 'marker')
    make_probe()._bw_setup_probe()
    assert pub.cross == {'keep': 1}
    assert pub.per_task == PerTaskState()
    assert not hasattr(pri.per_task, 'marker')


def test_runtime_distributes_typed_options_and_clears_previous_values():
    probe = make_probe()
    pub, pri = probe._bw_setup_probe()
    plan = BattleWaitPlan('setup_probe')
    option = OptionSetupDefault(excludes=['test'])
    runtime.update_options({'setup': option}, plan)
    assert pub.options['setup'] is option
    assert pri.options is option
    runtime.update_options(None, plan)
    assert pub.options == {}
    assert pri.options == OptionSetupDefault()


@pytest.mark.parametrize('outcome', [BattleResult.SUCCESS, BattleResult.FAILURE])
def test_completion_returns_recorded_outcome(outcome):
    class Probe(BattleWait):
        def screenshot(self):
            runtime.hook_enabled_update(enable=('completion',), disable=())
        def _bw_setup_probe(self, pub, pri):
            pub.per_battle.success = outcome
            return HookSignal.DONE
        def _bw_completion_probe(self, pub, pri):
            return HookSignal.DONE
    probe = Probe.__new__(Probe)
    assert probe.battle_wait_with_strategy(
        battle_wait_plan=BattleWaitPlan('setup_probe', 'completion_probe')
    ) is (outcome == BattleResult.SUCCESS)


def test_defeat_clears_success_before_enabling_completion():
    from unittest.mock import Mock
    probe = make_probe()
    pub, _ = probe._bw_setup_probe()
    pub.per_battle.success = BattleResult.SUCCESS
    probe.appear = Mock(return_value=True)
    probe.ui_click_until_disappear = Mock()
    probe._bw_failure_default()
    assert pub.per_battle.success == BattleResult.FAILURE
    assert 'completion' in pub.per_battle.hook_enabled
    probe.ui_click_until_disappear.assert_called_once_with(probe.I_FALSE)
