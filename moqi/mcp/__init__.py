"""MCP 适配层。

**故意不在这里 import server。**

`python -m moqi.mcp.server` 会先 import 包 `moqi.mcp`；如果这里顺手
`from . import server`，server 模块就被提前加载了，runpy 会警告
"found in sys.modules after import of package"。
要 server 就自己 import：`from moqi.mcp import server`。
"""
