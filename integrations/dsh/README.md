# DeepSeek Harness 桌面端接入

需要 DeepSeek Harness 支持 profile bundle 和 `agent/pre-step` 钩子，并有 Node.js 20+、Python 3.10+。插件会在每次回复前调用本地 `moqi scan --stdin --json`；模型收到命中的已确认含义及 `usable` 标记。弱匹配不能直接当作确定含义。

## 安装

先按照仓库根目录的 README，在一个虚拟环境里安装 moqi，运行 `python -m moqi doctor` 确认成功。然后把本目录作为本地依赖加入目标 DSH profile 的 `package.json`：

```json
{
  "dependencies": {
    "moqi-dsh": "link:/absolute/path/to/moqi/integrations/dsh"
  },
  "dsh": {
    "profile": {
      "bundles": ["moqi-dsh"]
    }
  }
}
```

这只是需并入现有 `package.json` 的字段，不要覆盖原有依赖和 bundles。运行该 profile 所用的包管理器安装依赖。插件包自带 `cordis.patch.yml`，会插入 `moqi-dsh` 条目；在 profile 自己的 `cordis.patch.yml` 中补上 Python 路径：

```yaml
- id: moqi-dsh
  config:
    python: 'C:/path/to/.venv/Scripts/python.exe'
```

macOS/Linux 填相应虚拟环境的 `bin/python` 绝对路径。重启 DSH 后，新聊天回合才会使用该插件。只调用本地进程；若 moqi 缺失、数据损坏或查询超时，会原样继续聊天。不要把个人 `MOQI_HOME` 数据目录提交到公开仓库。

## 验证与移除

在测试数据目录中先运行 `guess`、`correct` 存一条记录，再对 DSH 说完整的 key，检查模型能引用已确认含义；发送带上下文的长句时，模型应根据 `usable=false` 核对语境。无命中时不会注入提示。自动化验证：`node --test integrations/dsh/test/hook.test.mjs`（在仓库根目录、且 Python 已安装 moqi 时运行）。

移除时从 profile 的 `package.json` 删除 `moqi-dsh` 依赖和 bundle，删除 profile patch 中的 `moqi-dsh` 配置，重新安装依赖并重启 DSH。个人记忆数据不会被插件删除。
