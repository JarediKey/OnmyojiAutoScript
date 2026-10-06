# dev 到 prod 的自动同步

[English](prod-sync.md)

`Sync Upstream Branches` 位于默认分支 `master`，每天 04:17 UTC（北京时间
12:17）执行，也支持手动触发。GitHub 可能延迟定时任务的实际开始时间。
工作流先将 `runhey/dev` 完整镜像到 `origin/dev`，随后尝试普通合并到
`origin/prod`。`master` 独立合并 `runhey/master`，失败不会取消 prod 流程。
这个工作流不部署 Ebony，也不重启账号进程。

## 执行与发布

1. GitHub 托管的准备任务固定 prod/dev 的提交。dev 已被包含时直接结束，
   不调用 AI、不发布。没有未合并文件的 Git 错误直接失败，不触发 AI。
2. 真正发生合并冲突时，将任务派给标签为 `oas-codex-subscription` 的本地
   Runner。它使用已有 ChatGPT 登录执行 `codex exec`，忽略用户的提供商配置，
   强制使用 ChatGPT/OpenAI 认证，并从 Codex 环境移除 API Key 和 GitHub 令牌。
   仍受订阅限额约束；登录失效或额度不足会失败，不自动切换 API Key。
   不需要保持桌面应用窗口打开。
3. AI 只能修改冲突文件及对应的任务生成资源，不能发布。控制脚本检查修改范围、
   索引、Python/JSON、冲突标记、手写代码空白错误和合并身份，然后生成 Git bundle。
   上游资源生成器产生的空白格式会报告，但不会阻止发布。
4. 全新的 GitHub 托管 Windows 任务验证 bundle 并运行离线回归测试。另一个具有
   写权限的任务再次核对远程分支、作者/提交者和父提交，之后普通推送。
   并发改动导致发布失败，不会强推；下一次同步重新准备候选版本。
   离线检查不能证明所有游戏状态或 Ebony 独有补丁都正常。

## Runner 运行

在获准的 Mac 账号下使用 GitHub 官方 Actions Runner。将
`.github/scripts/runner-guard.sh` 安装到检出目录和 Runner 程序目录之外，并将
`ACTIONS_RUNNER_HOOK_JOB_STARTED` 指向其绝对路径。检查脚本只接受本仓库
`master` 上的 `sync-upstream.yml`、定时/手动事件，以及 `resolve_conflict`
或 `runner_smoke` 任务。不要在此 Runner 上启用外部 fork/PR 执行。
个人自托管 Runner 属于受信任机器，不是任意仓库代码的隔离沙箱；管理员须保护
工作流修改权限。

在 Runner 的 `.env` 文件中配置以下本机变量：

- `OAS_CODEX_BIN`：获准 Codex CLI 的绝对路径。
- `OAS_PYTHON_BIN`：Python 3.10 或更新版本的绝对路径。
- `OAS_AUTOMATION_STATE`：存放尝试记录和日志的本机私有目录。
- `ACTIONS_RUNNER_HOOK_JOB_STARTED`：已安装检查脚本的绝对路径。

用相同系统用户执行 `codex login`，通过 `codex login status` 确认 ChatGPT 登录。
凭据保留在本机。在仓库 Settings → Actions → Runners 使用 GitHub 短期注册令牌
注册 Runner；令牌、`.credentials`、`.runner`、Codex 日志和登录文件都不得提交。
通过 GitHub 的 `svc.sh` 安装、启动当前 Mac 用户的后台服务。Mac 需要联网且不休眠。
离线期间 GitHub 排队，超过 24 小时未执行会失败；下一次定时或手动同步可以重新
尝试尚未开始的任务。

## 控制与诊断

- 手动选择 `mode=sync`：执行正常同步链路。
- 手动选择 `mode=ai-smoke`：派发隔离仓库中的真实冲突，让本地 Codex 处理并
  验证两边设置均被保留，同时验证当前 prod 的 Windows 回归环境。
  不执行分支同步，也不发布。
- AI 子进程最多运行 15 分钟，其任务最多 20 分钟。每组固定 prod/dev 提交在 Mac
  记录一次 AI 尝试。后续复用成功的 bundle，或者直接失败，不重复调用 AI。
  排查失败原因后，如需有意重试，可手动触发并设置 `retry_ai=true`。
- Codex 原始输出仅保留在本机状态目录；只上传候选 bundle，保留七天。
  Actions 日志和工作流摘要显示状态及提交。失败通知沿用你的 GitHub 工作流通知
  偏好，没有额外添加邮件或桌面通知服务。
- `svc.sh stop` 停止 Runner。禁用此工作流会停止它的定时分支更新。
  失败时既有 prod 和 Ebony 进程保持不变。

## 验证

执行 `python .github/scripts/test_prod_sync.py`，使用隔离的真实 Git 仓库验证无变化、
正常合并、冲突、Git 错误、脏目录/过期候选、无效修复、bundle 历史/身份和 Runner
准入条件。使用手动冒烟模式验证 GitHub → Mac → 订阅 Codex 以及 Windows 回归环境。

参考：[GitHub Runner](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)、
[Runner 钩子](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts)、
[Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)、
[Codex 认证](https://learn.chatgpt.com/docs/auth)。
