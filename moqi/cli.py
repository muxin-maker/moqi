"""moqi 的命令行接口。

没有 MCP 的客户端也能用：模型只需要会「跑一条命令、读输出」。
输出的格式刻意做成**人也能直接读**——出问题时你能一眼看出它凭什么这么判。

用法：
    python -m moqi scan "他发了个哼"
    python -m moqi recall "看到这张图" --domain faces
    python -m moqi guess faces 哼_白发少女 "不服气但认了" --signal "白发少女闭眼哼气"
    python -m moqi correct faces-3f2a "撒娇"
    python -m moqi stats
    python -m moqi dump --domain faces
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .core import match as matcher
from .core import evaluation
from .core import query
from .core import store
from .core import web_lookup


def _rows(domain: Optional[str]) -> List[Dict[str, Any]]:
    return store.load(domain, strict=True) if domain else store.load_all(strict=True)


def _query_text(value: Optional[str], from_stdin: bool) -> str:
    if from_stdin:
        if value is not None:
            raise ValueError("不能同时提供文本参数和 --stdin")
        value = sys.stdin.read(matcher.MAX_QUERY_LENGTH + 1)
    if value is None:
        raise ValueError("请提供查询文本，或使用 --stdin 从标准输入读取")
    return value


def _print_rows(title: str, rows: List[Dict[str, Any]], show_score: bool = False) -> None:
    print(f"== {title} ==")
    if not rows:
        print("  （没有）")
        return
    for row in rows:
        mark = "?" if not row.get("truth") else "OK"
        head = f"  [{mark}] {row.get('id')}  {row.get('key')}"
        if show_score:
            head += f"  score={row.get('_score')}"
            if float(row.get("_score") or 0) < 0.8:
                head += "（弱匹配，请确认语境）"
        print(head)
        if row.get("signal"):
            print(f"       信号：{row['signal']}")
        if row.get("truth"):
            print(f"       用户确认：{row['truth']}")
        else:
            print(f"       待确认的猜测：{row.get('guess')}")


def cmd_scan(args: argparse.Namespace) -> int:
    text = _query_text(args.text, args.stdin)
    rows = _rows(args.domain)
    limit = max(1, min(args.limit, 50))
    if args.json:
        print(json.dumps(query.scan(text, rows, limit=limit), ensure_ascii=False, indent=2))
        return 0
    hits = matcher.rank(text, rows, limit=limit)
    open_items = [r for r in hits if not r.get("truth")]

    _print_rows("扫到这些", hits, show_score=True)
    if not hits and not open_items:
        print("没有相关记录。第一次遇到的话：先问他，再 guess 记一条。")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    context = _query_text(args.context, args.stdin)
    rows = _rows(args.domain)
    limit = max(1, min(args.limit, 50))
    if args.json:
        print(json.dumps(query.recall(context, rows, limit=limit), ensure_ascii=False, indent=2))
        return 0
    hits = matcher.rank(context, rows, limit=limit)
    _print_rows("相关记录", hits, show_score=True)
    if not hits:
        print("库里没有。先问他，再 guess 记一条。")
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    result = web_lookup.research(args.term, args.topic)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"搜索：{result['query']}")
        for item in result["results"]:
            print(f"- {item['title']}\n  {item['url']}\n  {item['snippet']}")
        print(result["hint"])
    return 0 if result["ok"] else 2


def cmd_guess(args: argparse.Namespace) -> int:
    row = store.upsert(
        domain=args.domain,
        key=args.key,
        guess=args.guess,
        signal=args.signal or "",
    )
    action = "已有" if row.get("already_confirmed") else ("更新" if row.get("existed") else "记下")
    print(f"[{action}] {row['id']}  {row['key']} → 我理解成「{row['guess']}」")
    if row.get("already_confirmed"):
        print("       已有用户确认的含义；没有覆盖它。若含义变了，请用 correct 修订")
        return 0
    if not row.get("truth"):
        print("       等他纠正后跑 correct 回填，这条才算闭环")
    return 0


def cmd_correct(args: argparse.Namespace) -> int:
    row = store.correct(args.id, args.truth, feedback=args.feedback)
    if not row:
        print(f"[!] 没有「{args.id}」这条记录。先跑 list 看看有哪些。")
        print("    也可以直接用 key 当 id：correct 哼_白发少女 撒娇")
        return 2

    print(f"[已纠正] {row['id']}  {row['key']}")
    print(f"         用户确认：{row['truth']}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    row = store.forget(args.id)
    if row is None:
        print(f"[!] 没有「{args.id}」这条记录")
        return 2
    print(f"[已删除] {row['id']}  {row['key']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = _rows(args.domain)
    if args.pending:
        rows = [r for r in rows if not r.get("truth")]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    _print_rows("记录", rows)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    rows = _rows(args.domain)
    closed = [r for r in rows if r.get("truth")]
    feedback = {name: sum(r.get("feedback") == name for r in closed) for name in ("right", "partial", "wrong")}
    domains: Dict[str, int] = {}
    for row in rows:
        domain = str(row.get("domain"))
        domains[domain] = domains.get(domain, 0) + 1
    if args.json:
        print(json.dumps({
            "total": len(rows), "closed": len(closed), "open": len(rows) - len(closed),
            "feedback": feedback, "domains": domains,
        }, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("（库里还是空的。等他第一次纠正你，就有了。）")
        return 0

    print(f"总共 {len(rows)} 条，已闭环 {len(closed)} 条，悬着 {len(rows) - len(closed)} 条")
    print(f"明确反馈：正确 {feedback['right']}，接近 {feedback['partial']}，错误 {feedback['wrong']}")

    print("各领域：")
    for domain, count in sorted(domains.items()):
        print(f"  {domain}: {count}")
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    rows = [row for row in _rows(args.domain) if row.get("truth")]
    if not rows:
        print("（没有可导出的记录）")
        return 0

    text = store.dump_markdown(rows, args.domain)
    print(text)
    if args.save:
        path = os.path.join(store.home(), "dump.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"\n[已存] {path}", file=sys.stderr)
    return 0


def cmd_json(args: argparse.Namespace) -> int:
    rows = _rows(args.domain)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """只读检查安装和数据文件，方便首次接入时定位故障。"""
    issues: List[str] = []
    domains = store.list_domains()
    total = 0
    for domain in domains:
        try:
            total += len(store.load(domain, strict=True))
        except (OSError, UnicodeError, store.DataIntegrityError) as exc:
            issues.append(f"{domain}: {exc}")
    result = {
        "ok": not issues,
        "version": __version__,
        "python": sys.version.split()[0],
        "data_dir": os.path.abspath(store.home()),
        "domains": len(domains),
        "records": total,
        "mcp_available": importlib.util.find_spec("mcp") is not None,
        "research_configured": bool(os.environ.get("MOQI_BRAVE_API_KEY", "").strip()),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"moqi {result['version']} · Python {result['python']}")
        print(f"数据目录：{result['data_dir']}（{total} 条，{len(domains)} 个领域）")
        mcp_status = "可用" if result["mcp_available"] else '未安装，可用 pip install ".[mcp]"'
        print(f"MCP：{mcp_status}")
        print(f"联网查梗：{'已配置' if result['research_configured'] else '未配置（可选）'}")
        print("数据检查：" + ("通过" if not issues else "发现问题：" + "; ".join(issues)))
    return 0 if not issues else 2


def cmd_evaluate(args: argparse.Namespace) -> int:
    result = evaluation.evaluate(args.path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"评估 {result['total']} 句，符合标注 {result['correct']} 句，准确率 {result['accuracy']:.1%}")
        for item in result["mismatches"]:
            print(f"  第 {item['line']} 行 {item['id']}：预期 {item['expected']}，实际 {item['actual']}（{item['score']}）")
    return 0 if not result["mismatches"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="moqi",
        description="你和你的 AI 之间的默契笔记",
    )
    parser.add_argument("--version", action="version", version=f"moqi {__version__}")
    parser.add_argument("--domain", "-d", help="只对某个领域操作")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出（配合 list/stats）")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="嗅探：这段话里有没有我可能理解错的地方")
    p_scan.add_argument("text", nargs="?")
    p_scan.add_argument("--stdin", action="store_true", help="从标准输入读取，适合宿主每轮调用")
    p_scan.add_argument("--limit", type=int, default=8)
    p_scan.set_defaults(func=cmd_scan)

    p_recall = sub.add_parser("recall", help="按上下文查相关条目")
    p_recall.add_argument("context", nargs="?")
    p_recall.add_argument("--stdin", action="store_true", help="从标准输入读取")
    p_recall.add_argument("--limit", type=int, default=8)
    p_recall.set_defaults(func=cmd_recall)

    p_research = sub.add_parser("research", help="联网查公开梗的出处线索（需配置 Brave Search API）")
    p_research.add_argument("term", help="公开短语，不要输入私人聊天")
    p_research.add_argument("--topic", default="", help="公开背景，例如游戏名")
    p_research.set_defaults(func=cmd_research)

    p_guess = sub.add_parser("guess", help="记下我的猜测")
    p_guess.add_argument("domain")
    p_guess.add_argument("key")
    p_guess.add_argument("guess")
    p_guess.add_argument("--signal", default="")
    p_guess.set_defaults(func=cmd_guess)

    p_correct = sub.add_parser("correct", help="回填真实意思")
    p_correct.add_argument("id")
    p_correct.add_argument("truth")
    p_correct.add_argument("--feedback", choices=("right", "partial", "wrong"))
    p_correct.set_defaults(func=cmd_correct)

    p_forget = sub.add_parser("forget", help="按完整 id 或 key 删除一条记录")
    p_forget.add_argument("id")
    p_forget.set_defaults(func=cmd_forget)

    p_list = sub.add_parser("list", help="列出记录")
    p_list.add_argument("--pending", action="store_true", help="只看还没闭环的")
    p_list.set_defaults(func=cmd_list)

    p_stats = sub.add_parser("stats", help="确认条数与明确反馈")
    p_stats.set_defaults(func=cmd_stats)

    p_dump = sub.add_parser("dump", help="导出 markdown（给没有工具的模型贴）")
    p_dump.add_argument("--save", action="store_true", help="另存一份到数据目录")
    p_dump.set_defaults(func=cmd_dump)

    p_json = sub.add_parser("json", help="原始 JSON")
    p_json.set_defaults(func=cmd_json)

    p_doctor = sub.add_parser("doctor", help="只读检查安装、依赖和数据文件")
    p_doctor.set_defaults(func=cmd_doctor)

    p_eval = sub.add_parser("evaluate", help="用人工标注的 JSONL 例句评估匹配效果")
    p_eval.add_argument("path")
    p_eval.set_defaults(func=cmd_evaluate)

    return parser


def _hoist_globals(argv: List[str]) -> List[str]:
    """让 `moqi dump --domain faces` 和 `moqi --domain faces dump` 都能用。

    argparse 的全局参数必须写在子命令前面，但人下意识会写在后面。
    与其在 README 里写个注意事项，不如这里替人挪一下。
    """
    head: List[str] = []
    rest: List[str] = []
    index = 0
    while index < len(argv):
        item = argv[index]
        if item in ("--domain", "-d") and index + 1 < len(argv):
            head.extend([item, argv[index + 1]])
            index += 2
            continue
        if item.startswith("--domain="):
            head.append(item)
            index += 1
            continue
        if item == "--json":
            head.append(item)
            index += 1
            continue
        rest.append(item)
        index += 1
    return head + rest


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(_hoist_globals(raw))
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except (ValueError, TimeoutError, OSError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
