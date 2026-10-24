# moqi — design spec

> 历史设计稿（v1）。当前实现与使用说明以仓库根目录的 `README.md` 和代码为准；本文件保留当时的设计背景。

- 日期：2026-10-23
- 状态：已批准（老大："建吧，做完文档直接建项目"）
- 来源：早期项目讨论记录

## 一句话

**moqi 是一份「你和你的 AI 之间的默契笔记」**：某一个表情、某一个词、某一种语气，在这个人嘴里到底是什么意思。

## 为什么需要它

模型看不懂人的引申义，不是理解力不够，是**没有记忆**。

同一张「哼」，在这个人这里是撒娇，在那个人那里是不服气；同一个「神鲸」，在别人那里是骂人，在这里是夸。模型每次都在凭字面重新猜，猜完不落盘，下次还猜错。

**所以真正的价值不在「理解」而在此**：

```
我猜 → 说出来 → 他说不对 → 纠正落盘 → 下次先查
```

变好的不是模型的悟性，是**同一个错只犯一次**这条回路。

## 为什么不做成「表情包理解插件」

那会把一个通用问题压窄成图库工具，和现成的 emoji 词典撞车。

moqi 记录的是**这个人跟这个 AI 之间**的约定，领域是开放的：表情、黑话、缩写、语气、称呼禁忌、什么时候该闭嘴。目录下一个 `*.jsonl` 就是一个领域，用的人自己加。

## 交付形态（三件套）

| 件 | 给谁 | 说明 |
| --- | --- | --- |
| `moqi/core` | 所有 | 纯标准库逻辑：存取、匹配、信心。零第三方依赖 |
| `moqi/mcp` | 支持 MCP 的客户端 | Claude Desktop / Cursor / Cline 等直接接 |
| `prompts/*.md` | 接不了 MCP 的 | 一段提示词 + `dump` 导出的 markdown 摘要，贴进去就能用 |

## 数据模型

一条记录 = 一次「我以为 X，实际是 Y」的校准。

```json
{"id":"faces-3f2a","domain":"faces","key":"哼_白发少女","signal":"白发少女闭眼哼气",
 "guess":"不服气但认了","truth":"撒娇","hits":3,"right":1,"wrong":1,
 "confidence":0.0,"created":"2026-10-23T12:14:00+08:00","corrected_at":"2026-10-23T12:20:00+08:00"}
```

字段说明：

- `id` — `<domain>-<4位hash>`，从 `key` 派生，同一个 key 不会产生两条
- `domain` — 自由字符串，对应 `$MOQI_HOME/<domain>.jsonl`
- `key` — 这个信号的稳定标识（图片名、词、短语）
- `signal` — 人可读的描述，给检索和 dump 用
- `guess` / `truth` — 我猜的 / 实际的意思。`truth` 为空 = 还没闭环
- `hits` — 被查询命中过几次
- `right` / `wrong` — 猜对 / 猜错的次数
- `confidence` — 见下

**confidence 是全项目唯一一条学习规则**：

- 猜对一次 `+0.25`，上限 1.0
- 猜错一次**直接归零**（错一次比三次对更值得记）
- `>= 0.75` 表示可以少问；归零的永远先查

不写更复杂的，写完也解释不清。

## 存储

- 默认 `~/.moqi/`，环境变量 `MOQI_HOME` 覆盖
- 一个领域一个 `.jsonl`，一行一条，UTF-8，不重建、不清空
- 写用「读全量 → 改内存 → 原子覆盖（临时文件 + os.replace）」，天然不会有半行
- 不做数据库。JSONL 能 git diff、能手改、能整份发给别人，这是它比 sqlite 值得开源的地方

## 工具（MCP 六个）

| 工具 | 参数 | 返回 | 用途 |
| --- | --- | --- | --- |
| `scan` | `text: str` | `{hits, open_guesses}` | **核心**。嗅探这段话里可能被我理解错的地方，同时报出还悬着的旧猜测 |
| `recall` | `context: str, domain?: str, limit?: int` | `{matches}` | 按上下文查相关条目 |
| `guess` | `domain, key, guess, signal?` | `{id, existed}` | 记下猜测 |
| `correct` | `id: str, truth: str` | `{ok, entry}` | 回填真意，同时更新 confidence |
| `stats` | `domain?: str` | `{total, closed, open, right, wrong, worst}` | 给人看的 |
| `dump` | `domain?: str` | `{markdown}` | 导出给没有 MCP 的模型 |

`scan` 的匹配规则（v1，故意简单）：

1. 文本里**包含**某条的 `key`（或 key 去掉下划线后的各段）→ 命中
2. `signal` 与文本的字符二元组重合度 ≥ 0.35 → 命中
3. `truth` 为空的旧猜测，只要 domain 沾边就一直带出来（最多 5 条），提醒模型「这条还没闭环」
4. 结果按 confidence 升序（最没把握的排前面）

不做向量、不调模型、不联网。v1 只要快和可预测。

## 提示词模板

中文版全文（`prompts/zh.md`）：

> 你有 `moqi` 工具，记录的是**这个人跟你的默契**：他某个表情、某个词、某种语气，真正的意思是什么。
>
> 三个必须调用的时机：
> 1. 看到图片、表情、梗图 → 先 `scan` 或 `recall`
> 2. 遇到他不解释的短词、缩写、圈内话 → 先 `recall`
> 3. 你**猜**了他的意思并且说出口之后 → `guess` 一条
>
> 他纠正你的时候，无条件 `correct`，别争。
>
> 库里没有的，**先问再猜**；猜了就要 `guess`，别只在脑子里过一遍。
>
> 一次只问一句。问的时候把选项给出来，别问"你是什么意思"。

英文版同义，见 `prompts/en.md`。

## 目录结构

```
moqi/
  moqi/__init__.py
  moqi/core/store.py         JSONL 存取、原子写、id 生成
  moqi/core/match.py         关键词与二元组匹配
  moqi/core/confidence.py    信心规则
  moqi/mcp/server.py         MCP 适配器（唯一需要 sdk 的地方）
  moqi/cli.py                命令行（没有 MCP 也能用）
  prompts/zh.md  prompts/en.md
  examples/faces.jsonl  examples/slang.jsonl
  tests/test_store.py  test_match.py  test_confidence.py
  README.md  LICENSE  pyproject.toml  .gitignore
```

`core` **零第三方依赖**是硬要求：开源项目装不上就没人用。

## v1 范围

**做**：六个工具、关键词匹配、confidence 规则、中英提示词、CLI、5 分钟上手 README、MIT。

**不做**：向量检索、多用户、云同步、Web 界面、聊天记录导入、自动发现「模型理解错了」（没有这种能力，别假装有）。

## 怎么算做对了

一句验收：

> **装上以后，同一个理解错误，不会出现第二次。**

对应测试：同一张图猜错一次 → `correct` → 下次 `scan` 必须命中，并且带回的是正确答案，且 confidence 已归零。

## 风险

| 风险 | 应对 |
| --- | --- |
| 模型不主动调工具 | 靠提示词写死三个时机，不靠自觉；`scan` 的成本低到可以每次都调 |
| 库里空着时就没人用 | 明确接受：从零开始，靠纠正慢慢攒。README 用「第一次纠正」当第一个例子 |
| 关键词匹配漏掉变体 | v1 接受。signal 二元组匹配已经能兜住大部分改写；真漏了再加规则，不上向量 |
| 隐私 | 数据全在本地，一个文件，用户可以直接看、直接删。不联网、不上报 |
