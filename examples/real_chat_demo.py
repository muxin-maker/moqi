"""两段自然聊天中的 moqi 用法；数据隔离，运行后自动清理。

运行：python examples/real_chat_demo.py
这是确定性演示，不代替真实 MCP 宿主是否会主动调用工具的测试。
"""

import os
import tempfile
from pathlib import Path

from moqi.core import match, store


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    temp_root = ROOT / ".tmptest"
    temp_root.mkdir(exist_ok=True)
    previous_home = os.environ.get("MOQI_HOME")
    try:
        with tempfile.TemporaryDirectory(prefix="moqi-real-chat-", dir=temp_root) as demo_home:
            os.environ["MOQI_HOME"] = demo_home

            first_message = "刚刚那局最后一秒被反杀了，我了个雷。"
            assert match.rank(first_message, store.load_all()) == []
            guessed = store.upsert(
                "slang", "我了个雷", "表示惊讶",
                signal="我了个雷；火影忍者手游界的一个热梗",
            )
            corrected = store.correct(guessed["id"], "震惊吧", feedback="partial")
            assert corrected is not None and corrected["truth"] == "震惊吧"

            # 第二天的聊天使用同一份本地记录，不需要重新解释这个梗。
            next_message = "今天又碰到最后一秒翻盘，我了个雷，这也能赢？"
            remembered = match.rank(next_message, store.load_all())
            assert remembered and remembered[0]["truth"] == "震惊吧"
            assert remembered[0]["_score"] >= 0.8

            # 另一个单字记录不能误套到普通叙述里的“哼”。
            tone = store.upsert("tone", "哼", "不高兴")
            store.correct(tone["id"], "撒娇", feedback="wrong")
            unrelated_message = "我哼着歌去打下一局。"
            assert match.rank(unrelated_message, store.load_all()) == []

            print("第一天｜对局结束")
            print(f"用户：{first_message}")
            print("AI：最后一秒被反杀，确实挺意外的。你说的‘我了个雷’是表示惊讶吗？")
            print("用户：差不多吧，这是火影忍者手游界的一个热梗。准确说是震惊吧。")
            print("后台：把用户原话‘震惊吧’记为含义，旧猜测标记为‘接近’。")
            print()
            print("第二天｜继续聊天")
            print(f"用户：{next_message}")
            print(f"后台：命中‘{remembered[0]['key']}’→‘{remembered[0]['truth']}’，分数 {remembered[0]['_score']:.2f}。")
            print("AI：最后一秒还能翻回来，确实让人震惊。你当时是怎么打赢的？")
            print()
            print("误命中检查")
            print(f"用户：{unrelated_message}")
            print("后台：没有命中‘哼＝撒娇’，按普通叙述处理。")
    finally:
        if previous_home is None:
            os.environ.pop("MOQI_HOME", None)
        else:
            os.environ["MOQI_HOME"] = previous_home


if __name__ == "__main__":
    main()
