import openai
import tiktoken
import re
from typing import List, Dict
from slack_sdk.web import WebClient

#
# Internal functions
#


def call_openai(api_key: str, messages: List[Dict[str, str]], user: str):
    max_tokens = 1024

    # Remove old user messages to make sure we have room for max_tokens 
    while num_tokens_from_messages(messages) >= 4096 - max_tokens:
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
        max_tokens=max_tokens,
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

def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo-0301":  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")

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
