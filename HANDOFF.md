# moqi 开发交接

本文件描述 **0.2.0 beta 2 当前实现**。最初设想见 `docs/specs/2026-10-23-moqi-design.md`；如两者冲突，以当前代码和 README 为准。

## 目标

让支持 MCP 的 AI 查询用户亲自确认过的词语、表情或语气含义。可选的 `research` 用 Brave Search API 查询公开短语的网页线索；默认不联网，不调用模型，也不主动观察聊天。宿主是否调用工具仍需实测。

## 代码位置

- `moqi/core/store.py`：按领域存储 JSONL、稳定 ID、跨进程锁、原子写入和数据完整性检查。
- `moqi/core/match.py`：确定性的 key 和文字描述匹配；单字 key 不嵌入长句匹配。
- `moqi/core/web_lookup.py`：可选的公开短语搜索；不读取个人记录，不自动确认出处。
- `moqi/cli.py`：本地命令行；`scan` / `recall` 只读。
- `moqi/mcp/server.py`：八个 MCP 工具。匹配分数与冲突状态会返回给模型；`forget` 仅用于用户明确要求删除记录。
- `tests/test_core.py`、`tests/mcp_smoke.py`：隔离数据目录的回归与 MCP 测试。

## 数据约定

默认 `~/.moqi/<domain>.jsonl`，`MOQI_HOME` 可覆盖。一行一个平面 JSON 对象；`key` 与 `truth` 保留用户原话。确认记录后，后续 `guess` 不覆盖 `truth`。新 ID 用 24 位 SHA-256 前缀，已有 4 位 ID 保留不迁移。修改数据必须在同领域锁内完成；损坏行不能在写入时悄悄丢弃。

`feedback` 仅表示用户**明确说出**的旧猜测评价：`right`、`partial`、`wrong`。没有明确评价时留空。旧文件的 `right`、`wrong`、`confidence` 和 `hits` 字段为兼容保留，不再用来推断猜测准确率。

## 发布前仍需验证

1. 在目标 Windows、macOS、Linux 客户端上安装 wheel 并连接 MCP，特别检查各宿主是否按提示主动调用 `scan`。
2. 用真实但经同意的数据做连续多轮使用测试，量化漏检、误检和打断频率；当前单元测试不能证明对话体验。
3. 发布公开仓库与包之前，确认名称、主页、支持渠道、版本号以及是否公开本地历史文件。每版同步 GitHub 的步骤见 `docs/releasing.md`。

本地开发测试：`python -m pytest -q`、`python tests/mcp_smoke.py`。核心保持零第三方依赖，不引入数据库或自动上传。
