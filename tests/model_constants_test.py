import pytest
from app.openai_constants import (
    resolve_model_alias,
    MODEL_FALLBACKS,
    MODEL_TOKENS,
    MODEL_CONTEXT_LENGTHS,
    CHAT_LATEST_MODEL,
    GPT_4_MODEL,
    GPT_4_0613_MODEL,
    GPT_5_1_MODEL,
    GPT_5_1_2025_11_13_MODEL,
    GPT_5_2_MODEL,
    GPT_5_2_2025_12_11_MODEL,
    GPT_5_4_MODEL,
    GPT_5_4_MINI_MODEL,
    GPT_5_4_NANO_MODEL,
    GPT_5_4_2026_03_05_MODEL,
    GPT_5_4_MINI_2026_03_17_MODEL,
    GPT_5_4_NANO_2026_03_17_MODEL,
    GPT_5_5_MODEL,
    GPT_5_5_2026_04_23_MODEL,
    GPT_5_6_MODEL,
    GPT_5_6_SOL_MODEL,
    GPT_5_6_TERRA_MODEL,
    GPT_5_6_LUNA_MODEL,
)

def test_alias_resolution():
    """Tests that a model alias resolves to its specific version."""
    assert resolve_model_alias(GPT_4_MODEL) == GPT_4_0613_MODEL


def test_gpt_5_1_alias_resolution():
    """Ensures the GPT-5.1 alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_1_MODEL) == GPT_5_1_2025_11_13_MODEL

def test_gpt_5_2_alias_resolution():
    """Ensures the GPT-5.2 alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_2_MODEL) == GPT_5_2_2025_12_11_MODEL

def test_gpt_5_4_alias_resolution():
    """Ensures the GPT-5.4 alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_4_MODEL) == GPT_5_4_2026_03_05_MODEL

def test_gpt_5_4_mini_alias_resolution():
    """Ensures the GPT-5.4-mini alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_4_MINI_MODEL) == GPT_5_4_MINI_2026_03_17_MODEL

def test_gpt_5_4_nano_alias_resolution():
    """Ensures the GPT-5.4-nano alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_4_NANO_MODEL) == GPT_5_4_NANO_2026_03_17_MODEL

def test_gpt_5_5_alias_resolution():
    """Ensures the GPT-5.5 alias resolves to the dated release."""
    assert resolve_model_alias(GPT_5_5_MODEL) == GPT_5_5_2026_04_23_MODEL


def test_gpt_5_6_model_support():
    """Ensures GPT-5.6 aliases and model metadata are registered."""
    from app.openai_ops import calculate_num_tokens, context_length

    gpt_5_6_models = (
        GPT_5_6_SOL_MODEL,
        GPT_5_6_TERRA_MODEL,
        GPT_5_6_LUNA_MODEL,
    )

    assert resolve_model_alias(GPT_5_6_MODEL) == GPT_5_6_SOL_MODEL
    assert MODEL_FALLBACKS[GPT_5_6_MODEL] == GPT_5_6_SOL_MODEL
    assert context_length(GPT_5_6_MODEL) == 272000
    for model in gpt_5_6_models:
        assert resolve_model_alias(model) == model
        assert MODEL_TOKENS[model] == (3, 1)
        assert MODEL_CONTEXT_LENGTHS[model] == 272000
        assert context_length(model) == 272000
        assert calculate_num_tokens(
            messages=[{"role": "user", "content": "hello"}],
            model=model,
        ) > 0


def test_chat_latest_model_support():
    """Ensures chat-latest has direct token and context definitions."""
    from app.openai_ops import calculate_num_tokens, context_length

    assert resolve_model_alias(CHAT_LATEST_MODEL) == CHAT_LATEST_MODEL
    assert CHAT_LATEST_MODEL not in MODEL_FALLBACKS
    assert MODEL_TOKENS[CHAT_LATEST_MODEL] == (3, 1)
    assert MODEL_CONTEXT_LENGTHS[CHAT_LATEST_MODEL] == 400000
    assert context_length(CHAT_LATEST_MODEL) == 400000
    assert calculate_num_tokens(
        messages=[{"role": "user", "content": "hello"}],
        model=CHAT_LATEST_MODEL,
    ) > 0

def test_unregistered_model_fails():
    """Tests that resolving an unregistered model raises NotImplementedError."""
    # First, test the resolver
    unregistered_model = "this-model-does-not-exist"
    assert resolve_model_alias(unregistered_model) == unregistered_model

    # Then, test the functions that use the resolver
    from app.openai_ops import context_length, calculate_num_tokens
    with pytest.raises(NotImplementedError):
        context_length(unregistered_model)
    with pytest.raises(NotImplementedError):
        calculate_num_tokens(messages=[], model=unregistered_model)

def test_circular_fallback_fails(monkeypatch):
    """Tests that a circular dependency in fallbacks raises a ValueError."""
    # Temporarily introduce a circular dependency for testing
    monkeypatch.setitem(MODEL_FALLBACKS, "model_a", "model_b")
    monkeypatch.setitem(MODEL_FALLBACKS, "model_b", "model_a")

    with pytest.raises(ValueError, match="Circular dependency detected"):
        resolve_model_alias("model_a")

def test_model_coverage():
    """
    Tests that all models in FALLBACKS can be resolved to a model
    with defined tokens and context length.
    """
    for alias in MODEL_FALLBACKS.keys():
        try:
            resolved_model = resolve_model_alias(alias)
            assert resolved_model in MODEL_TOKENS
            assert resolved_model in MODEL_CONTEXT_LENGTHS
        except Exception as e:
            pytest.fail(f"Failed to resolve or find definitions for model alias {alias}: {e}")


def test_gpt_6_model_support():
    from app.openai_constants import (
        GPT_6_ASTRA_MODEL,
        GPT_6_SOL_MODEL,
        GPT_6_LUNA_MODEL,
    )
    from app.openai_ops import calculate_num_tokens, context_length

    for model in (GPT_6_ASTRA_MODEL, GPT_6_SOL_MODEL, GPT_6_LUNA_MODEL):
        assert resolve_model_alias(model) == model
        assert MODEL_TOKENS[model] == (3, 1)
        assert MODEL_CONTEXT_LENGTHS[model] == 272000
        assert context_length(model) == 272000
        assert (
            calculate_num_tokens(
                messages=[{"role": "user", "content": "hello"}], model=model
            )
            > 0
        )
