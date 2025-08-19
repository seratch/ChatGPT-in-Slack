import logging
import threading
import time
import re
import json
from typing import List, Dict, Tuple, Optional, Union
from importlib import import_module

from openai import OpenAI, Stream
from openai.lib.azure import AzureOpenAI
from openai.types import Completion
import tiktoken

from slack_bolt import BoltContext
from slack_sdk.web import WebClient, SlackResponse

from app.markdown_conversion import slack_to_markdown, markdown_to_slack
from app.openai_constants import (
    MAX_TOKENS,
    MODEL_TOKENS,
    MODEL_CONTEXT_LENGTHS,
    resolve_model_alias,
    DEFAULT_TOKEN_COUNT_MODEL,
)
from app.slack_ops import update_wip_message
from app.slack_constants import REASONING_EMPTY_OUTPUT_HINT

# Local budget for function-call prompt token estimation
FUNCTION_CALL_TOKEN_BUDGET = 1024

# ----------------------------
# Internal functions
# ----------------------------

_prompt_tokens_used_by_function_call_cache: Optional[int] = None


# Format message from Slack to send to OpenAI
def format_openai_message_content(
    content: str, translate_markdown: bool
) -> Optional[str]:
    if content is None:
        return None

    # Unescape &, < and >, since Slack replaces these with their HTML equivalents
    # See also: https://api.slack.com/reference/surfaces/formatting#escaping
    content = content.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

    # Convert from Slack mrkdwn to markdown format
    if translate_markdown:
        content = slack_to_markdown(content)

    return content


def messages_within_context_window(
    messages: List[Dict[str, Union[str, Dict[str, str]]]],
    context: BoltContext,
) -> Tuple[List[Dict[str, Union[str, Dict[str, str]]]], int, int]:
    # Remove old messages to make sure we have room for max_tokens
    # See also: https://platform.openai.com/docs/guides/chat/introduction
    # > total tokens must be below the model’s maximum limit (e.g., 4096 tokens for gpt-3.5-turbo-0301)
    max_context_tokens = context_length(context.get("OPENAI_MODEL")) - MAX_TOKENS - 1
    if context.get("OPENAI_FUNCTION_CALL_MODULE_NAME") is not None:
        max_context_tokens -= calculate_tokens_necessary_for_function_call(context)
    num_context_tokens = 0  # Number of tokens in the context window just before the earliest message is deleted
    while (
        num_tokens := calculate_num_tokens(messages, model=context.get("OPENAI_MODEL"))
    ) > max_context_tokens:
        removed = False
        for i, message in enumerate(messages):
            if message["role"] in ("user", "assistant", "function"):
                num_context_tokens = num_tokens
                del messages[i]
                removed = True
                break
        if not removed:
            # Fall through and let the OpenAI error handler deal with it
            break
    else:
        num_context_tokens = num_tokens

    return messages, num_context_tokens, max_context_tokens


def _is_reasoning(model: str) -> bool:
    """Returns True if the model is a reasoning model under Chat Completions.

    Excludes chat models like gpt-5-chat-latest. Matches o3*, o4*, and
    non-chat gpt-5* families. Case-insensitive and safe with None/empty.
    """
    if not model:
        return False
    ml = model.lower()
    if ml.startswith("gpt-5-chat"):
        return False
    return (
        ml.startswith("o1")
        or ml.startswith("o3")
        or ml.startswith("o4")
        or ml.startswith("gpt-5")
    )


