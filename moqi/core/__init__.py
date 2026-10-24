"""core 子包：纯标准库逻辑，零第三方依赖。

对外暴露两样东西：
    store       —— JSONL 存取
    match       —— 匹配
"""

from . import match, store

__all__ = ["store", "match"]
