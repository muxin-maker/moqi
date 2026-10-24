"""用人工标注的例句评估匹配规则；只读，不访问用户的数据目录。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import match

LABELS = ("strong", "weak", "none")


def label(score: float) -> str:
    if score >= 0.8:
        return "strong"
    return "weak" if score > 0 else "none"


def evaluate(path: str) -> Dict[str, Any]:
    """逐行读取 {text,key,signal,expected}，返回总数与错例。"""
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ValueError(f"无法读取评估文件：{source}") from exc
    if size > 2_000_000:
        raise ValueError("评估文件超过 2 MB，请分批运行")
    counts = {name: 0 for name in LABELS}
    predicted = {name: 0 for name in LABELS}
    mismatches: List[Dict[str, Any]] = []
    total = 0
    with source.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {number} 行不是有效 JSON") from exc
            if not isinstance(case, dict) or not all(isinstance(case.get(field), str) for field in ("text", "key", "expected")):
                raise ValueError(f"第 {number} 行需要 text、key、expected 字符串")
            if case["expected"] not in LABELS or not isinstance(case.get("signal", ""), str):
                raise ValueError(f"第 {number} 行的 expected 或 signal 不合法")
            if len(case["text"]) > 2000 or len(case["key"]) > 256 or len(case.get("signal", "")) > 2000:
                raise ValueError(f"第 {number} 行文本过长")
            point = match.score(case["text"], case)
            actual = label(point)
            counts[case["expected"]] += 1
            predicted[actual] += 1
            total += 1
            if actual != case["expected"]:
                mismatches.append({"line": number, "id": case.get("id", number), "expected": case["expected"], "actual": actual, "score": point})
    if total == 0:
        raise ValueError("评估文件没有例句")
    return {
        "total": total,
        "correct": total - len(mismatches),
        "accuracy": round((total - len(mismatches)) / total, 4),
        "expected": counts,
        "predicted": predicted,
        "mismatches": mismatches,
    }