def make_synchronous_openai_call(
    *,
    openai_api_key: str,
    model: str,
    temperature: float,
    messages: List[Dict[str, Union[str, Dict[str, str]]]],
    user: str,
    openai_api_type: str,
    openai_api_base: str,
    openai_api_version: str,
    openai_deployment_id: str,
    openai_organization_id: Optional[str],
    timeout_seconds: int,
) -> Completion:
    if openai_api_type == "azure":
        client = AzureOpenAI(
            api_key=openai_api_key,
            api_version=openai_api_version,
            azure_endpoint=openai_api_base,
            azure_deployment=openai_deployment_id,
        )
    else:
        client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            organization=openai_organization_id,
        )
    # Some reasoning models require max_completion_tokens instead of max_tokens

    token_kwarg = (
        {"max_completion_tokens": MAX_TOKENS}
        if _is_reasoning(model)
        else {"max_tokens": MAX_TOKENS}
    )

    base_kwargs = dict(
        model=model,
        messages=messages,
        top_p=1,
        n=1,
        user=user,
        stream=False,
        timeout=timeout_seconds,
    )
    if not _is_reasoning(model):
        base_kwargs["temperature"] = temperature
        base_kwargs["presence_penalty"] = 0
        base_kwargs["frequency_penalty"] = 0
        base_kwargs["logit_bias"] = {}
    return client.chat.completions.create(
        **base_kwargs,
        **token_kwarg,
    )


def start_receiving_openai_response(
    *,
    openai_api_key: str,
    model: str,
    temperature: float,
    messages: List[Dict[str, Union[str, Dict[str, str]]]],
    user: str,
    openai_api_type: str,
    openai_api_base: str,
    openai_api_version: str,
    openai_deployment_id: str,
    openai_organization_id: Optional[str],
    function_call_module_name: Optional[str],
) -> Stream[Completion]:
    kwargs = {}
    if function_call_module_name is not None:
        kwargs["functions"] = import_module(function_call_module_name).functions
    if openai_api_type == "azure":
        client = AzureOpenAI(
            api_key=openai_api_key,
            api_version=openai_api_version,
            azure_endpoint=openai_api_base,
            azure_deployment=openai_deployment_id,
        )
    else:
        client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
            organization=openai_organization_id,
        )

    token_kwarg = (
        {"max_completion_tokens": MAX_TOKENS}
        if _is_reasoning(model)
        else {"max_tokens": MAX_TOKENS}
    )

    base_kwargs = dict(
        model=model,
        messages=messages,
        top_p=1,
        n=1,
        user=user,
        stream=True,
    )
    if not _is_reasoning(model):
        base_kwargs["temperature"] = temperature
        base_kwargs["presence_penalty"] = 0
        base_kwargs["frequency_penalty"] = 0
        base_kwargs["logit_bias"] = {}
    return client.chat.completions.create(
        **base_kwargs,
        **token_kwarg,
        **kwargs,
    )


