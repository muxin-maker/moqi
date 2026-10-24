# moqi · 默契

moqi 让你培养一个真正懂你意思的 AI：记住你的幽默、黑话和表达习惯，在一次次交流与纠正中，越聊越有默契。

它把你确认过的含义存在本地，让支持 MCP 的 AI 下次遇到相同说法时先查，再回答。

**当前状态：0.2.0 beta 5，公开源码预发布版。** 源码在 [GitHub](https://github.com/muxin-maker/moqi)，尚未发布到 PyPI；可以直接从 GitHub 版本标签安装。
版本变化见 [更新记录](CHANGELOG.md)。

## 它怎样工作

1. AI 遇到不确定的说法，调用 `scan` 或 `recall` 查记录。
2. 没查到时，AI 可以说明自己的猜测，并用 `guess` 记录为**待确认**。
3. 你明确解释后，`correct` 把你的原话记为已确认含义。可选的 `feedback` 记录你对旧猜测的评价：`right`、`partial`、`wrong`。工具不会靠两句话是否完全一样来推断对错。
4. 再遇到相近文本，工具返回含义和匹配分数。弱匹配必须先确认语境，不能直接套用。

moqi 不会自动监听聊天。宿主 AI 必须实际调用工具；只写提示词不能保证每轮都调用。

### 可选的联网查梗

`research` 可以查公开短语的用例、原话和出处线索。它只发送你输入的短语与公开背景，返回网页标题、链接和摘要；**不会发送个人默契记录，也不会把网页结果写成已确认含义**。网页摘要不能证明谁最早说了这句话，需打开原视频或原帖核对。

联网搜索使用 [Brave Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get)，需要自行取得密钥，并注意该服务的额度与计费。Windows PowerShell 当前窗口配置示例：

```powershell
$env:MOQI_BRAVE_API_KEY = "你的密钥"
python -m moqi research "我了个雷" --topic "火影忍者手游"
```

将密钥放在运行 MCP 服务的客户端环境变量中，不要写进 Git 仓库。未配置密钥时，工具会提示宿主使用其已有的网页搜索能力。搜索仅在明确调用 `research` 时发生。

## 安装与五分钟试用

需要 Python 3.10+。先运行 `py -3 --version` 确认 Python 可用；若系统没有 `py` 命令，请用 `python --version` 检查，并在下方把 `py -3` 换成 `python`。两个命令都不可用时，先安装 Python。无需克隆仓库，先在自己选定的空目录创建虚拟环境，再从固定版本安装。Windows PowerShell：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "moqi[mcp] @ https://github.com/muxin-maker/moqi/archive/refs/tags/v0.2.0b5.zip"
.\.venv\Scripts\python.exe -m moqi doctor
```

macOS/Linux 使用 `python3 -m venv .venv` 创建环境，后续把 `.\.venv\Scripts\python.exe` 换成 `./.venv/bin/python`；前两行 PowerShell 编码设置只用于 Windows。只用命令行、不接 MCP 时，可以去掉包名中的 `[mcp]`。开发者克隆源码后可运行 `python -m pip install -e ".[dev,mcp]"`。

Windows 五分钟试用（以下操作会在默认数据目录创建演示记录；想隔离可先设置 `MOQI_HOME`）：

```powershell
.\.venv\Scripts\python.exe -m moqi scan "我了个雷"
.\.venv\Scripts\python.exe -m moqi guess slang "我了个雷" "表示惊讶" --signal "火影忍者手游圈的说法"
.\.venv\Scripts\python.exe -m moqi correct "我了个雷" "震惊吧" --feedback partial
.\.venv\Scripts\python.exe -m moqi scan "我了个雷"
.\.venv\Scripts\python.exe -m moqi stats
.\.venv\Scripts\python.exe -m moqi dump
```

`doctor` 是只读检查：显示版本、数据目录、记录数、MCP 是否可用以及数据文件错误，不会打印密钥或记录内容。`python -m moqi evaluate examples/evaluation_cases.jsonl` 可在源码目录运行公开示例评估；自备标注文件时也可用同一命令评估真实语境，格式见[评估说明](docs/evaluation.md)。

`correct` 的含义会按输入原样保存。没有得到明确评价时可省略 `--feedback`。`scan` 和 `recall` 只读，不会为了命中计数反复写盘。`dump` 只导出已确认记录。

确实要删除某条记录时，运行 `.\.venv\Scripts\python.exe -m moqi forget "我了个雷"`；不会接受模糊匹配。

仓库源码里的演示脚本使用隔离临时目录，不碰你的个人记录；直接安装的目录里没有这些脚本：

```bash
python examples/real_chat_demo.py
python examples/walkthrough.py
```

`real_chat_demo.py` 展示两天的自然聊天：第一次确认“我了个雷”的意思，第二天在对局聊天中召回，并检查相似字词不会误命中。它演示工具逻辑；真实聊天还需确认 MCP 客户端确实调用了这些工具。

### 每轮先查：给有前置钩子的宿主

宿主若有“收到用户消息、生成回答之前”的钩子，可每轮把**当前这条消息**送进标准输入，并读取 JSON：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
'我了个雷炸了' | .\.venv\Scripts\python.exe -m moqi scan --stdin --json
```

结果中的 `hits[].usable` 表示能否参考已确认含义；`false`、`conflicting=true` 或空结果都不能当成确定解释。钩子应把这个结果作为数据交给宿主，再由宿主判断当前语境。这样可以保证钩子每轮执行查询；仅靠 MCP 工具描述或提示词，无法保证宿主每轮主动调用。一次只传当前消息，避免把整段私人聊天发进命令行或第三方搜索。

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

可用工具：`scan`、`recall`、`research`、`guess`、`correct`、`forget`、`stats`、`dump`。`forget` 只接受完整 ID 或唯一的完整 key，宿主仅在用户明确要求删除时才应调用。推荐把 [调用说明](prompts/when-to-call.md) 加入宿主的自定义指令，并检查宿主实际支持 MCP 工具调用。

每次发布新版本，同步更新版本号与更新记录，测试通过后将对应提交和版本标签推送到 GitHub；步骤见 [发布流程](docs/releasing.md)。

## 匹配规则与边界

- 整条输入与 key 相等才是强匹配；key 或 signal 只出现在长句里时仅提供弱匹配线索，需结合语境确认。
- 单字 key（例如“哼”）只在整条输入就是该字时以 0.60 弱匹配命中，避免把“我哼了一首歌”当作语气记录。
- 整条输入是带问号或引号的短语时只给弱匹配；多个强匹配含义不同也要先确认。
- `signal` 使用字符二元组找相近描述。分数低于 `0.8` 是线索，不是确定答案；多个强匹配含义冲突时先问。
- 这不是语义模型，不懂图像本身，也不会自动识别梗的来源。图片需要宿主提供稳定的文件名或文字描述。改写、反讽和跨圈用法仍可能漏检或误检。

## 数据、安全与兼容

默认数据目录是 `~/.moqi/`，可用 `MOQI_HOME` 环境变量指定别处，例如自己已有的备份目录下的 `moqi/` 子目录，以便一起备份。它仍使用独立的 JSONL 格式，不会自动读取其他笔记或同步到云端。一个领域一个 UTF-8 `.jsonl` 文件，一行一条。写入使用同领域跨进程锁与原子替换；文件有损坏行时，查询与写入会明确报错并指出行号，保留原文件供你修复。
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

安装、接入或匹配有问题，可用 [GitHub Issues](https://github.com/muxin-maker/moqi/issues) 反馈；提交前请删掉私人记录和密钥。

准备公开发布时，请按 [对外发布验收](docs/release-readiness.md) 完成跨平台与真实宿主试用。
