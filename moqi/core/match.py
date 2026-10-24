"""匹配：v1 故意简单，只有两条规则。

    1. key 出现在文本里（或 key 拆开后的某一段出现）
    2. signal 与文本的字符二元组重合度够高

不上向量、不调模型、不联网。理由：
    - 快。`scan` 的用法是「每次看到图片/陌生词都调一次」，慢就没法用
    - 可预测。同一个输入永远给同一个结果，出问题能查
    - 零依赖。装不上就没人用

漏了怎么办：往 signal 里多写几种说法。这是使用者能理解、也能自己动的地方，
比「换了个 embedding 模型」对吧。
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Set

SIM_THRESHOLD = 0.60
"""signal 与文本的二元组重合度到这条线算命中。"""

_PUNCT = re.compile(r"[\s\u3000,，.。!！?？:：;；'\"“”‘’()（）\[\]【】<>《》/\\|~`@#$%^&*+=_-]+")


def norm(text: str) -> str:
    """小写、去标点空白。中英文都按字符比，不做分词。"""
    if not text:
        return ""
    return _PUNCT.sub("", text).lower()


def bigrams(text: str) -> Set[str]:
    """字符二元组。中文没有空格，二元组是最省事的近似。"""
    clean = norm(text)
    if len(clean) < 2:
        return {clean} if clean else set()
    return {clean[i : i + 2] for i in range(len(clean) - 1)}


def similarity(a: str, b: str) -> float:
    """在长文本中寻找最相近的片段，用 Dice 系数避免少量重合就命中。"""
    left, right = norm(a), norm(b)
    if not left or not right:
        return 0.0
    short, long = sorted((left, right), key=len)
    if len(short) < 4:
        return 0.0
    target = bigrams(short)
    best = 0.0
    for start in range(len(long) - len(short) + 1):
        window = bigrams(long[start : start + len(short)])
        best = max(best, 2 * len(target & window) / (len(target) + len(window)))
        if best == 1.0:
            break
    return best


def key_parts(key: str) -> List[str]:
    """`哼_白发少女` → [`哼`, `白发少女`]。下划线和空格都算分隔。"""
    parts = [p for p in re.split(r"[_\s]+", key.strip()) if p]
    return parts or ([key.strip()] if key.strip() else [])


def key_score(text: str, key: str) -> float:
    """key 与文本的吻合程度，0 表示不沾边。

    整串命中给 1.00，单个多字片段给 0.70。
    单字只在整条输入就是该字时给 0.60，避免它嵌在普通词句里误命中。
    """
    clean = norm(text)
    if not clean or not key:
        return 0.0

    whole = norm(key)
    if whole and (clean == whole or (len(whole) >= 2 and whole in clean)):
        return 1.0

    best = 0.0
    for part in key_parts(key):
        piece = norm(part)
        if not piece:
            continue
        if len(piece) == 1:
            if clean == piece:
                best = max(best, 0.60)
        elif piece in clean:
            best = max(best, 0.70)
    return best


def hit_key(text: str, key: str) -> bool:
    """有没有沾上。阈值以上的都算。"""
    return key_score(text, key) > 0.0


def score(text: str, row: Dict[str, object]) -> float:
    """给一条记录打分，0 表示不命中。

    单个 key 片段只作线索；准确描述命中可把分数提升到 0.84。
    """
    key = str(row.get("key") or "")
    signal = str(row.get("signal") or "")

    key_point = key_score(text, key)
    if signal:
        sim = similarity(text, signal)
        if sim >= SIM_THRESHOLD:
            # 相似度压到 0.5~0.84，永远不会高过整串 key 命中
            signal_point = round(0.5 + (sim - SIM_THRESHOLD) * (0.34 / (1 - SIM_THRESHOLD)), 4)
            return max(key_point, signal_point)

    return key_point


def rank(
    text: str,
    rows: Sequence[Dict[str, object]],
    limit: int = 8,
) -> List[Dict[str, object]]:
    """按匹配分排序，返回带 `_score` 的新列表（不改原对象）。"""
    scored: List[Dict[str, object]] = []
    for row in rows:
        point = score(text, row)
        if point <= 0:
            continue
        item = dict(row)
        item["_score"] = point
        scored.append(item)

    scored.sort(
        key=lambda r: (
            -float(r.get("_score") or 0),
            -len(norm(str(r.get("key") or ""))),
            str(r.get("id") or ""),
        )
    )
    return scored[:limit]


def open_guesses(
    rows: Iterable[Dict[str, object]],
    limit: int = 5,
) -> List[Dict[str, object]]:
    """兼容旧调用；交互时应只呈现当前文本命中的待确认记录。"""
    pending = [dict(r) for r in rows if not r.get("truth")]
    pending.sort(key=lambda r: str(r.get("id") or ""))
    return pending[:limit]