def consume_openai_stream_to_write_reply(
    *,
    client: WebClient,
    wip_reply: Union[dict, SlackResponse],
    context: BoltContext,
    user_id: str,
    messages: List[Dict[str, Union[str, Dict[str, str]]]],
    stream: Stream[Completion],
    timeout_seconds: int,
    translate_markdown: bool,
):
    start_time = time.time()
    assistant_reply: Dict[str, Union[str, Dict[str, str]]] = {
        "role": "assistant",
        "content": "",
    }
    messages.append(assistant_reply)
    word_count = 0
    threads = []
    function_call: Dict[str, str] = {"name": "", "arguments": ""}
    finish_reason: Optional[str] = None
    try:
        loading_character = " ... :writing_hand:"
        for chunk in stream:
            spent_seconds = time.time() - start_time
            if timeout_seconds < spent_seconds:
                raise TimeoutError()
            # Some versions of the Azure OpenAI API return an empty choices array in the first chunk
            if context.get("OPENAI_API_TYPE") == "azure" and not chunk.choices:
                continue
            item = chunk.choices[0].model_dump()
            if item.get("finish_reason") is not None:
                finish_reason = item.get("finish_reason")
                break
            delta = item.get("delta")
            if delta.get("content") is not None:
                word_count += 1
                assistant_reply["content"] += delta.get("content")
                if word_count >= 20:

                    def update_message():
                        assistant_reply_text = format_assistant_reply(
                            assistant_reply["content"], translate_markdown
                        )
                        wip_reply["message"]["text"] = assistant_reply_text
                        update_wip_message(
                            client=client,
                            channel=context.channel_id,
                            ts=wip_reply["message"]["ts"],
                            text=assistant_reply_text + loading_character,
                            messages=messages,
                            user=user_id,
                        )

                    thread = threading.Thread(target=update_message)
                    thread.daemon = True
                    thread.start()
                    threads.append(thread)
                    word_count = 0
            elif delta.get("function_call") is not None:
                # Ignore function call suggestions after content has been received
                if assistant_reply["content"] == "":
                    for k in function_call.keys():
                        function_call[k] += delta["function_call"].get(k) or ""
                    assistant_reply["function_call"] = function_call

        for t in threads:
            try:
                if t.is_alive():
                    t.join()
            except Exception:
                pass

        if function_call["name"] != "":
            function_call_module_name = context.get("OPENAI_FUNCTION_CALL_MODULE_NAME")
            function_call_module = import_module(function_call_module_name)
            function_to_call = getattr(function_call_module, function_call["name"])
            function_args = json.loads(function_call["arguments"])
            function_response = function_to_call(**function_args)
            function_message = {
                "role": "function",
                "name": function_call["name"],
                "content": function_response,
            }
            messages.append(function_message)
            messages_within_context_window(messages, context=context)
            sub_stream = start_receiving_openai_response(
                openai_api_key=context.get("OPENAI_API_KEY"),
                model=context.get("OPENAI_MODEL"),
                temperature=context.get("OPENAI_TEMPERATURE"),
                messages=messages,
                user=user_id,
                openai_api_type=context.get("OPENAI_API_TYPE"),
                openai_api_base=context.get("OPENAI_API_BASE"),
                openai_api_version=context.get("OPENAI_API_VERSION"),
                openai_deployment_id=context.get("OPENAI_DEPLOYMENT_ID"),
                openai_organization_id=context["OPENAI_ORG_ID"],
                function_call_module_name=function_call_module_name,
            )
            consume_openai_stream_to_write_reply(
                client=client,
                wip_reply=wip_reply,
                context=context,
                user_id=user_id,
                messages=messages,
                stream=sub_stream,
                timeout_seconds=int(timeout_seconds - (time.time() - start_time)),
                translate_markdown=translate_markdown,
            )
            return

        # Minimal feedback when reasoning consumed all completion tokens
        content_field = assistant_reply.get("content")
        content_text = content_field if isinstance(content_field, str) else ""
        if (
            content_text.strip() == ""
            and finish_reason == "length"
            and _is_reasoning(context.get("OPENAI_MODEL"))
        ):
            assistant_reply["content"] = REASONING_EMPTY_OUTPUT_HINT
        assistant_reply_text = format_assistant_reply(
            assistant_reply["content"], translate_markdown
        )
        wip_reply["message"]["text"] = assistant_reply_text
        update_wip_message(
            client=client,
            channel=context.channel_id,
            ts=wip_reply["message"]["ts"],
            text=assistant_reply_text,
            messages=messages,
            user=user_id,
        )
    finally:
        for t in threads:
            try:
                if t.is_alive():
                    t.join()
            except Exception:
                pass
        try:
            stream.close()
        except Exception:
            pass


def context_length(
    model: str,
) -> int:
    """Returns the context length for a given model."""
    actual_model = resolve_model_alias(model)
    length = MODEL_CONTEXT_LENGTHS.get(actual_model)
    if length is not None:
        return length

    error = f"Calculating the length of the context window for model {actual_model} is not yet supported."
    raise NotImplementedError(error)


