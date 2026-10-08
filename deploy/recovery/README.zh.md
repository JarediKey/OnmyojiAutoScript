# 终止通知恢复

[English](README.md)

独立控制器使用 OAS 已有的通知、配置、WebSocket 和维护接口。OAS 必须包含
`8d080403` 引入的配置启动等待锁。它不检测没有通知的工作进程崩溃。

## 行为

- 在带令牌的本机回环地址接收 OnePush Custom JSON POST，先持久化终止事件，
  立即返回 HTTP 200，再异步恢复。
- 只处理 `RequestHumanTakeover`、`ScriptError`、未处理异常及连续三次失败。
  普通自动重试、空闲、无通知退出及手动停止不触发恢复。
- 合并同一配置的未结束事件。一小时内再次终止时转入私有 AI 队列，避免立即反复重启。
- 最多三次检查 Android shell、启动状态和可解码的 1280×720 ADB 截图，每次间隔
  五秒；命令有超时，并允许一次针对该连接的重连。有通道正常就不能认定模拟器卡死。
  启动 OAS 配置前还要验证实际配置的 ADB 或 Nemu IPC 截图通道。
- 可使用经人工核实的私有引擎更新弹窗模板，仅在相关度达到 0.985 时点击“暂不更新”，
  并验证弹窗消失。没有模板就不自动点击。恢复期间持续检查该弹窗，因为游戏重启会再次弹出。
- 两个 Android 通道持续失败时，只重启已核实身份的 MuMu 实例。先使用管理器关闭，
  必要时只结束可执行路径和 `--vm` 标识均匹配的该实例进程。禁止结束全局 ADB、
  MuMu 公共服务或其他模拟器。确认 Android 启动、ADB 截图及配置截图正常后才恢复配置。
  期间同模拟器内仍存活的配置保持在已确认的调度等待锁内，无法操作模拟器。
- 共用模拟器恢复时不打断健康配置的正在执行任务。失败配置的逾期任务按配置分组，
  每组间隔至少 30 分钟，同配置的待办放在同一批；只顺延随后冲突的批次。
  修改前备份，仅修改 `next_run`，逐项读回校验。实际运行锁防止超时批次与下一批重叠。
  已完成任务和周期规则保留；已过活动时段的任务仍按原任务规则延期。
- 尊重外部重启替换的工作进程。仅有 PID 不代表恢复完成，必须回到调度等待状态。

## 私有 AI 消费程序

Mac 每分钟经 SSH 查询私有事件队列，只有需要处理的事件才调用 `codex exec`。
使用已有 ChatGPT 登录，清除 API key 环境覆盖。每个事件执行一次结构化只读分析；
模型可请求一次受控制器约束的重试，或转人工处理。模型不能任意杀进程，也不会静默
修改、发布源码。目前源码缺陷需要人工审核。只有未解决事件才弹出本机桌面通知。
日志、分析结果、通知令牌和配置备份均留在私有目录，不进入 GitHub。
Mac 必须开机且能通过 SSH 连接 Ebony；离线期间 AI 事件留在队列中等待，本机确定性恢复仍可运行。

## 运行目录

Python 文件安装在私有 `recovery/code/`，旁边放 `settings.json`。Windows 设置包括
`root`、`private`、`deployment_lock`、`oas_port`、`port` 和随机生成的 `token`。
用 OAS 的 Python 在已登录的桌面会话运行 `service.py --settings <路径>`。
使用登录触发的计划任务，并分别重定向 stdout/stderr；不能让 PowerShell 把 Python
普通日志当成致命错误而终止进程。

各配置设置 `script.error.notify_enable=true`，`notify_config` 为：

```yaml
provider: custom
url: http://127.0.0.1:22389/notify/REPLACE_WITH_PRIVATE_TOKEN
method: post
data: {}
```

替换前备份原通知设置，先用非终止测试消息验证实际安装的 OnePush。
`/health` 仅用于读取状态。历史故障只能由操作员明确导入；启动时不会因为缺少进程
就扫描并重启配置。

Mac 设置包括 `host`、`user`、`ssh_key`、`hostkey_alias`、`private` 和 `codex`。
launchd 每分钟运行 `codex_worker.py --settings <路径>`。`incidentctl.py` 只提供
固定的私有 SSH 操作，不导出账号配置。中断的操作先进入诊断，不盲目重放。

控制器以私有固定副本安装，与 OAS 代码激活分开。替换前检查当前恢复批次，保留
SQLite 队列、设置和备份。停止 Windows 计划任务可禁用自动恢复；停用 Mac launchd
任务可禁用 AI 消费。OAS 本身的自动重试继续工作。

## 验证

运行 `python -m unittest discover -s deploy/recovery -p 'test_*.py' -v`，以及维护锁、
维护接口和安全更新测试。可私下回放经确认的弹窗正样本和庭院负样本。
不要为测试强制重启流程而重启健康的生产模拟器；需要在受监督的故障或隔离模拟器上
验证真实重启和启动过程，才能宣称该路径已通过实机验证。
