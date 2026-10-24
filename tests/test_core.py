"""core 的单元测试。零外部依赖，pytest 跑。

    pip install pytest
    pytest -q
"""

import os
import sys
import multiprocessing
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moqi.core import match as matcher  # noqa: E402
from moqi.core import store  # noqa: E402
from moqi import cli  # noqa: E402


def _parallel_writer(home, prefix):
    os.environ["MOQI_HOME"] = home
    for index in range(20):
        store.upsert("parallel", f"{prefix}-{index}", "含义")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """每个用例一个空数据目录，绝不碰真的 ~/.moqi。"""
    monkeypatch.setenv("MOQI_HOME", str(tmp_path))
    yield tmp_path


# ---------- match ----------

def test_norm_strips_punct_and_space():
    assert matcher.norm(" 你 好，啊！ ") == "你好啊"


def test_bigrams_of_single_char():
    assert matcher.bigrams("哼") == {"哼"}


def test_similarity_identical_is_one():
    assert matcher.similarity("白发少女闭眼", "白发少女闭眼") == 1.0


def test_key_score_whole_match_is_one():
    assert matcher.key_score("哼_白发少女", "哼_白发少女") == 1.0
    assert matcher.key_score("他发了个哼_白发少女", "哼_白发少女") == 0.70


def test_long_sentence_does_not_make_slang_certain():
    row = {"key": "我了个雷", "signal": "我了个雷"}
    assert matcher.score("我了个雷！", row) == 1.0
    assert matcher.score("我了个雷炸了", row) < 0.8
    assert matcher.score("你说我了个雷是在骂人吗", row) < 0.8


def test_embedded_signal_is_only_a_clue():
    row = {"key": "别的词", "signal": "白发少女闭眼哼气"}
    assert matcher.score("白发少女闭眼哼气", row) == 0.84
    assert matcher.score("她说白发少女闭眼哼气是在生气", row) < 0.8


def test_key_score_multi_char_part():
    assert matcher.key_score("白发少女闭眼了", "哼_白发少女") == 0.70


def test_single_char_only_matches_standalone_message():
    assert matcher.key_score("哼", "哼_白发少女") == 0.60
    assert matcher.key_score("他发了个哼", "哼_白发少女") == 0.0
    assert matcher.key_score("我哼了一首歌", "哼") == 0.0


def test_key_score_no_match():
    assert matcher.key_score("今天吃什么", "哼_白发少女") == 0.0


def test_signal_similarity_never_beats_key():
    row = {"key": "哼_白发少女", "signal": "白发少女闭眼哼气"}
    assert matcher.score("白发少女闭眼哼气", row) == 0.84
    assert matcher.score("白发少女今天来了", row) < 0.8


def test_rank_sorts_and_limits():
    rows = [
        {"id": "a", "key": "哼", "signal": ""},
        {"id": "b", "key": "哼_白发少女", "signal": ""},
    ]
    got = matcher.rank("哼_白发少女来了", rows)
    assert [r["id"] for r in got] == ["b"]


def test_rank_drops_non_hits():
    rows = [{"id": "a", "key": "河马", "signal": ""}]
    assert matcher.rank("今天天气", rows) == []


def test_open_guesses_excludes_confirmed():
    rows = [
        {"id": "a", "key": "a", "truth": None},
        {"id": "b", "key": "b", "truth": "已知"},
    ]
    assert [r["id"] for r in matcher.open_guesses(rows)] == ["a"]


# ---------- store ----------

def test_upsert_creates_then_updates():
    first = store.upsert("faces", "哼", "不服气")
    assert first["existed"] is False
    second = store.upsert("faces", "哼", "撒娇")
    assert second["existed"] is True
    assert len(store.load("faces")) == 1
    assert store.load("faces")[0]["guess"] == "撒娇"


def test_upsert_keeps_signal_when_blank():
    store.upsert("slang", "666", "厉害", signal="夸人")
    row = store.upsert("slang", "666", "敷衍")
    assert row["signal"] == "夸人"