def encode_and_count_tokens(
    value: Union[str, List[Dict[str, Union[str, Dict[str, str]]]], Dict[str, str]],
    encoding: tiktoken.Encoding,
) -> int:
    if isinstance(value, str):
        return len(encoding.encode(value))
    elif isinstance(value, list):
        return sum(encode_and_count_tokens(item, encoding) for item in value)
    elif isinstance(value, dict):
        return sum(
            encode_and_count_tokens(v, encoding)
            for k, v in value.items()
            if k != "image_url"
        )
    return 0


# Initially adapted from the following source code,
# and then we customized it to support broader use cases
# https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
def calculate_num_tokens(
    messages: List[Dict[str, Union[str, Dict[str, str], List[Dict[str, str]]]]],
    model: Optional[str] = None,
) -> int:
    """Returns the number of tokens used by a list of messages."""
    actual_model = resolve_model_alias(model or DEFAULT_TOKEN_COUNT_MODEL)
    try:
        encoding = tiktoken.encoding_for_model(actual_model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    model_tokens = MODEL_TOKENS.get(actual_model)
    if model_tokens is None:
        error = (
            f"Calculating the number of tokens for model {actual_model} is not yet supported. "
            "See https://github.com/openai/openai-python/blob/main/chatml.md "
            "for information on how messages are converted to tokens."
        )
        raise NotImplementedError(error)

    tokens_per_message, tokens_per_name = model_tokens

    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            if key == "function_call":
                num_tokens += (
                    1
                    + len(encoding.encode(value["name"]))
                    + len(encoding.encode(value["arguments"]))
                )
            else:
                num_tokens += encode_and_count_tokens(value, encoding)
            if key == "name":
                num_tokens += tokens_per_name

    num_tokens += 3  # every reply is primed with <|im_start|>assistant<|im_sep|>

    return num_tokens


# Format message from OpenAI to display in Slack
def format_assistant_reply(content: str, translate_markdown: bool) -> str:
    for o, n in [
        # Remove leading newlines
        ("^\n+", ""),
        # Remove prepended Slack user ID
        ("^<@U.*?>\\s?:\\s?", ""),
        # Remove OpenAI syntax tags since Slack doesn't render them in a message
        ("```\\s*[Rr]ust\n", "```\n"),
        ("```\\s*[Rr]uby\n", "```\n"),
        ("```\\s*[Ss]cala\n", "```\n"),
        ("```\\s*[Kk]otlin\n", "```\n"),
        ("```\\s*[Jj]ava\n", "```\n"),
        ("```\\s*[Gg]o\n", "```\n"),
        ("```\\s*[Ss]wift\n", "```\n"),
        ("```\\s*[Oo]objective[Cc]\n", "```\n"),
        ("```\\s*[Cc]\n", "```\n"),
        ("```\\s*[Cc][+][+]\n", "```\n"),
        ("```\\s*[Cc][Pp][Pp]\n", "```\n"),
        ("```\\s*[Cc]sharp\n", "```\n"),
        ("```\\s*[Mm][Aa][Tt][Ll][Aa][Bb]\n", "```\n"),
        ("```\\s*[Jj][Ss][Oo][Nn]\n", "```\n"),
        ("```\\s*[Ll]a[Tt]e[Xx]\n", "```\n"),
        ("```\\s*[Ll][Uu][Aa]\n", "```\n"),
        ("```\\s*[Cc][Mm][Aa][Kk][Ee]\n", "```\n"),
        ("```\\s*bash\n", "```\n"),
        ("```\\s*zsh\n", "```\n"),
        ("```\\s*sh\n", "```\n"),
        ("```\\s*[Ss][Qq][Ll]\n", "```\n"),
        ("```\\s*[Pp][Hh][Pp]\n", "```\n"),
        ("```\\s*[Pp][Ee][Rr][Ll]\n", "```\n"),
        ("```\\s*[Jj]ava[Ss]cript\n", "```\n"),
        ("```\\s*[Ty]ype[Ss]cript\n", "```\n"),
        ("```\\s*[Pp]ython\n", "```\n"),
    ]:
        content = re.sub(o, n, content)

    # Convert from OpenAI markdown to Slack mrkdwn format
    if translate_markdown:
        content = markdown_to_slack(content)

    return content


def build_system_text(
    system_text_template: str, translate_markdown: bool, context: BoltContext
):
    system_text = system_text_template.format(bot_user_id=context.bot_user_id)
    # Translate format hint in system prompt
    if translate_markdown is True:
        system_text = slack_to_markdown(system_text)
    return system_text


def calculate_tokens_necessary_for_function_call(context: BoltContext) -> int:
    """Calculates the estimated number of prompt tokens necessary for loading Function Call stuff"""
    function_call_module_name = context.get("OPENAI_FUNCTION_CALL_MODULE_NAME")
    if function_call_module_name is None:
        return 0

    global _prompt_tokens_used_by_function_call_cache
    if _prompt_tokens_used_by_function_call_cache is not None:
        return _prompt_tokens_used_by_function_call_cache

    def _calculate_prompt_tokens(functions) -> int:
        client = create_openai_client(context)
        model = context.get("OPENAI_MODEL")
        token_kwarg = (
            {"max_completion_tokens": FUNCTION_CALL_TOKEN_BUDGET}
            if _is_reasoning(model)
            else {"max_tokens": FUNCTION_CALL_TOKEN_BUDGET}
        )
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hello"}],
            user="system",
            **token_kwarg,
            **({"functions": functions} if functions is not None else {}),
        ).model_dump()["usage"]["prompt_tokens"]

    # TODO: If there is a better way to calculate this, replace the logic with it
    module = import_module(function_call_module_name)
    _prompt_tokens_used_by_function_call_cache = _calculate_prompt_tokens(
        module.functions
    ) - _calculate_prompt_tokens(None)
    return _prompt_tokens_used_by_function_call_cache


