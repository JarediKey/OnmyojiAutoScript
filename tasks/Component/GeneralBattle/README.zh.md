# 战斗等待选项

[English](README.md)

战斗等待使用源头的类型化运行状态：`battle_wait_strategy` 选择处理函数，
`battle_wait_options` 提供各事件的选项数据类。选项依次叠加类型默认值、装饰器
覆盖值、当前上下文覆盖值。覆盖以整个事件选项对象为单位；未填写字段使用其默认值，
包括奖励点击排除区域。嵌套上下文退出后恢复外层状态。装饰器调用结束或抛出异常时
恢复调用前的选项，避免临时设置泄漏到后续任务。原 `with_options()` 接口由
`with battle_wait_options(...)` 替代。

处理函数接收共享 `pub` 和各自的 `pri` 状态。任务所有者切换时重置任务状态，
每次通过装饰器调用战斗时重置单场状态。完成阶段只有在 `pub.per_battle.success`
为 `BattleResult.SUCCESS` 时返回 `True`；完成不等于胜利。失败处理先记录
`BattleResult.FAILURE`，再开启完成阶段。

回归检查：`python -m pytest tests/tasks/Component/GeneralBattle`。
这些是离线检查，不代表游戏实测。
