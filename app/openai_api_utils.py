from typing import Optional, Dict, Union

from openai import OpenAI
from openai.lib.azure import AzureOpenAI


def is_reasoning_model(model: Optional[str]) -> bool:
    """Returns True if the model is a reasoning model under Chat Completions."""
    if not model:
        return False
    ml = model.lower()
    # Treat any gpt-5 family chat/search variants (including numbered updates)
    # as regular chat models so they keep sampling params.
    if ml.startswith("gpt-5") and ("-chat" in ml or "-search" in ml):
        return False
    return (
        ml.startswith("o1")
        or ml.startswith("o3")
        or ml.startswith("o4")
        or ml.startswith("gpt-5")
    )


def is_search_model(model: Optional[str]) -> bool:
    """Returns True for search-specific chat models."""
    if not model:
        return False
    return model.lower().startswith("gpt-5-search")


def normalize_base_url(value: Optional[str]) -> Optional[str]:
    """Normalizes falsy/empty base URLs to None for SDK compatibility."""
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def token_budget_kwarg(model: Optional[str], budget: int) -> Dict[str, int]:
    """Returns the correct token budget kwarg for the given model."""
    should_use_completion_tokens = (
        model and model.lower().startswith("gpt-5")
    ) or is_reasoning_model(model)

    return (
        {"max_completion_tokens": budget}
        if should_use_completion_tokens
        else {"max_tokens": budget}
    )


def sampling_kwargs(
    model: Optional[str], temperature: float
) -> Dict[str, Union[float, Dict]]:
    """Returns sampling-related kwargs supported by the given model."""
    ml = model.lower() if model else ""
    if is_reasoning_model(model) or is_search_model(model):
        return {}
    if ml.startswith(("gpt-5.1", "gpt-5.2", "gpt-5.3")):
        return {}
    return {
        "temperature": temperature,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "logit_bias": {},
        "top_p": 1,
    }


def build_openai_client(
    *,
    openai_api_key: str,
    openai_api_type: Optional[str],
    openai_api_base: Optional[str],
    openai_api_version: Optional[str],
    openai_deployment_id: Optional[str],
    openai_organization_id: Optional[str] = None,
) -> Union[OpenAI, AzureOpenAI]:
    if openai_api_type == "azure":
        return AzureOpenAI(
            api_key=openai_api_key,
            api_version=openai_api_version,
            azure_endpoint=openai_api_base,
            azure_deployment=openai_deployment_id,
        )
    return OpenAI(
        api_key=openai_api_key,
        base_url=normalize_base_url(openai_api_base),
        organization=openai_organization_id,
    )