def generate_slack_thread_summary(
    *,
    context: BoltContext,
    logger: logging.Logger,
    openai_api_key: str,
    prompt: str,
    thread_content: str,
    timeout_seconds: int,
) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You're an assistant tasked with helping Slack users by summarizing threads. "
                "You'll receive a collection of replies in this format: <@user_id>: reply text\n"
                "Your role is to provide a concise summary that highlights key facts and decisions. "
                "If the first line of a user's request is in a non-English language, "
                "please summarize in that same language. "
                "Lastly, please prioritize speed of generation over perfection."
            ),
        },
        {
            "role": "user",
            "content": f"{prompt}\n\n{thread_content}",
        },
    ]
    start_time = time.time()
    openai_response = make_synchronous_openai_call(
        openai_api_key=openai_api_key,
        model=context["OPENAI_MODEL"],
        temperature=context["OPENAI_TEMPERATURE"],
        messages=messages,
        user=context.actor_user_id,
        openai_api_type=context["OPENAI_API_TYPE"],
        openai_api_base=context["OPENAI_API_BASE"],
        openai_api_version=context["OPENAI_API_VERSION"],
        openai_deployment_id=context["OPENAI_DEPLOYMENT_ID"],
        openai_organization_id=context["OPENAI_ORG_ID"],
        timeout_seconds=timeout_seconds,
    )
    spent_time = time.time() - start_time
    logger.debug(f"Making a summary took {spent_time} seconds")
    data = openai_response.model_dump()
    choice = data["choices"][0]
    content = (choice["message"].get("content") or "").strip()
    if (
        content == ""
        and choice.get("finish_reason") == "length"
        and _is_reasoning(context.get("OPENAI_MODEL"))
    ):
        return REASONING_EMPTY_OUTPUT_HINT
    return content


