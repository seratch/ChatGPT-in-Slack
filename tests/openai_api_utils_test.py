import pytest

import app.openai_api_utils as api_utils


def test_azure_v1_base_url():
    assert (
        api_utils.azure_v1_base_url("https://example.openai.azure.com")
        == "https://example.openai.azure.com/openai/v1/"
    )
    assert (
        api_utils.azure_v1_base_url("https://example.openai.azure.com/openai/v1/")
        == "https://example.openai.azure.com/openai/v1/"
    )


@pytest.mark.parametrize("base_url", [None, "", "https://api.openai.com/v1"])
def test_azure_v1_base_url_requires_azure_resource(base_url):
    with pytest.raises(ValueError, match="OPENAI_API_BASE"):
        api_utils.azure_v1_base_url(base_url)


def test_request_model_uses_azure_deployment():
    assert api_utils.request_model("gpt-4o", None, "deployment") == "gpt-4o"
    assert api_utils.request_model("gpt-4o", "azure", "deployment") == "deployment"
    assert api_utils.request_model("gpt-4o", "azure", None) == "gpt-4o"


def test_sampling_and_token_budget_for_gpt_4o_mini():
    token_kwargs = api_utils.token_budget_kwarg("gpt-4o-mini", 1024)
    sampling = api_utils.sampling_kwargs("gpt-4o-mini", 0.75)

    assert token_kwargs == {"max_tokens": 1024}
    assert sampling == {
        "temperature": 0.75,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "logit_bias": {},
        "top_p": 1,
    }


def test_sampling_and_token_budget_for_gpt_5_4_nano():
    token_kwargs = api_utils.token_budget_kwarg("gpt-5.4-nano", 1024)
    sampling = api_utils.sampling_kwargs("gpt-5.4-nano", 0.75)

    assert token_kwargs == {"max_completion_tokens": 1024}
    assert sampling == {}


def test_sampling_and_token_budget_for_gpt_5_5():
    token_kwargs = api_utils.token_budget_kwarg("gpt-5.5", 1024)
    sampling = api_utils.sampling_kwargs("gpt-5.5", 0.75)

    assert token_kwargs == {"max_completion_tokens": 1024}
    assert sampling == {}


def test_sampling_and_token_budget_for_gpt_5_6_models():
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        token_kwargs = api_utils.token_budget_kwarg(model, 1024)
        sampling = api_utils.sampling_kwargs(model, 0.75)

        assert token_kwargs == {"max_completion_tokens": 1024}
        assert sampling == {}


def test_reasoning_effort_for_gpt_5_6_luna():
    assert api_utils.reasoning_effort_kwargs("gpt-5.6-luna") == {
        "reasoning_effort": "none"
    }
    assert api_utils.reasoning_effort_kwargs("gpt-5.6-luna", function_calling=True) == {
        "reasoning_effort": "low"
    }
    assert api_utils.reasoning_effort_kwargs(
        "gpt-5.6-luna", function_calling=True, openai_api_type="azure"
    ) == {"reasoning_effort": "none"}
    assert api_utils.reasoning_effort_kwargs("gpt-5.6-terra") == {}
    assert api_utils.reasoning_effort_kwargs("gpt-4o-mini") == {}


def test_sampling_and_token_budget_for_chat_latest():
    token_kwargs = api_utils.token_budget_kwarg("chat-latest", 1024)
    sampling = api_utils.sampling_kwargs("chat-latest", 0.75)

    assert token_kwargs == {"max_completion_tokens": 1024}
    assert sampling == {}
