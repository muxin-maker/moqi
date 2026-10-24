"""MCP 冒烟测试：把 server 真拉起来，连一遍，列工具、调一次。

不放进 pytest 收集（文件名不以 test_ 开头），因为它要起子进程、依赖
mcp sdk，比单元测试重得多。手动跑：

    python tests/mcp_smoke.py

退出码 0 = 通了。
"""

import asyncio
import atexit
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main() -> int:
    try:
        from mcp import ClientSession, StdioServerParameters, stdio_client
    except ImportError:
        print("[skip] 没装 mcp，先 pip install mcp")
        return 0

    temp_root = os.path.join(ROOT, ".tmptest")
    os.makedirs(temp_root, exist_ok=True)
    home = tempfile.mkdtemp(prefix="moqi-mcp-", dir=temp_root)
    atexit.register(shutil.rmtree, home, ignore_errors=True)
    env = dict(os.environ)
    env["MOQI_HOME"] = home
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "moqi.mcp.server"],
        env=env,
        cwd=ROOT,
    )

    print(f"（数据目录：{home}）")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[ok] 握手完成")

            listed = await session.list_tools()
            names = [t.name for t in listed.tools]
            print(f"[ok] 工具 {len(names)} 个：{', '.join(names)}")

            expect = {"scan", "recall", "guess", "correct", "forget", "stats", "dump"}
            missing = expect - set(names)
            if missing:
                print(f"[fail] 少了：{sorted(missing)}")
                return 1

            got = await session.call_tool("guess", {
                "domain": "faces",
                "key": "哼_白发少女",
                "guess": "不服气但认了",
                "signal": "白发少女闭眼哼气",
            })
            text = str(got.content)
            print(f"[ok] guess → {text[:120]}")
            if "faces-" not in text:
                print("[fail] guess 没返回 id")
                return 1

            entry_id = json.loads(got.content[0].text)["id"]
            got = await session.call_tool("correct", {"id": entry_id, "truth": "撒娇", "feedback": "wrong"})
            print(f"[ok] correct → {str(got.content)[:120]}")

            got = await session.call_tool("scan", {"text": "白发少女闭眼哼气"})
            body = str(got.content)
            print(f"[ok] scan → {body[:160]}")
            scan_result = json.loads(got.content[0].text)
            if not scan_result["hits"] or scan_result["hits"][0]["meaning"] != "撒娇":
                print("[fail] scan 没带回正确答案")
                return 1
            if scan_result["hits"][0]["match_score"] < 0.8:
                print("[fail] scan 没有给出可解释的强匹配分数")
                return 1
            if scan_result["hits"][0]["usable"] is not True:
                print("[fail] 已确认的强匹配没有标为可用")
                return 1

            pending_result = await session.call_tool("guess", {"domain": "slang", "key": "另一条", "guess": "未确认"})
            pending_id = json.loads(pending_result.content[0].text)["id"]
            got = await session.call_tool("scan", {"text": "我哼着歌"})
            unrelated = json.loads(got.content[0].text)
            if unrelated["hits"] or unrelated["open_guesses"]:
                print("[fail] 无关句子误命中或带出无关待确认记录")
                return 1

            for domain, meaning in (("tone", "含义甲"), ("slang", "含义乙")):
                created = await session.call_tool("guess", {
                    "domain": domain, "key": "同一个词", "guess": "待确认",
                })
                row_id = json.loads(created.content[0].text)["id"]
                await session.call_tool("correct", {"id": row_id, "truth": meaning})
            got = await session.call_tool("scan", {"text": "同一个词"})
            conflict = json.loads(got.content[0].text)
            if not conflict["conflicting"] or any(hit["usable"] for hit in conflict["hits"]):
                print("[fail] 相同 key 的不同含义没有要求确认语境")
                return 1

            got = await session.call_tool("stats", {})
            print(f"[ok] stats → {str(got.content)[:120]}")

            got = await session.call_tool("dump", {})
            print(f"[ok] dump → {str(got.content)[:120]}")
            if "另一条" in str(got.content):
                print("[fail] dump 带出了未确认的猜测")
                return 1

            deleted = await session.call_tool("forget", {"id": pending_id})
            if not json.loads(deleted.content[0].text)["ok"]:
                print("[fail] forget 没有删除指定测试记录")
                return 1

    print("\n全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
