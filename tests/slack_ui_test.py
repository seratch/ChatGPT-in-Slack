from unittest.mock import MagicMock

from app.slack_ui import build_configure_modal
from app.openai_constants import (
    GPT_5_3_CHAT_LATEST_MODEL,
    GPT_5_4_MODEL,
)


def make_context(*, api_key=None, model=None):
    context = MagicMock()

    def _get(key, default=None):
        values = {
            "OPENAI_API_KEY": api_key,
            "OPENAI_MODEL": model,
        }
        return values.get(key, default)

    context.get.side_effect = _get
    return context


def test_build_configure_modal_includes_new_models():
    modal = build_configure_modal(make_context())

    options = modal["blocks"][1]["element"]["options"]
    values = [option["value"] for option in options]

    assert values[:4] == [
        GPT_5_4_MODEL,
        GPT_5_3_CHAT_LATEST_MODEL,
        "gpt-5.2-chat-latest",
        "gpt-5.2",
    ]


def test_build_configure_modal_keeps_saved_model_selected(monkeypatch):
    monkeypatch.setattr(
        "app.slack_ui.translate",
        lambda *, text, **kwargs: text,
    )
    modal = build_configure_modal(
        make_context(api_key="sk-test", model=GPT_5_3_CHAT_LATEST_MODEL)
    )

    initial_option = modal["blocks"][1]["element"]["initial_option"]

    assert initial_option["value"] == GPT_5_3_CHAT_LATEST_MODEL