def test_same_key_same_id():
    a = store.make_id("faces", "哼")
    b = store.make_id("faces", " 哼 ")
    assert a == b


def test_previous_four_digit_hash_collision_no_longer_overwrites():
    first = store.upsert("slang", "key78", "A")
    second = store.upsert("slang", "key295", "B")
    assert first["id"] != second["id"]
    assert len(store.load("slang")) == 2


def test_existing_short_id_is_kept_for_same_key():
    row = store.upsert("slang", "旧词", "旧猜测")
    row["id"] = "slang-ab12"
    store.save("slang", [row])
    updated = store.upsert("slang", "旧词", "新猜测")
    assert updated["id"] == "slang-ab12"
    assert len(store.load("slang")) == 1


def test_confirmed_record_cannot_be_overwritten_by_new_guess():
    first = store.upsert("slang", "我了个雷", "惊讶")
    store.correct(first["id"], "震惊吧", feedback="partial")
    repeated = store.upsert("slang", "我了个雷", "别的意思")
    assert repeated["already_confirmed"] is True
    assert store.load("slang")[0]["guess"] == "惊讶"
    assert store.load("slang")[0]["truth"] == "震惊吧"


def test_stale_correction_is_rejected(monkeypatch):
    row = store.upsert("slang", "词", "猜测")
    stale = store.find(row["id"])
    store.correct(row["id"], "新含义")
    monkeypatch.setattr(store, "find", lambda query: stale)
    with pytest.raises(store.DataIntegrityError):
        store.correct(row["id"], "过期含义")
    assert store.load("slang")[0]["truth"] == "新含义"


def test_apply_truth_preserves_users_wording_and_explicit_feedback():
    row = store.upsert("faces", "哼", "不服气")
    row = store.apply_truth(row, "撒娇", feedback="partial")
    assert row["truth"] == "撒娇"
    assert row["feedback"] == "partial"


def test_apply_truth_does_not_infer_guess_accuracy_from_wording():
    row = store.upsert("faces", "嗯", "同意")
    row = store.apply_truth(row, "同意")
    assert "feedback" not in row


def test_apply_truth_twice_same_answer_not_double_counted():
    row = store.upsert("faces", "嗯", "同意")
    row = store.apply_truth(row, "同意")
    row = store.apply_truth(row, "同意")
    assert row["truth"] == "同意"
    assert row["corrected_at"] is not None


def test_changing_truth_does_not_keep_old_feedback():
    row = store.upsert("slang", "词", "A")
    row = store.apply_truth(row, "B", feedback="wrong")
    row = store.apply_truth(row, "C")
    assert row["truth"] == "C"
    assert "feedback" not in row


def test_find_by_hash_id():
    row = store.upsert("faces", "哼", "不服气")
    assert store.find(row["id"])["id"] == row["id"]


def test_find_by_id_prefix():
    row = store.upsert("faces", "哼", "不服气")
    assert store.find(row["id"][:3])["id"] == row["id"]


def test_find_by_exact_key():
    row = store.upsert("faces", "哼_白发少女", "不服气")
    assert store.find("哼_白发少女")["id"] == row["id"]


def test_find_by_partial_key():
    row = store.upsert("faces", "哼_白发少女", "不服气")
    assert store.find("白发少女")["id"] == row["id"]


def test_ambiguous_partial_key_requires_specific_id():
    store.upsert("faces", "哼_白发少女", "a")
    store.upsert("faces", "哼_黑发少年", "b")
    with pytest.raises(store.AmbiguousMatchError):
        store.find("哼")


def test_forget_requires_exact_key_or_full_id():
    first = store.upsert("slang", "我了个雷", "惊讶")
    assert store.forget("我了个") is None
    assert store.forget(first["id"])["key"] == "我了个雷"
    assert store.load("slang") == []


def test_forget_rejects_same_key_in_two_domains():
    store.upsert("slang", "哼", "甲")
    store.upsert("tone", "哼", "乙")
    with pytest.raises(store.AmbiguousMatchError):
        store.forget("哼")
    assert len(store.load_all()) == 2


