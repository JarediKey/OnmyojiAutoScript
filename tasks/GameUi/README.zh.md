# 页面导航

[English](README.md)

导航发现战斗或准备页面时，战斗处理优先使用当前任务的 `GeneralBattle` 实现。
仅导航的任务（如 GotoMain）使用相同配置和设备创建 `GeneralBattle`，先处理战斗
再继续导航，不再导入不存在的辅助函数。已有任务专用战斗等待逻辑保留。

回归检查：`python -m pytest tests/test_navigation_battle_hook.py`。

共用登录和战斗组件保留调用任务的身份。严格的任务名／路径校验适用于任务入口
`script_task.py`，不适用于 LoginHandler 等共用组件。任务可以从登录页面恢复，
不会因为登录组件位于另一任务目录而被拒绝。
