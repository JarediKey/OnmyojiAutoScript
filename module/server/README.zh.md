# 系统时区 API

[English](README.md)

| 项目 | 约定 |
|---|---|
| 方法与路径 | `GET /home/system_timezone` |
| 含义 | OAS 所在机器的操作系统时区，不是调度进程或浏览器时区 |
| 请求参数 | 无 |
| 成功响应 | HTTP `200`，`{"timezone":"Asia/Shanghai"}` |
| 标识格式 | IANA 时区标识；Windows 配置通过 tzlocal 源自 CLDR 的映射转换 |
| 刷新 | 每次请求重新读取系统；成功和失败响应均带 `Cache-Control: no-store` |
| 读取失败 | HTTP `500`，错误码 `SYSTEM_TIMEZONE_READ_FAILED` |
| 映射失败 | HTTP `500`，错误码 `SYSTEM_TIMEZONE_MAPPING_FAILED` |
| 不支持的平台 | HTTP `501`，错误码 `SYSTEM_TIMEZONE_UNSUPPORTED_PLATFORM` |
| 写入 | 没有写入接口，不保存到账号配置 |

错误响应仅包含 `code` 和 `message`：

```json
{"code":"SYSTEM_TIMEZONE_READ_FAILED","message":"Unable to read system timezone."}
```

另两种消息分别为 `Unable to map system timezone to an IANA identifier.`
和 `System timezone detection is not supported on this platform.`。
前端按状态码和错误码判断，不依赖消息文本。不返回内部异常细节，检测失败不猜测时区。

检测器支持 Windows、Linux 和 macOS。每次请求启动一个短生命周期 Python 检测进程，
从其环境中移除 `TZ`，避免服务器强制时区及 tzlocal 缓存的影响，不修改服务器进程环境。
检测超时为五秒。系统配置必须提供时区名称，无名称的时区文件不一定能映射。
Windows→IANA 映射表示配置的时区，不代表用户实际地理位置。
操作系统的自定义时区规则可能没有对应的 IANA 时区。

依赖版本在 requirements 文件中固定。接口运行时不访问网络。
启动更新后的后端前须先安装依赖。

回归命令：`python -m pytest tests/test_system_timezone.py -q`
（仅测试需要 pytest 和 httpx）。测试覆盖 HTTP 响应、拒绝写入、多次读取、TZ 隔离及检测失败。
真实系统测试仅验证执行测试的操作系统，不修改系统时区。

## 工作进程终止错误

工作进程出现未处理异常或非零 `SystemExit` 时，会向父进程状态队列发布
`{"state":2}`（WARNING），包括任务执行范围之外的调度配置写入和初始化错误。
现有 WebSocket 状态广播程序更新缓存状态并向已订阅客户端发送警告。
仅有工作进程 PID 不等于运行状态事件。

启用通知时，工作进程边界会通过已配置的 OnePush 发送终止通知。它使用现有配置
文件锁读取通知设置，不构造配置模型，也不写配置。任务内已经通过
`Notifier.push_terminal` 成功发送的终止通知不会再次发送；任务内发送失败时，
边界再尝试一次。即使通知发送失败，也会发布 WARNING。

普通任务自动重试沿用原有通知行为。正常返回、零退出码和手动信号停止不产生
边界失败提醒。此机制捕获程序异常，不增加父进程的崩溃监视器。

OnePush 与 WebSocket 状态是两条独立通道。原生客户端本地通知还要求状态订阅
连通、应用通知已开启以及操作系统允许通知；单独的错误日志不等于 WARNING 事件。
