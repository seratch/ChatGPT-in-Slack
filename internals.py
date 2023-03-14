import threading
import time

import openai
import tiktoken
import re
from typing import List, Dict, Any, Generator

from openai.error import Timeout
from openai.openai_object import OpenAIObject
from slack_bolt import BoltContext
from slack_sdk.web import WebClient, SlackResponse

#
# Internal functions
#

MAX_TOKENS = 1024
GPT_3_5_TURBO_0301_MODEL = "gpt-3.5-turbo-0301"


def format_openai_message_content(content: str) -> str:
    if content is None:
        return None
    # Unescape &, < and >, since Slack replaces these with their HTML equivalents
    # See also: https://api.slack.com/reference/surfaces/formatting#escaping
    return content.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


def start_receiving_openai_response(
    *,
    api_key: str,
    messages: List[Dict[str, str]],
    user: str,
) -> Generator[OpenAIObject, Any, None]:
    # Remove old user messages to make sure we have room for max_tokens
    # See also: https://platform.openai.com/docs/guides/chat/introduction
    # > total tokens must be below the model’s maximum limit (4096 tokens for gpt-3.5-turbo-0301)
    while calculate_num_tokens(messages) >= 4096 - MAX_TOKENS:
        removed = False
        for i, message in enumerate(messages):
            if message["role"] == "user":
                del messages[i]
                removed = True
                break
        if not removed:
            # Fall through and let the OpenAI error handler deal with it
            break

    return openai.ChatCompletion.create(
        api_key=api_key,
        model="gpt-3.5-turbo",
        messages=messages,
        top_p=1,
        n=1,
        max_tokens=MAX_TOKENS,
        temperature=1,
        presence_penalty=0,
        frequency_penalty=0,
        logit_bias={},
        user=user,
        stream=True,
    )


def consume_openai_stream_to_write_reply(
    *,
    client: WebClient,
    wip_reply: dict,
    context: BoltContext,
    user_id: str,
    messages: List[Dict[str, str]],
    steam: Generator[OpenAIObject, Any, None],
    timeout_seconds: int,
):
    start_time = time.time()
    assistant_reply: Dict[str, str] = {"content": ""}
    messages.append(assistant_reply)
    word_count = 0
    threads = []
    try:
        for chunk in steam:
            spent_seconds = time.time() - start_time
            if timeout_seconds < spent_seconds:
                raise Timeout()
            item = chunk.choices[0]
            if item.get("finish_reason") is not None:
                break
            delta = item.get("delta")
            if delta.get("role") is not None:
                assistant_reply["role"] = delta.get("role")
            elif delta.get("content") is not None:
                word_count += 1
                assistant_reply["content"] += delta.get("content")
                if word_count >= 20:

                    def update_message():
                        assistant_reply_text = format_assistant_reply(
                            assistant_reply["content"]
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

                    thread = threading.Thread(target=update_message)
                    thread.daemon = True
                    thread.start()
                    threads.append(thread)
                    word_count = 0
        assistant_reply_text = format_assistant_reply(assistant_reply["content"])
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
            steam.close()
        except Exception:
            pass


def post_wip_message(
    client: WebClient,
    channel: str,
    thread_ts: str,
    messages: List[Dict[str, str]],
    user: str,
) -> SlackResponse:
    return client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":hourglass_flowing_sand: Wait a second, please ...",
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": {"messages": messages, "user": user},
        },
    )


def update_wip_message(
    client: WebClient,
    channel: str,
    ts: str,
    text: str,
    messages: List[Dict[str, str]],
    user: str,
) -> SlackResponse:
    return client.chat_update(
        channel=channel,
        ts=ts,
        text=text,
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": {"messages": messages, "user": user},
        },
    )


def calculate_num_tokens(
    messages: List[Dict[str, str]],
    model: str = GPT_3_5_TURBO_0301_MODEL,
) -> int:
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == GPT_3_5_TURBO_0301_MODEL:  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            # every message follows <im_start>{role/name}\n{content}<im_end>\n
            num_tokens += 4
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        error = (
            f"Calculating the number of tokens for for model {model} is not yet supported. "
            "See https://github.com/openai/openai-python/blob/main/chatml.md "
            "for information on how messages are converted to tokens."
        )
        raise NotImplementedError(error)


def format_assistant_reply(content: str) -> str:
    result = format_openai_message_content(content)
    for o, n in [
        ("^\n+", ""),
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
        ("```\\s*[Mm]atlab\n", "```\n"),
        ("```\\s*[Ss][Qq][Ll]\n", "```\n"),
        ("```\\s*[Pp][Hh][Pp]\n", "```\n"),
        ("```\\s*[Pp][Ee][Rr][Ll]\n", "```\n"),
        ("```\\s*[Jj]ava[Ss]cript", "```\n"),
        ("```\\s*[Ty]ype[Ss]cript", "```\n"),
        ("```\\s*[Pp]ython\n", "```\n"),
    ]:
        result = re.sub(o, n, result)
    return result
