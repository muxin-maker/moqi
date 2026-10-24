# 更新记录

## 0.2.0 beta

- 新记录改用 24 位稳定 ID；已有 4 位 ID 保持可读写，按 key 更新不会改动旧 ID。
- 同领域写入使用跨进程锁；损坏或重复的 JSONL 行会阻止写入，原文件保留。
- `scan` / `recall` 改为只读；单字不再嵌入长句命中，匹配分数和冲突状态返回给 MCP 宿主。
- `correct` 支持用户明确给出的 `right`、`partial`、`wrong` 反馈；不再把字面不同自动算错。旧 `confidence`、`hits`、`right`、`wrong` 字段保留在已有记录中，但不再参与决策。
- 新增只按完整 ID 或完整 key 删除记录的 `forget`；`dump` 只导出已确认记录，并标明领域。
- 更新本地安装说明、MCP 提示词、回归测试和跨平台 CI 配置。

这是预发布版本。公开发布前的验收要求见 [对外发布验收](docs/release-readiness.md)。
