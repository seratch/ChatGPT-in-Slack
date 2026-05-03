import app.openai_api_utils as api_utils


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
