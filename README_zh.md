# Codex Limit Patch

[English](README.md) | [中文](README_zh.md)

跨平台本地查看器，用于查看 Codex 使用配额与重置库 (Reset Bank) 的状态。

默认情况下，它读取本地 Codex app-server 协议：

- `account/rateLimits/read`
- `rateLimitResetCredits`

这是一个轻量级的账户状态查询。它不会启动 Codex 线程或进行模型对话，也不会请求模型生成，因此不应消耗 ChatGPT/Codex 套餐 Tokens。它只读取由本地已认证的 Codex app-server 暴露的配额/重置库状态。与所有账户服务端点一样，如果 OpenAI 的服务端行为后续发生更改，以服务端为准。

该工具在设计上非常保守。如果当前的 Codex app-server 只返回一个重置总数，它就会显示总数，并提示由于服务端未提供因此无详情。它不会凭空捏造重置积分的来源、获取时间、过期时间或使用历史。

默认模式下不会读取 `~/.codex/auth.json`。

## 支持的平台

- Windows
- macOS

需要 Python 3.8+。无需任何第三方 Python 依赖包。

## 安装

你可以使用 `pip` 在本地进行安装：

```bash
pip install -e .
```

## 使用方法

如果通过 `pip` 安装，你可以在任何地方直接使用命令行工具：

```bash
codex_limit_patch --mode pill
codex_limit_patch --mode expanded
codex_limit_patch --mode json
```

或者，不安装而直接在该项目目录下作为源码模块运行：

```bash
python -m codex_limit_patch --mode pill
```

如果 `codex` 不在 `PATH` 中，请设置环境变量 `CODEX_BIN` 或传递 `--codex-bin` 参数：

```bash
CODEX_BIN=/path/to/codex codex_limit_patch --mode expanded
codex_limit_patch --codex-bin "C:\Path\To\codex.exe" --mode expanded
```

如果想把配额信息作为常驻贴片显示，可以启动 overlay：

```bash
codex_limit_patch_overlay --mode pill
codex_limit_patch_overlay --mode expanded --refresh-sec 60
```

overlay 会复用同一套本地 Codex app-server 数据读取、解析和文本渲染逻辑。macOS 上它会尝试贴近 Codex 窗口右上角；如果系统没有授予辅助功能权限，或找不到 Codex 窗口，则退回到屏幕右上角。也可以手动指定位置：

```bash
codex_limit_patch_overlay --geometry "+1200+20" --no-track-codex
```

overlay 支持拖动移动、双击立即刷新，按 `Esc` 或 `Ctrl-Q` 关闭。

## 多供应商使用量监控

原有 Codex 命令行与常驻贴片保持不变。项目新增了一套独立的数据面板，
将不同客户端和供应商的只读使用量统一展示；它不负责供应商配置，也不提供模型切换。

| 供应商 / 客户端 | 当前展示内容 | 数据来源 |
| --- | --- | --- |
| Codex | 套餐时间窗与 Reset Bank | 本地 Codex app-server |
| Claude Code | 请求数与 Token 总量 | 本地 JSONL 中的白名单字段 |
| DeepSeek | 人民币/美元余额、赠送与充值余额 | 官方余额 API |
| GLM / 小米 MiMo | 预留 Demo 行 | 后续再实现适配器 |

生成本机三源面板数据：

```bash
python3 -m codex_limit_patch.usage_monitor.three_source_demo
# 安装项目后也可以使用
ai_usage_monitor_demo
```

DeepSeek 为可选数据源。设置 `DEEPSEEK_API_KEY` 或 `DEEPSEEK_KEY` 后读取余额；
未设置时会明确显示为不可用，不会把示例值冒充实时数据。密钥只在进程内存中使用，
不会写入生成的 JavaScript 数据文件。

生成后打开 `demos/milestone-4/index-live.html`。仓库内的
`demos/milestone-4/index.html` 是不含凭据的示例页面，之前各里程碑 Demo
也会继续保留。

`pill` 模式是紧凑型的输出：

```text
Codex 5h 78% | Week 64% | Reset x2
```

如果重置库数据不可用：

```text
Codex 5h 78% | Week 64% | Reset ?
```

`expanded` (展开) 模式包含了重置库的具体信息：

```text
Codex 5h remaining: 78%
Codex 5h resets at: 2026-07-02 20:59
Weekly remaining: 64%
Weekly resets at: 2026-07-09 09:35

Reset Bank
Available: 2
Snapshot: 2026-07-02 14:25
Details: not provided by supported Codex app-server
Reset credit details not available from local safe sources.
```

当未来的 Codex 版本返回按次的积分详情时，兼容的解析器将展示如下格式：

```text
#1 Available | Referral
Granted: 2026-07-01 10:22
Expires: 2026-07-31 23:59
expires in 29d
```

## 数据源级别

### 级别 1：稳定的 app-server

这是默认数据源。该工具仅调用：

```text
account/rateLimits/read
```

它会显示：

- 5小时限额剩余量
- 周限额剩余量
- 5小时/周限额的 `resetsAt` (重置时间)
- `rateLimitResetCredits.availableCount`

如果 app-server 只返回了 `availableCount`，UI 将只显示 `Reset xN`，不会凭空捏造具体的积分明细。

### 级别 2：本地安全探测

