from unittest.mock import MagicMock
import pytest

from app.slack_ui import build_configure_modal
from app.openai_constants import (
    GPT_5_4_MODEL,
    GPT_5_4_MINI_MODEL,
    GPT_5_4_NANO_MODEL,
    GPT_5_5_MODEL,
    GPT_6_ASTRA_MODEL,
    GPT_6_SOL_MODEL,
    GPT_6_LUNA_MODEL,
    GPT_6_1_SOL_MODEL,
    GPT_5_6_SOL_MODEL,
    GPT_5_6_TERRA_MODEL,
    GPT_5_6_LUNA_MODEL,
    CHAT_LATEST_MODEL,
)


def make_context(
    *, api_key=None, model=None, function_module=None, api_type=None, api_base=None
):
    context = MagicMock()

    def _get(key, default=None):
        values = {
            "OPENAI_API_KEY": api_key,
            "OPENAI_MODEL": model,
            "OPENAI_API_TYPE": api_type,
            "OPENAI_API_BASE": api_base,
            "OPENAI_FUNCTION_CALL_MODULE_NAME": function_module,
        }
        return values.get(key, default)

    context.get.side_effect = _get
    return context


def test_build_configure_modal_includes_new_models():
    modal = build_configure_modal(make_context())

    options = modal["blocks"][1]["element"]["options"]
    values = [option["value"] for option in options]

    assert values[:13] == [
        GPT_5_6_SOL_MODEL,
        GPT_6_ASTRA_MODEL,
        GPT_6_SOL_MODEL,
        GPT_6_1_SOL_MODEL,
        GPT_6_LUNA_MODEL,
        GPT_5_6_TERRA_MODEL,
        GPT_5_6_LUNA_MODEL,
        GPT_5_5_MODEL,
        CHAT_LATEST_MODEL,
        GPT_5_4_MODEL,
        GPT_5_4_MINI_MODEL,
        GPT_5_4_NANO_MODEL,
        "gpt-5.2",
    ]


@pytest.mark.parametrize("saved_model", [GPT_6_1_SOL_MODEL, GPT_6_SOL_MODEL, None])
def test_configure_modal_filters_gpt_6_1_sol_with_functions(monkeypatch, saved_model):
    monkeypatch.setattr("app.slack_ui.translate", lambda *, text, **kwargs: text)
    modal = build_configure_modal(
        make_context(api_key="sk-test", model=saved_model, function_module="app.tools")
    )
    element = modal["blocks"][1]["element"]
    values = [option["value"] for option in element["options"]]
    assert GPT_6_1_SOL_MODEL not in values
    assert GPT_6_SOL_MODEL in values
    assert GPT_6_LUNA_MODEL in values
    if saved_model == GPT_6_1_SOL_MODEL:
        assert "initial_option" not in element
        assert not modal["blocks"][1].get("optional", False)
        assert (
            "Please choose another model" in modal["blocks"][2]["elements"][0]["text"]
        )
    else:
        assert len(modal["blocks"]) == 2
        assert element["initial_option"]["value"] == (
            GPT_6_SOL_MODEL if saved_model == GPT_6_SOL_MODEL else GPT_5_6_SOL_MODEL
        )


@pytest.mark.parametrize("translated_warning", [None, ""])
def test_configure_modal_preserves_warning_when_translation_is_empty(
    monkeypatch, translated_warning
):
    monkeypatch.setattr(
        "app.slack_ui.translate",
        lambda *, text, **kwargs: (
            translated_warning if text.startswith("GPT-6.1 Sol") else text
        ),
    )
    modal = build_configure_modal(
        make_context(
            api_key="sk-test", model=GPT_6_1_SOL_MODEL, function_module="app.tools"
        )
    )
    assert modal["blocks"][2]["elements"][0]["text"] == (
        "GPT-6.1 Sol cannot be used while tools are enabled. "
        "Please choose another model before submitting."
    )


def test_build_configure_modal_keeps_saved_model_selected(monkeypatch):
    monkeypatch.setattr(
        "app.slack_ui.translate",
        lambda *, text, **kwargs: text,
    )
    modal = build_configure_modal(make_context(api_key="sk-test", model=GPT_5_4_MODEL))

    initial_option = modal["blocks"][1]["element"]["initial_option"]

    assert initial_option["value"] == GPT_5_4_MODEL


@pytest.mark.parametrize(
    "model",
    [
        "gpt-5-chat-latest",
        "gpt-5.1-chat-latest",
        "gpt-5.2-chat-latest",
        "gpt-5.3-chat-latest",
        "o4-mini",
    ],
)
def test_configure_modal_requires_new_selection_for_retired_model(model):
    modal = build_configure_modal(
        make_context(
            api_key="sk-test", model=model, api_base="https://api.openai.com/v1/"
        )
    )

    element = modal["blocks"][1]["element"]
    values = [option["value"] for option in element["options"]]
    assert model not in values
    assert "o3" in values
    assert "initial_option" not in element
    assert not modal["blocks"][1].get("optional", False)
    assert f"OpenAI has retired {model}." in modal["blocks"][2]["elements"][0]["text"]


@pytest.mark.parametrize(
    "api_type,api_base",
    [
        ("azure", "https://demo.openai.azure.com"),
        (None, "https://other-provider.example/v1"),
    ],
)
def test_configure_modal_preserves_legacy_options_for_other_endpoints(
    api_type, api_base
):
    model = "gpt-5.3-chat-latest"
    modal = build_configure_modal(
        make_context(
            api_key="sk-test", model=model, api_type=api_type, api_base=api_base
        )
    )

    element = modal["blocks"][1]["element"]
    assert model in [option["value"] for option in element["options"]]
    assert element["initial_option"]["value"] == model
    assert len(modal["blocks"]) == 2
