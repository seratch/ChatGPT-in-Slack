import openai
import re
from typing import List, Dict
from slack_sdk.web import WebClient

#
# Internal functions
#


def call_openai(api_key: str, messages: List[Dict[str, str]], user: str):
    return openai.ChatCompletion.create(
        api_key=api_key,
        model="gpt-3.5-turbo",
        messages=messages,
        top_p=1,
        n=1,
        max_tokens=1024,
        temperature=1,
        presence_penalty=0,
        frequency_penalty=0,
        logit_bias={},
        user=user,
    )


def post_wip_message(
    client: WebClient,
    channel: str,
    thread_ts: str,
    messages: List[Dict[str, str]],
    user: str,
):
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
):
    client.chat_update(
        channel=channel,
        ts=ts,
        text=text,
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": {"messages": messages, "user": user},
        },
    )


def format_assistant_reply(content: str) -> str:
    result = content
    for o, n in [
        ("^\n+", ""),
        ("```[Rr]ust\n", "```\n"),
        ("```[Rr]uby\n", "```\n"),
        ("```[Ss]cala\n", "```\n"),
        ("```[Kk]otlin\n", "```\n"),
        ("```[Jj]ava\n", "```\n"),
        ("```[Gg]o\n", "```\n"),
        ("```[Ss]wift\n", "```\n"),
        ("```[Oo]objective[Cc]\n", "```\n"),
        ("```[Cc]\n", "```\n"),
        ("```[Ss][Qq][Ll]\n", "```\n"),
        ("```[Pp][Hh][Pp]\n", "```\n"),
        ("```[Pp][Ee][Rr][Ll]\n", "```\n"),
        ("```[Jj]ava[Ss]cript", "```\n"),
        ("```[Ty]ype[Ss]cript", "```\n"),
        ("```[Pp]ython\n", "```\n"),
    ]:
        result = re.sub(o, n, result)
    return result