如果 app-server 没有提供单次积分明细，该工具会执行一次本地的只读探测，并且不会读取 `auth.json` 里的 tokens。

允许扫描的目录：

- `~/.codex/sessions/`
- `~/.codex/archived_sessions/`
- `~/.codex/logs/` (如果存在)

它只搜索包含以下关键词的候选行：

- `granted_at`
- `grantedAt`
- `expires_at`
- `expiresAt`
- `rateLimitResetCredits`
- `rate-limit-reset-credits`
- `resetBank`
- `availableCount`
- `credits`

如果它清晰地找到了一个包含单次积分 `granted_at` / `expires_at` 或兼容的 camelCase 字段的 JSON 行，就会解析并显示这些详情。如果只找到了 `availableCount`，依然只显示 `Reset xN`。

如果没有找到明细行：

```text
Reset credit details not available from local safe sources.
```

### 级别 3：实验性的私有端点 (Private endpoint)

默认禁用。

只有当你显式地将以下两个设置均置为 `true` 时，该工具才会读取本地的 Codex 认证信息，并调用私有后端端点：

```json
{
  "resetBank": {
    "enablePrivateEndpoint": true,
    "privateEndpointWarningAccepted": true
  }
}
```

端点为：

```text
GET https://chatgpt.com/backend-api/wham/rate-limit-reset-credits
```

这种模式是实验性的且不受官方支持：

- 该端点不是稳定的 Codex app-server 接口
- 它随时可能变更或消失
- 它需要读取本地的 Codex/ChatGPT auth 数据
- 它仅在得到明确同意后才会读取 `~/.codex/auth.json`
- tokens 仅在本地内存中使用
- tokens、账户 ID、完整响应、cookies 以及 auth 标头绝不会写入日志中
- 不会向任何第三方上传数据

建议：等待官方的 app-server 支持返回详细的重置积分列表后，再将逐条积分明细作为正式功能依赖。

## 重置库 (Reset Bank) 行为

重置库展示当前可用的 Codex 赚取重置积分。

- 如果 Codex app-server 仅返回总数，该工具仅显示总数。
- 仅当 API 返回了匹配的字段时，才会显示获取时间与过期时间。
- 该工具不会去猜测重置积分的来源、获取时间或过期时间。
- 除非 API 返回了过期字段，否则该工具不会假定积分有效期为 30 天。
- 该工具不会自动消耗重置积分。
- 如果未来的 Codex app-server 响应包含了更丰富的明细，解析器的设计目标是在不改变 UI 契约的前提下直接展示它们。

## 解析的字段

对于重置总数，解析器接受兼容的字段，例如：

- `availableCount`
- `count`
- `balance`

对于详情数组，它会查找：

- `credits`
- `items`
- `entries`
- `resetBank`

获取时间的匹配优先级：

1. `acquiredAt`
2. `earnedAt`
3. `grantedAt`
4. `createdAt`
5. `issuedAt`
6. `awardedAt`
7. `receivedAt`

过期时间的匹配优先级：

1. `expiresAt`
2. `expirationAt`
3. `expireAt`
4. `validUntil`
5. `endsAt`
6. `deadlineAt`

支持的时间戳格式：

- Unix 秒级时间戳
- Unix 毫秒级时间戳
- ISO 字符串
- 类似 RFC3339 的字符串
- 任何 Python 能安全解析的类日期字符串

## 设置

可参考 `settings.example.json`：

```json
{
  "resetBank": {
    "showInPill": true,
    "showDetailsInExpanded": true,
    "warnExpireWithinHours": 72,
    "dangerExpireWithinHours": 24,
    "showUnknownDetails": true,
    "enablePrivateEndpoint": false,
    "privateEndpointWarningAccepted": false
  }
}
```

通过以下命令传入配置文件：

```bash
codex_limit_patch --settings settings.example.json
```

## Debug 日志

使用 `--debug-log` 来记录重置库响应结构的诊断信息：

```bash
codex_limit_patch --debug-log ./logs/reset-bank.log
```

Debug 日志会记录结构化特征，比如：重置库是否存在、是否仅存在 `availableCount`，以及详情条目数是否与后端的快照总数不一致。

它不会记录 tokens、auth 标头、API keys、账户 ids、cookies，也不会记录原始的响应 JSON。

## 测试

运行测试：

```bash
python -m unittest discover -s tests
```

解析器的测试用例覆盖了：

- 仅存在 `availableCount`
- `availableCount` 为 `0`
- 重置库数据缺失
- `credits` / `items` 详情数组
- Unix 秒级、毫秒级和 ISO 时间戳
- 获取时间字段优先级
- 将 `redeemed` / `consumed` 等状态映射到 `used`
- 基于过期时间判断是否 `expired` (已过期)
- 后端总数与明细总数不匹配的警告
- 在不崩溃的情况下处理完全未知的字段
- 本地安全探测发现详情
- 本地安全探测忽略仅有计数的记录
- 剩余百分比显示

## 限制

本项目默认使用本地 Codex app-server 的数据。它不是官方的计费账本。除非 API 显式提供了来源类字段，否则它无法证明重置积分的具体来源。

目前稳定的 app-server 接口并不保证会返回单次重置的 `granted` / `expires` 字段。工具仅当本地安全探测找到、或显式启用了实验性私有端点且该端点返回了这些字段时，才会显示它们。