def generate_proofreading_result(
    *,
    context: BoltContext,
    logger: logging.Logger,
    openai_api_key: str,
    original_text: str,
    tone_and_voice: Optional[str] = None,
    timeout_seconds: int,
) -> str:
    system_content = (
        "You're an assistant tasked with helping Slack users by proofreading a given text. "
        "Your task is to enhance the quality of the sentences provided "
        "without altering their original meaning as far as possible. "
    )
    if tone_and_voice is not None:
        system_content += (
            f"The generated output must be a suitable one for {tone_and_voice}. "
        )
    system_content += "Lastly, generating results swiftly should be prioritized over achieving perfection."

    messages = [
        {
            "role": "system",
            "content": system_content,
        },
        {
            "role": "user",
            "content": "Please proofread my written work, which starts after '!!!' "
            "I'll provide a text input which might be in a non-English language. "
            "Ensure that the proofread result is in the same language. "
            "Even if you consider annotating the proofread text, kindly withhold it. "
            f"Here is the input !!!\n{original_text}",
        },
    ]
    start_time = time.time()
    openai_response = make_synchronous_openai_call(
        openai_api_key=openai_api_key,
        model=context["OPENAI_MODEL"],
        temperature=context["OPENAI_TEMPERATURE"],
        messages=messages,
        user=context.actor_user_id,
        openai_api_type=context["OPENAI_API_TYPE"],
        openai_api_base=context["OPENAI_API_BASE"],
        openai_api_version=context["OPENAI_API_VERSION"],
        openai_deployment_id=context["OPENAI_DEPLOYMENT_ID"],
        openai_organization_id=context["OPENAI_ORG_ID"],
        timeout_seconds=timeout_seconds,
    )
    spent_time = time.time() - start_time
    logger.debug(f"Proofreading took {spent_time} seconds")
    data = openai_response.model_dump()
    choice = data["choices"][0]
    content = (choice["message"].get("content") or "").strip()
    if (
        content == ""
        and choice.get("finish_reason") == "length"
        and _is_reasoning(context.get("OPENAI_MODEL"))
    ):
        return REASONING_EMPTY_OUTPUT_HINT
    return content


def generate_chatgpt_response(
    *,
    context: BoltContext,
    logger: logging.Logger,
    openai_api_key: str,
    prompt: str,
    timeout_seconds: int,
) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You're an assistant tasked with helping Slack users by responding to a given prompt. "
                "If the first line of a user's request is in a non-English language, "
                "please provide its result in that same language. "
                "Lastly, please prioritize speed of generation over perfection."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    start_time = time.time()
    openai_response = make_synchronous_openai_call(
        openai_api_key=openai_api_key,
        model=context["OPENAI_MODEL"],
        temperature=context["OPENAI_TEMPERATURE"],
        messages=messages,
        user=context.actor_user_id,
        openai_api_type=context["OPENAI_API_TYPE"],
        openai_api_base=context["OPENAI_API_BASE"],
        openai_api_version=context["OPENAI_API_VERSION"],
        openai_deployment_id=context["OPENAI_DEPLOYMENT_ID"],
        openai_organization_id=context["OPENAI_ORG_ID"],
        timeout_seconds=timeout_seconds,
    )
    spent_time = time.time() - start_time
    logger.debug(f"Proofreading took {spent_time} seconds")
    data = openai_response.model_dump()
    choice = data["choices"][0]
    content = (choice["message"].get("content") or "").strip()
    if (
        content == ""
        and choice.get("finish_reason") == "length"
        and _is_reasoning(context.get("OPENAI_MODEL"))
    ):
        return REASONING_EMPTY_OUTPUT_HINT
    return content


def create_openai_client(context: BoltContext) -> Union[OpenAI, AzureOpenAI]:
    if context.get("OPENAI_API_TYPE") == "azure":
        return AzureOpenAI(
            api_key=context.get("OPENAI_API_KEY"),
            api_version=context.get("OPENAI_API_VERSION"),
            azure_endpoint=context.get("OPENAI_API_BASE"),
            azure_deployment=context.get("OPENAI_DEPLOYMENT_ID"),
        )
    else:
        return OpenAI(
            api_key=context.get("OPENAI_API_KEY"),
            base_url=context.get("OPENAI_API_BASE"),
        )
