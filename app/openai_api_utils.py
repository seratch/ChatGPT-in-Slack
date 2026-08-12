from typing import Optional, Dict, Union

from openai import OpenAI


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


def azure_v1_base_url(value: Optional[str]) -> str:
    """Returns an Azure OpenAI v1 base URL for the configured resource."""
    base_url = normalize_base_url(value)
    if base_url is None or base_url.rstrip("/") == "https://api.openai.com/v1":
        raise ValueError(
            "OPENAI_API_BASE must be set to an Azure OpenAI resource endpoint"
        )
    base_url = base_url.rstrip("/")
    if base_url.endswith("/openai/v1"):
        return f"{base_url}/"
    return f"{base_url}/openai/v1/"


def request_model(
    model: str,
    openai_api_type: Optional[str],
    openai_deployment_id: Optional[str],
) -> str:
    """Returns the model or Azure deployment name used by the request."""
    if openai_api_type == "azure" and openai_deployment_id:
        return openai_deployment_id
    return model


def token_budget_kwarg(model: Optional[str], budget: int) -> Dict[str, int]:
    """Returns the correct token budget kwarg for the given model."""
    should_use_completion_tokens = (
        model == "chat-latest" or (model and model.lower().startswith("gpt-5"))
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
    if model == "chat-latest" or ml.startswith(("gpt-5.1", "gpt-5.2", "gpt-5.3")):
        return {}
    return {
        "temperature": temperature,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "logit_bias": {},
        "top_p": 1,
    }


def reasoning_effort_kwargs(
    model: Optional[str],
    *,
    function_calling: bool = False,
    openai_api_type: Optional[str] = None,
) -> Dict[str, str]:
    """Returns compatible low-latency reasoning settings for Luna requests."""
    if model and model.lower() == "gpt-5.6-luna":
        effort = "low" if function_calling and openai_api_type != "azure" else "none"
        return {"reasoning_effort": effort}
    return {}


def build_openai_client(
    *,
    openai_api_key: str,
    openai_api_type: Optional[str],
    openai_api_base: Optional[str],
    openai_organization_id: Optional[str] = None,
) -> OpenAI:
    if openai_api_type == "azure":
        return OpenAI(
            api_key=openai_api_key,
            base_url=azure_v1_base_url(openai_api_base),
        )
    return OpenAI(
        api_key=openai_api_key,
        base_url=normalize_base_url(openai_api_base),
        organization=openai_organization_id,
    )
