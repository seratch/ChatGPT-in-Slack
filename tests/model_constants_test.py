import pytest
from app.openai_constants import (
    resolve_model_alias,
    MODEL_FALLBACKS,
    MODEL_TOKENS,
    MODEL_CONTEXT_LENGTHS,
    GPT_4_MODEL,
    GPT_4_0613_MODEL,
)

def test_alias_resolution():
    """Tests that a model alias resolves to its specific version."""
    assert resolve_model_alias(GPT_4_MODEL) == GPT_4_0613_MODEL

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
