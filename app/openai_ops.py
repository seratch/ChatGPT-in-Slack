import threading
import time
import re
from typing import List, Dict, Any, Generator, Tuple

import openai
from openai.error import Timeout
from openai.openai_object import OpenAIObject
import tiktoken

from slack_bolt import BoltContext
from slack_sdk.web import WebClient

from app.markdown import slack_to_markdown, markdown_to_slack
from app.slack_ops import update_wip_message

# ----------------------------
# Internal functions
# ----------------------------

MAX_TOKENS = 1024
GPT_3_5_TURBO_MODEL = "gpt-3.5-turbo"
GPT_3_5_TURBO_0301_MODEL = "gpt-3.5-turbo-0301"
GPT_3_5_TURBO_0613_MODEL = "gpt-3.5-turbo-0613"
GPT_3_5_TURBO_16K_MODEL = "gpt-3.5-turbo-16k"
GPT_3_5_TURBO_16K_0613_MODEL = "gpt-3.5-turbo-16k-0613"
GPT_4_MODEL = "gpt-4"
GPT_4_0314_MODEL = "gpt-4-0314"
GPT_4_0613_MODEL = "gpt-4-0613"
GPT_4_32K_MODEL = "gpt-4-32k"
GPT_4_32K_0314_MODEL = "gpt-4-32k-0314"
GPT_4_32K_0613_MODEL = "gpt-4-32k-0613"


# Format message from Slack to send to OpenAI
def format_openai_message_content(content: str, translate_markdown: bool) -> str:
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
    messages: List[Dict[str, str]],
    model: str,
) -> Tuple[List[Dict[str, str]], int, int]:
    # Remove old messages to make sure we have room for max_tokens
    # See also: https://platform.openai.com/docs/guides/chat/introduction
    # > total tokens must be below the model’s maximum limit (e.g., 4096 tokens for gpt-3.5-turbo-0301)
    max_context_tokens = context_length(model) - MAX_TOKENS - 1
    num_context_tokens = 0  # Number of tokens in the context window just before the earliest message is deleted
    while (num_tokens := calculate_num_tokens(messages)) > max_context_tokens:
        removed = False
        for i, message in enumerate(messages):
            if message["role"] in ("user", "assistant"):
                num_context_tokens = num_tokens
                del messages[i]
                removed = True
                break
        if not removed:
            # Fall through and let the OpenAI error handler deal with it
            break
    return messages, num_context_tokens, max_context_tokens


def start_receiving_openai_response(
    *,
    openai_api_key: str,
    model: str,
    temperature: float,
    messages: List[Dict[str, str]],
    user: str,
    openai_api_type: str,
    openai_api_base: str,
    openai_api_version: str,
    openai_deployment_id: str,
) -> Generator[OpenAIObject, Any, None]:
    return openai.ChatCompletion.create(
        api_key=openai_api_key,
        model=model,
        messages=messages,
        top_p=1,
        n=1,
        max_tokens=MAX_TOKENS,
        temperature=temperature,
        presence_penalty=0,
        frequency_penalty=0,
        logit_bias={},
        user=user,
        stream=True,
        api_type=openai_api_type,
        api_base=openai_api_base,
        api_version=openai_api_version,
        deployment_id=openai_deployment_id,
    )


def consume_openai_stream_to_write_reply(
    *,
    client: WebClient,
    wip_reply: dict,
    context: BoltContext,
    user_id: str,
    messages: List[Dict[str, str]],
    stream: Generator[OpenAIObject, Any, None],
    timeout_seconds: int,
    translate_markdown: bool,
):
    start_time = time.time()
    assistant_reply: Dict[str, str] = {"role": "assistant", "content": ""}
    messages.append(assistant_reply)
    word_count = 0
    threads = []
    try:
        loading_character = " ... :writing_hand:"
        for chunk in stream:
            spent_seconds = time.time() - start_time
            if timeout_seconds < spent_seconds:
                raise Timeout()
            item = chunk.choices[0]
            if item.get("finish_reason") is not None:
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

        for t in threads:
            try:
                if t.is_alive():
                    t.join()
            except Exception:
                pass

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
    if model == GPT_3_5_TURBO_MODEL:
        # Note that GPT_3_5_TURBO_MODEL may change over time. Return context length assuming GPT_3_5_TURBO_0613_MODEL.
        return context_length(model=GPT_3_5_TURBO_0613_MODEL)
    if model == GPT_3_5_TURBO_16K_MODEL:
        # Note that GPT_3_5_TURBO_16K_MODEL may change over time. Return context length assuming GPT_3_5_TURBO_16K_0613_MODEL.
        return context_length(model=GPT_3_5_TURBO_16K_0613_MODEL)
    elif model == GPT_4_MODEL:
        # Note that GPT_4_MODEL may change over time. Return context length assuming GPT_4_0613_MODEL.
        return context_length(model=GPT_4_0613_MODEL)
    elif model == GPT_4_32K_MODEL:
        # Note that GPT_4_32K_MODEL may change over time. Return context length assuming GPT_4_32K_0613_MODEL.
        return context_length(model=GPT_4_32K_0613_MODEL)
    elif model == GPT_3_5_TURBO_0301_MODEL or model == GPT_3_5_TURBO_0613_MODEL:
        return 4096
    elif model == GPT_3_5_TURBO_16K_0613_MODEL:
        return 16384
    elif model == GPT_4_0314_MODEL or model == GPT_4_0613_MODEL:
        return 8192
    elif model == GPT_4_32K_0314_MODEL or model == GPT_4_32K_0613_MODEL:
        return 32768
    else:
        error = f"Calculating the length of the context window for model {model} is not yet supported."
        raise NotImplementedError(error)


def calculate_num_tokens(
    messages: List[Dict[str, str]],
    model: str = GPT_3_5_TURBO_0301_MODEL,
) -> int:
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == GPT_3_5_TURBO_MODEL:
        # Note that GPT_3_5_TURBO_MODEL may change over time. Return num tokens assuming GPT_3_5_TURBO_0613_MODEL.
        return calculate_num_tokens(messages, model=GPT_3_5_TURBO_0613_MODEL)
    if model == GPT_3_5_TURBO_16K_MODEL:
        # Note that GPT_3_5_TURBO_16K_MODEL may change over time. Return num tokens assuming GPT_3_5_TURBO_16K_0613_MODEL.
        return calculate_num_tokens(messages, model=GPT_3_5_TURBO_16K_0613_MODEL)
    elif model == GPT_4_MODEL:
        # Note that GPT_4_MODEL may change over time. Return num tokens assuming GPT_4_0613_MODEL.
        return calculate_num_tokens(messages, model=GPT_4_0613_MODEL)
    elif model == GPT_4_32K_MODEL:
        # Note that GPT_4_32K_MODEL may change over time. Return num tokens assuming GPT_4_32K_0613_MODEL.
        return calculate_num_tokens(messages, model=GPT_4_32K_0613_MODEL)
    elif (
        model == GPT_3_5_TURBO_0301_MODEL
        or model == GPT_3_5_TURBO_0613_MODEL
        or model == GPT_3_5_TURBO_16K_0613_MODEL
    ):
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif (
        model == GPT_4_0314_MODEL
        or model == GPT_4_0613_MODEL
        or model == GPT_4_32K_0314_MODEL
        or model == GPT_4_32K_0613_MODEL
    ):
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        error = (
            f"Calculating the number of tokens for model {model} is not yet supported. "
            "See https://github.com/openai/openai-python/blob/main/chatml.md "
            "for information on how messages are converted to tokens."
        )
        raise NotImplementedError(error)
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
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
