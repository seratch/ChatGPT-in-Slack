from typing import Optional

from openai import OpenAI
from openai.lib.azure import AzureOpenAI
from slack_bolt import BoltContext

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


def translate(*, openai_api_key: Optional[str], context: BoltContext, text: str) -> str:
    if openai_api_key is None or len(openai_api_key.strip()) == 0:
        return text

    lang = from_locale_to_lang(context.get("locale"))
    if lang is None or lang == "English":
        return text

    cached_result = _translation_result_cache.get(f"{lang}:{text}")
    if cached_result is not None:
        return cached_result
    if context.get("OPENAI_API_TYPE") == "azure":
        client = AzureOpenAI(
            api_key=openai_api_key,
            api_version=context.get("OPENAI_API_VERSION"),
            azure_endpoint=context.get("OPENAI_API_BASE"),
            azure_deployment=context.get("OPENAI_DEPLOYMENT_ID"),
        )
    else:
        client = OpenAI(
            api_key=openai_api_key,
            base_url=context.get("OPENAI_API_BASE"),
        )
    response = client.chat.completions.create(
        model=GPT_4O_MINI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You're the AI model that primarily focuses on the quality of language translation. "
                "You always respond with the only the translated text in a format suitable for Slack user interface. "
                "Slack's emoji (e.g., :hourglass_flowing_sand:) and mention parts must be kept as-is. "
                "You don't change the meaning of sentences when translating them into a different language. "
                "When the given text is a single verb/noun, its translated text must be a norm/verb form too. "
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
        top_p=1,
        n=1,
        max_tokens=1024,
        temperature=1,
        presence_penalty=0,
        frequency_penalty=0,
        logit_bias={},
        user="system",
    )
    translated_text = response.model_dump()["choices"][0]["message"].get("content")
    _translation_result_cache[f"{lang}:{text}"] = translated_text
    return translated_text
