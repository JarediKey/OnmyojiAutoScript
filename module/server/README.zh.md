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
