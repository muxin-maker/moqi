"""JSONL 存取：一个领域一个文件，一行一条。

设计取舍：
    不上数据库。JSONL 能 git diff、能手改、能整份发给别人，
    这比查询快慢重要得多——它是这东西值得开源的原因。

写的方式：
    读全量 → 改内存 → 写临时文件 → os.replace 原子替换。
    所以永远不会出现半行，也不会因为写到一半断掉而毁掉整份库。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".moqi")
MAX_KEY_LENGTH = 256
MAX_TEXT_LENGTH = 2000

RESERVED_FIELDS = ("domain",)
"""由 store 自己维护的字段，upsert 时不许外部覆盖。"""

INTERNAL_FIELDS = ("existed", "already_confirmed")
"""只活在内存里的字段，落盘前一律剥掉。"""


class DataIntegrityError(ValueError):
    """文件已有损坏内容，拒绝覆盖以免丢失原始数据。"""


class AmbiguousMatchError(ValueError):
    """查询匹配了多条记录，必须使用完整 id 或更具体的 key。"""


@contextmanager
def domain_lock(domain: str):
    """跨进程锁住一个领域的读改写事务。"""
    path = domain_path(domain) + ".lock"
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "a+b") as fh:
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        fh.seek(0)
        if os.name == "nt":
            import msvcrt

            for attempt in range(100):
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if attempt == 99:
                        raise TimeoutError(f"等待领域锁超时：{domain}")
                    time.sleep(0.1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fh.seek(0)
            if os.name == "nt":
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def home() -> str:
    """数据目录。`MOQI_HOME` 可覆盖，默认 ~/.moqi。"""
    return os.environ.get("MOQI_HOME") or DEFAULT_HOME


def domain_path(domain: str) -> str:
    """某个领域的数据文件路径。"""
    safe = "".join(ch for ch in domain if ch.isalnum() or ch in "-_")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if not safe or safe != domain or len(domain) > 64 or domain.upper() in reserved:
        raise ValueError(f"领域名不合法：{domain!r}")
    return os.path.join(home(), f"{safe}.jsonl")


def list_domains() -> List[str]:
    """数据目录下现有哪些领域。文件不存在时返回空列表。"""
    base = home()
    if not os.path.isdir(base):
        return []
    out: List[str] = []
    for name in sorted(os.listdir(base)):
        if name.endswith(".jsonl"):
            domain = name[: -len(".jsonl")]
            try:
                domain_path(domain)
            except ValueError:
                continue
            else:
                out.append(domain)
    return out


def load(domain: str, *, strict: bool = False) -> List[Dict[str, Any]]:
    """读一个领域的全部记录。坏行跳过，不让一行脏数据毁掉整库。"""
    path = domain_path(domain)
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    seen_ids = set()
    seen_keys = set()
    with io.open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if strict:
                    raise DataIntegrityError(f"{path} 第 {number} 行不是有效 JSON，已拒绝写入")
                continue
            if not isinstance(row, dict):
                if strict:
                    raise DataIntegrityError(f"{path} 第 {number} 行不是记录对象，已拒绝写入")
                continue
            if strict:
                row_id, key = row.get("id"), row.get("key")
                if not isinstance(row_id, str) or not row_id.startswith(domain + "-"):
                    raise DataIntegrityError(f"{path} 第 {number} 行缺少合法 id")
                if not isinstance(key, str) or not key.strip():
                    raise DataIntegrityError(f"{path} 第 {number} 行缺少 key")
                if row_id in seen_ids or key.strip() in seen_keys:
                    raise DataIntegrityError(f"{path} 第 {number} 行有重复 id 或 key")
                seen_ids.add(row_id)
                seen_keys.add(key.strip())
            # 文件名是领域的唯一依据，避免脏行在跨领域保存时被漏掉。
            row["domain"] = domain
            rows.append(row)
    return rows


def load_all(*, strict: bool = False) -> List[Dict[str, Any]]:
    """读所有领域的全部记录。"""
    rows: List[Dict[str, Any]] = []
    for domain in list_domains():
        rows.extend(load(domain, strict=strict))
    return rows


def dump_markdown(rows: Iterable[Dict[str, Any]], domain: Optional[str] = None) -> str:
    """只导出已确认记录，并转义可改变 Markdown 结构的字符。"""
    def escaped(value: Any) -> str:
        text = str(value or "")
        for old, new in (("\\", "\\\\"), ("\r", "\\r"), ("\n", "\\n"), ("*", "\\*"), ("`", "\\`"), ("[", "\\["), ("]", "\\]")):
            text = text.replace(old, new)
        return text

    lines = ["# 默契笔记", ""]
    if domain:
        lines.extend((f"领域：{escaped(domain)}", ""))
    for row in rows:
        if not row.get("truth"):
            continue
        line = f"- **[{escaped(row.get('domain'))}] {escaped(row.get('key'))}**：{escaped(row['truth'])}"
        if row.get("signal"):
            line += f"（信号：{escaped(row['signal'])}）"
        lines.append(line)
    return "\n".join(lines)


def _save_unlocked(domain: str, rows: Iterable[Dict[str, Any]]) -> None:
    """原子写一个领域。

    落盘前剥掉内部字段（`existed` 只用来告诉调用方「新建还是更新」，
    不该出现在数据文件里，也不该被 `json` 子命令暴露出去）。
    """
    path = domain_path(domain)
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    lines: List[str] = []
    for row in rows:
        clean = {k: v for k, v in row.items() if k not in INTERNAL_FIELDS}
        lines.append(json.dumps(clean, ensure_ascii=False))
    body = "\n".join(lines) + ("\n" if lines else "")

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        raise


def save(domain: str, rows: Iterable[Dict[str, Any]]) -> None:
    """手动替换领域内容；文件损坏时拒绝覆盖。"""
    with domain_lock(domain):
        load(domain, strict=True)
        _save_unlocked(domain, rows)


def make_id(domain: str, key: str) -> str:
    """由 key 派生稳定 id：`<domain>-<24位hash>`。

    同一个 key 永远得到同一个 id，所以同一条默契不会被记成两条。
    """
    digest = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()[:24]
    return f"{domain}-{digest}"


def find_by_id(row_id: str) -> Optional[Dict[str, Any]]:
    """跨领域找一条。领域数量是小数，直接扫，不建索引。"""
    matches: List[Dict[str, Any]] = []
    for domain in list_domains():
        for row in load(domain):
            if row.get("id") == row_id:
                matches.append(row)
    if len(matches) > 1:
        raise AmbiguousMatchError(f"id={row_id} 在多个文件中重复，请先修复数据")
    return matches[0] if matches else None


def find(query: str) -> Optional[Dict[str, Any]]:
    """按 id 或 key 找一条；模糊结果不唯一时拒绝猜测。

    为什么要这一层：id 是四个十六进制字符，人在对话里记不住。
    对方说「那个哼」，用 `correct 哼 撒娇` 就该能用。
    """
    want = (query or "").strip()
    if not want:
        return None

    exact = find_by_id(want)
    if exact:
        return exact

    rows: List[Dict[str, Any]] = []
    for domain in list_domains():
        rows.extend(load(domain))

    for predicate in (
        lambda row: str(row.get("key") or "").strip() == want,
        lambda row: str(row.get("id") or "").startswith(want),
        lambda row: want.lower() in str(row.get("key") or "").lower(),
    ):
        matches = [row for row in rows if predicate(row)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            choices = ", ".join(str(row.get("id")) for row in matches[:5])
            raise AmbiguousMatchError(f"「{want}」匹配多条记录：{choices}；请用完整 id")

    return None


def upsert(
    domain: str,
    key: str,
    guess: str,
    signal: str = "",
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """记一条猜测。同一个 key 已有记录就更新猜测，不新开一条。

    返回的记录里带 `existed` 字段，告诉调用方这是新的还是更新的。
    """
    if not key.strip() or not guess.strip():
        raise ValueError("key 和 guess 不能为空")
    if len(key) > MAX_KEY_LENGTH or len(guess) > MAX_TEXT_LENGTH or len(signal) > MAX_TEXT_LENGTH:
        raise ValueError("key 或描述过长；请只保存提炼后的短结论，不存整段聊天")
    domain_path(domain)
    row_id = make_id(domain, key)
    stamp = now or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with domain_lock(domain):
        rows = load(domain, strict=True)
        for row in rows:
            if str(row.get("key") or "").strip() == key.strip():
                row["existed"] = True
                if row.get("truth"):
                    row["already_confirmed"] = True
                    return row
                row["guess"] = guess
                if signal:
                    row["signal"] = signal
                _save_unlocked(domain, rows)
                return row
        if any(row.get("id") == row_id for row in rows):
            raise DataIntegrityError(f"领域 {domain} 中 id={row_id} 已属于别的 key")

        row: Dict[str, Any] = {
            "id": row_id,
            "domain": domain,
            "key": key,
            "signal": signal,
            "guess": guess,
            "truth": None,
            "created": stamp,
            "corrected_at": None,
            "existed": False,
        }
        rows.append(row)
        _save_unlocked(domain, rows)
        return row


def apply_truth(
    row: Dict[str, Any], truth: str, now: Optional[str] = None, feedback: Optional[str] = None
) -> Dict[str, Any]:
    """原样保存用户确认的含义；猜测评价只使用用户明确给出的 feedback。"""
    if not truth.strip():
        raise ValueError("真实含义不能为空")
    if len(truth) > MAX_TEXT_LENGTH:
        raise ValueError("真实含义过长；请只保存提炼后的短结论")
    if feedback not in (None, "right", "partial", "wrong"):
        raise ValueError("feedback 只能是 right、partial 或 wrong")
    if row.get("truth") == truth and (feedback is None or row.get("feedback") == feedback):
        return row
    if row.get("truth") != truth and feedback is None:
        row.pop("feedback", None)
    row["truth"] = truth
    row["corrected_at"] = now or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if feedback is not None:
        row["feedback"] = feedback
    return row


def correct(query: str, truth: str, feedback: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """在同一把领域锁内重新读取、纠正并写回，避免覆盖并发更新。"""
    found = find(query)
    if found is None:
        return None
    domain = str(found["domain"])
    with domain_lock(domain):
        rows = load(domain, strict=True)
        for row in rows:
            if row.get("id") == found.get("id") and row.get("key") == found.get("key"):
                if any(row.get(field) != found.get(field) for field in ("guess", "truth", "feedback", "corrected_at")):
                    raise DataIntegrityError("记录刚被另一个客户端修改，请重新查询后再纠正")
                apply_truth(row, truth, feedback=feedback)
                _save_unlocked(domain, rows)
                return row
    raise DataIntegrityError("记录在纠正期间发生变化，请重新查询")


def forget(query: str) -> Optional[Dict[str, Any]]:
    """仅按完整 id 或完整 key 删除一条，模糊查询不能触发删除。"""
    want = (query or "").strip()
    if not want:
        raise ValueError("请提供完整 id 或 key")
    rows = load_all()
    matches = [row for row in rows if row.get("id") == want]
    if not matches:
        matches = [row for row in rows if str(row.get("key") or "").strip() == want]
    if not matches:
        return None
    if len(matches) > 1:
        raise AmbiguousMatchError(f"「{want}」对应多条记录，请使用完整 id")
    found = matches[0]
    domain = str(found["domain"])
    with domain_lock(domain):
        current = load(domain, strict=True)
        for index, row in enumerate(current):
            if row.get("id") == found.get("id") and row.get("key") == found.get("key"):
                if row != found:
                    raise DataIntegrityError("记录刚被另一个客户端修改，请重新查询后再删除")
                current.pop(index)
                _save_unlocked(domain, current)
                return row
    raise DataIntegrityError("记录在删除期间发生变化，请重新查询")
