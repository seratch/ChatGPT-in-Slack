from unittest.mock import MagicMock

import pytest

import app.i18n as i18n
from app.openai_constants import GPT_4O_MINI_MODEL


@pytest.fixture(autouse=True)
def clear_translation_cache():
    i18n._translation_result_cache.clear()


def make_context(*, locale="zh-TW", api_type=None, api_base="https://api.example/v1"):
    context = MagicMock()

    def _get(key, default=None):
        values = {
            "locale": locale,
            "OPENAI_API_TYPE": api_type,
            "OPENAI_API_BASE": api_base,
            "OPENAI_API_VERSION": "2025-01-01",
            "OPENAI_DEPLOYMENT_ID": "dep-1",
        }
        return values.get(key, default)

    context.get.side_effect = _get
    return context


def test_translate_returns_original_text_without_api_key():
    text = "Translate me"

    assert (
        i18n.translate(openai_api_key=None, context=make_context(), text=text) == text
    )


def test_translate_returns_original_text_for_english_locale():
    text = "Translate me"

    assert (
        i18n.translate(
            openai_api_key="sk-test",
            context=make_context(locale="en-US"),
            text=text,
        )
        == text
    )


def test_translate_uses_configured_translation_model_and_caches(monkeypatch):
    captured = {"calls": 0, "kwargs": None}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["calls"] += 1
            captured["kwargs"] = kwargs
            return MagicMock(
                model_dump=lambda: {"choices": [{"message": {"content": "翻譯結果"}}]}
            )

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    monkeypatch.setattr(
        i18n,
        "build_openai_client",
        lambda **kwargs: FakeClient(),
    )

    context = make_context()
    first = i18n.translate(openai_api_key="sk-test", context=context, text="Hello")
    second = i18n.translate(openai_api_key="sk-test", context=context, text="Hello")

    assert first == "翻譯結果"
    assert second == "翻譯結果"
    assert captured["calls"] == 1
    assert captured["kwargs"]["model"] == GPT_4O_MINI_MODEL
    assert captured["kwargs"]["n"] == 1
    assert captured["kwargs"]["user"] == "system"
    assert captured["kwargs"]["max_tokens"] == 1024
    assert "max_completion_tokens" not in captured["kwargs"]
    assert captured["kwargs"]["temperature"] == 1
    assert captured["kwargs"]["top_p"] == 1
