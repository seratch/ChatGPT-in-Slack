from typing import Optional

from slack_bolt import BoltContext

from .openai_api_utils import (
    build_openai_client,
    is_search_model,
    sampling_kwargs,
    token_budget_kwarg,
)
from .openai_constants import GPT_4O_MINI_MODEL

# All the supported languages for Slack app as of March 2023
_locale_to_lang = {
    "en-US": "English",
    "en-GB": "English",
    "de-DE": "German",
    "es-ES": "Spanish",
    "es-LA": "Spanish",
    "fr-FR": "French",
    "it-IT": "Italian",
    "pt-BR": "Portuguese",
    "ru-RU": "Russian",
    "ja-JP": "Japanese",
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ko-KR": "Korean",
}


def from_locale_to_lang(locale: Optional[str]) -> Optional[str]:
    if locale is None:
        return None
    return _locale_to_lang.get(locale)


_translation_result_cache = {}
TRANSLATION_MODEL = GPT_4O_MINI_MODEL
TRANSLATION_TEMPERATURE = 1
TRANSLATION_TOKEN_BUDGET = 1024


def translate(*, openai_api_key: Optional[str], context: BoltContext, text: str) -> str:
    if openai_api_key is None or len(openai_api_key.strip()) == 0:
        return text

    lang = from_locale_to_lang(context.get("locale"))
    if lang is None or lang == "English":
        return text

    cached_result = _translation_result_cache.get(f"{lang}:{text}")
    if cached_result is not None:
        return cached_result
    client = build_openai_client(
        openai_api_key=openai_api_key,
        openai_api_type=context.get("OPENAI_API_TYPE"),
        openai_api_base=context.get("OPENAI_API_BASE"),
        openai_api_version=context.get("OPENAI_API_VERSION"),
        openai_deployment_id=context.get("OPENAI_DEPLOYMENT_ID"),
    )
    request_kwargs = {
        "model": TRANSLATION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You're the AI model that primarily focuses on the quality of language translation. "
                "You always respond with only the translated text in a format suitable for Slack user interface. "
                "Slack's emoji (e.g., :hourglass_flowing_sand:) and mention parts must be kept as-is. "
                "You don't change the meaning of sentences when translating them into a different language. "
                "When the given text is a single verb/noun, its translated text must be a noun/verb form too. "
                "When the given text is in markdown format, the format must be kept as much as possible. ",
            },
            {
                "role": "user",
                "content": f"Can you translate the following text into {lang} in a professional tone? "
                "Your response must omit any English version / pronunciation guide for the result. "
                "Again, no need to append any English notes and guides about the result. "
                "Just return the translation result. "
                f"Here is the original sentence you need to translate:\n{text}",
            },
        ],
        "user": "system",
    }
    if not is_search_model(TRANSLATION_MODEL):
        request_kwargs["n"] = 1
    request_kwargs.update(
        token_budget_kwarg(TRANSLATION_MODEL, TRANSLATION_TOKEN_BUDGET)
    )
    request_kwargs.update(sampling_kwargs(TRANSLATION_MODEL, TRANSLATION_TEMPERATURE))
    response = client.chat.completions.create(
        **request_kwargs,
    )
    translated_text = response.model_dump()["choices"][0]["message"].get("content")
    _translation_result_cache[f"{lang}:{text}"] = translated_text
    return translated_text
