# moqi · 默契

把你纠正过的词、表情和语气记下来，让支持 MCP 的 AI 在下次遇到相同信号时先查，再回答。

**当前状态：0.2.0 beta，本地试用版。** 源码尚未发布到 PyPI 或公开 GitHub 仓库。安装命令以本地源码目录为准。
版本变化见 [更新记录](CHANGELOG.md)。

## 它怎样工作

1. AI 遇到不确定的说法，调用 `scan` 或 `recall` 查记录。
2. 没查到时，AI 可以说明自己的猜测，并用 `guess` 记录为**待确认**。
3. 你明确解释后，`correct` 把你的原话记为已确认含义。可选的 `feedback` 记录你对旧猜测的评价：`right`、`partial`、`wrong`。工具不会靠两句话是否完全一样来推断对错。
4. 再遇到相近文本，工具返回含义和匹配分数。弱匹配必须先确认语境，不能直接套用。

moqi 不会自动监听聊天。宿主 AI 必须实际调用工具；只写提示词不能保证每轮都调用。

## 安装与五分钟试用

需要 Python 3.10+。先用 `python --version` 确认 Python 已安装，然后在本源码目录里创建虚拟环境：

```bash
python -m venv .venv
```

Windows 安装命令：`.\.venv\Scripts\python -m pip install -e ".[mcp]"`。
macOS/Linux 安装命令：`./.venv/bin/python -m pip install -e ".[mcp]"`。
下面示例中的 `python` 也请换成对应的虚拟环境 Python。

```bash
python -m moqi scan "我了个雷"
python -m moqi guess slang "我了个雷" "表示惊讶" --signal "火影忍者手游圈的说法"
python -m moqi correct "我了个雷" "震惊吧" --feedback partial
python -m moqi scan "我了个雷"
python -m moqi stats
python -m moqi dump
```

`correct` 的含义会按输入原样保存。没有得到明确评价时可省略 `--feedback`。`scan` 和 `recall` 只读，不会为了命中计数反复写盘。`dump` 只导出已确认记录。

确实要删除某条记录时，运行 `python -m moqi forget "我了个雷"`；不会接受模糊匹配。

演示脚本使用隔离临时目录，不碰你的个人记录：

```bash
python examples/walkthrough.py
```

## 接入 MCP 客户端

将下面配置中的 `<虚拟环境里的 Python 绝对路径>` 换成刚安装 moqi 的 Python 可执行文件。各客户端的配置位置不同，请按客户端文档放置这一段：
在 Windows 的 JSON 配置里，路径可写成 `C:/path/to/moqi/.venv/Scripts/python.exe`，避免反斜杠转义问题。

```json
{
  "mcpServers": {
    "moqi": {
      "command": "<虚拟环境里的 Python 绝对路径>",
      "args": ["-m", "moqi.mcp.server"]
    }
  }
}
```

可用工具：`scan`、`recall`、`guess`、`correct`、`forget`、`stats`、`dump`。`forget` 只接受完整 ID 或唯一的完整 key，宿主仅在用户明确要求删除时才应调用。推荐把 [调用说明](prompts/when-to-call.md) 加入宿主的自定义指令，并检查宿主实际支持 MCP 工具调用。

## 匹配规则与边界

- 整个 key 出现在文本里是强匹配；复合 key 的多字片段也可匹配。
- 单字 key（例如“哼”）只在整条输入就是该字时命中，避免把“我哼了一首歌”当作语气记录。
- `signal` 使用字符二元组找相近描述。分数低于 `0.8` 是线索，不是确定答案；多个强匹配含义冲突时先问。
- 这不是语义模型，不懂图像本身，也不会自动识别梗的来源。图片需要宿主提供稳定的文件名或文字描述。改写、反讽和跨圈用法仍可能漏检或误检。

## 数据、安全与兼容

默认数据目录是 `~/.moqi/`，可用 `MOQI_HOME` 环境变量指定别处。一个领域一个 UTF-8 `.jsonl` 文件，一行一条，方便查看、备份和迁移。写入使用同领域跨进程锁与原子替换；文件有损坏行时，读取会跳过，写入会拒绝覆盖并指出行号，保留原文件供你修复。
领域名和单条文本有长度限制，防止误把整段对话当作一条默契保存。

旧版 4 位 ID 的记录仍可按原 ID 或 key 找到。新记录使用更长的稳定 ID；不同 key 不会因为旧式短哈希碰撞而互相覆盖。遇到模糊 key 匹配多条记录时，`correct` 会要求完整 ID。

moqi 本身不会主动联网或上传数据。**但 MCP 查询结果会交给宿主 AI**；如果宿主使用云端模型，返回的记录可能进入云端会话。`dump` 生成的内容也由使用者决定发送到哪里。请只记录愿意提供给所用模型的内容，并自行备份个人数据。当前没有账号、跨设备同步或自动提炼。

## 开发验证

```bash
python -m pip install -e ".[dev,mcp]"
python -m pytest -q
python tests/mcp_smoke.py
```

核心逻辑仅用 Python 标准库；MCP SDK 是可选依赖。项目协议为 [MIT](LICENSE)。

准备公开发布时，请按 [对外发布验收](docs/release-readiness.md) 完成跨平台与真实宿主试用。