def test_find_missing_returns_none():
    assert store.find("不存在的东西") is None


def test_corrupt_line_does_not_break_load(isolated_home):
    store.upsert("faces", "哼", "不服气")
    path = store.domain_path("faces")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{这不是 json}\n")
    assert len(store.load("faces")) == 1


def test_write_refuses_to_erase_corrupt_line():
    store.upsert("faces", "哼", "不服气")
    path = store.domain_path("faces")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{坏行}\n")
    before = open(path, "rb").read()
    with pytest.raises(store.DataIntegrityError):
        store.upsert("faces", "嗯", "同意")
    assert open(path, "rb").read() == before


def test_write_refuses_duplicate_key_in_existing_file():
    row = store.upsert("slang", "词", "猜测")
    duplicate = dict(row, id="slang-deadbeef", guess="另一猜测")
    path = store.domain_path("slang")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(duplicate, ensure_ascii=False) + "\n")
    before = open(path, "rb").read()
    with pytest.raises(store.DataIntegrityError):
        store.upsert("slang", "新词", "猜测")
    assert open(path, "rb").read() == before


def test_concurrent_writers_keep_all_records(isolated_home):
    context = multiprocessing.get_context("spawn")
    workers = [context.Process(target=_parallel_writer, args=(str(isolated_home), prefix)) for prefix in ("a", "b")]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=20)
        assert worker.exitcode == 0
    assert len(store.load("parallel")) == 40


def test_invalid_domain_is_rejected_instead_of_colliding_with_another_file():
    with pytest.raises(ValueError):
        store.upsert("face/s", "哼", "不服气")
    assert store.list_domains() == []
    with pytest.raises(ValueError):
        store.upsert("CON", "词", "含义")


def test_rejects_whole_conversation_as_guess():
    with pytest.raises(ValueError):
        store.upsert("slang", "词", "a" * (store.MAX_TEXT_LENGTH + 1))


def test_list_domains_ignores_unsupported_file_names(isolated_home):
    (isolated_home / "faces.old.jsonl").write_text("{}\n", encoding="utf-8")
    assert store.load_all() == []


def test_file_domain_wins_over_stale_row_domain_during_scan():
    row = store.upsert("faces", "哼", "不服气")
    row["domain"] = "wrong"
    store.save("faces", [row])

    assert cli.main(["scan", "哼"]) == 0
    saved = store.load("faces")
    assert len(saved) == 1
    assert saved[0]["domain"] == "faces"
    assert "hits" not in saved[0]


def test_load_all_merges_domains():
    store.upsert("faces", "哼", "a")
    store.upsert("slang", "666", "b")
    assert {r["domain"] for r in store.load_all()} == {"faces", "slang"}


def test_dump_only_exports_confirmed_and_escapes_multiline_text():
    confirmed = store.upsert("slang", "测试*词", "猜测")
    store.correct(confirmed["id"], "含义\n# 另一段")
    store.upsert("slang", "待确认", "猜测")
    dumped = store.dump_markdown(store.load_all())
    assert "测试\\*词" in dumped
    assert "含义\\n# 另一段" in dumped
    assert "\n# 另一段" not in dumped
    assert "待确认" not in dumped


def test_cli_scan_is_read_only(capsys):
    store.upsert("faces", "哼", "不服气")
    path = store.domain_path("faces")
    before = open(path, "rb").read()
    assert cli.main(["scan", "哼"]) == 0
    assert "待确认的猜测" in capsys.readouterr().out
    assert open(path, "rb").read() == before


def test_cli_json_flag_works_after_subcommand(capsys):
    store.upsert("slang", "词", "猜测")
    assert cli.main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["key"] == "词"
    assert cli.main(["stats", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["open"] == 1


def test_cli_forget_removes_exact_key(capsys):
    store.upsert("slang", "测试词", "猜测")
    assert cli.main(["forget", "测试词"]) == 0
    assert "已删除" in capsys.readouterr().out
    assert store.load("slang") == []
