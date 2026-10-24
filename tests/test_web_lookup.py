"""Web lookup must stay read-only and treat search results as unverified clues."""

import json
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from moqi.core import web_lookup  # noqa: E402


def test_missing_key_makes_no_network_request(monkeypatch):
    monkeypatch.delenv("MOQI_BRAVE_API_KEY", raising=False)
    monkeypatch.setattr(web_lookup, "urlopen", lambda *args, **kwargs: pytest.fail("unexpected network"))
    result = web_lookup.research("我了个雷", "火影忍者手游")
    assert result["configured"] is False
    assert result["results"] == []


def test_search_returns_bounded_unverified_clues(monkeypatch):
    monkeypatch.setenv("MOQI_BRAVE_API_KEY", "test-token")
    payload = {"web": {"results": [
        {"title": "视频", "url": "https://example.org/video", "description": "玩家讨论"}
    ]}}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, *_args):
            return json.dumps(payload).encode("utf-8")

    def fake_open(request, timeout):
        assert timeout == 8
        assert request.get_header("X-subscription-token") == "test-token"
        query = parse_qs(urlparse(request.full_url).query)
        assert query["q"] == ['"我了个雷" 火影忍者手游 原话 出处']
        assert query["count"] == ["5"]
        return Response()

    monkeypatch.setattr(web_lookup, "urlopen", fake_open)
    result = web_lookup.research("我了个雷", "火影忍者手游")
    assert result["ok"] is True
    assert result["results"][0]["url"] == "https://example.org/video"
    assert "未核对" in result["hint"]
    assert "truth" not in result


@pytest.mark.parametrize("term,topic", [("", "游戏"), ("词\n注入", ""), ("词", "x" * 101)])
def test_invalid_search_input_is_rejected(term, topic):
    with pytest.raises(ValueError):
        web_lookup.research(term, topic)
