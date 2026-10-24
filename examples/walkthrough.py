"""把 README 里那条链路跑一遍，用临时目录，不碰你的真数据。

    python examples/walkthrough.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cli(*args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    out = subprocess.run(
        [sys.executable, "-m", "moqi.cli", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print("$ moqi " + " ".join(args))
    print((out.stdout or "").rstrip())
    if out.stderr.strip():
        print((out.stderr or "").rstrip())
    print()
    return out


def main():
    os.makedirs(os.path.join(ROOT, ".tmptest"), exist_ok=True)
    home = tempfile.mkdtemp(prefix="moqi-demo-", dir=os.path.join(ROOT, ".tmptest"))
    os.environ["MOQI_HOME"] = home
    print(f"（数据目录：{home}，跑完就删）\n")

    try:
        print("== 第一步：他说了个「哼」，我不知道是哪种 ==")
        cli("scan", "他发了个哼")

        print("== 第二步：我先猜，记下来 ==")
        cli(
            "guess",
            "faces",
            "哼_白发少女",
            "不服气但认了",
            "--signal",
            "白发少女闭眼哼气",
        )

        print("== 第三步：他纠正我 ==")
        cli("correct", "哼_白发少女", "撒娇", "--feedback", "wrong")

        print("== 第四步：下次再看到，直接给正确答案 ==")
        cli("scan", "白发少女闭眼哼气")

        print("== 第五步：攒了多少 ==")
        cli("stats")

        print("== 第六步：换模型时导出 ==")
        cli("dump")
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
