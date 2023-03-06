import logging
import os

from openai.error import Timeout
from slack_bolt import App, Ack, BoltContext
from typing import Dict
from slack_sdk.web import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from internals import (
    post_wip_message,
    call_openai,
    format_assistant_reply,
    update_wip_message,
    format_openai_message_content,
)

#
# Listener functions
#


def just_ack(ack: Ack):
    ack()


DEFAULT_SYSTEM_TEXT = """
You are a bot in a slack chat room. You might receive messages from multiple people.
Each message has the author id prepended, like this: "<@U1234> message text".
"""
SYSTEM_TEXT = os.environ.get("SYSTEM_TEXT", DEFAULT_SYSTEM_TEXT)

DEFAULT_OPENAI_TIMEOUT_SECONDS = 30
OPENAI_TIMEOUT_SECONDS = int(os.environ.get(
    "OPENAI_TIMEOUT_SECONDS", DEFAULT_OPENAI_TIMEOUT_SECONDS
))

TIMEOUT_ERROR_MESSAGE = (
    f"Sorry! It looks like OpenAI didn't respond within {OPENAI_TIMEOUT_SECONDS} seconds. "
    "Please try again later. :bow:"
)


def start_convo(
    context: BoltContext, payload: dict, client: WebClient, logger: logging.Logger
):
    wip_reply = None
    try:
        if payload.get("thread_ts") is not None:
            return

        openai_api_key = context.get("OPENAI_API_KEY")
        if openai_api_key is None:
            client.chat_postMessage(
                channel=context.channel_id,
                text="To use this app, please configure your OpenAI API key first",
            )
            return

        messages = [
            {"role": "system", "content": SYSTEM_TEXT},
            {"role": "user", "content": format_openai_message_content(payload["text"])},
        ]
        wip_reply = post_wip_message(
            client=client,
            channel=context.channel_id,
            thread_ts=payload["ts"],
            messages=messages,
            user=context.user_id,
        )
        response = call_openai(
            api_key=openai_api_key,
            openai_timeout_seconds=OPENAI_TIMEOUT_SECONDS,
            messages=messages,
            user=context.user_id,
            logger=logger,
        )
        assistant_reply: Dict[str, str] = response["choices"][0]["message"]
        assistant_reply_text = format_assistant_reply(assistant_reply["content"])
        messages.append(
            {"content": assistant_reply_text, "role": assistant_reply["role"]}
        )

        update_wip_message(
            client=client,
            channel=context.channel_id,
            ts=wip_reply["message"]["ts"],
            text=assistant_reply_text,
            messages=messages,
            user=context.user_id,
        )
    except Timeout:
        if wip_reply is not None:
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=TIMEOUT_ERROR_MESSAGE,
            )
    except Exception as e:
        text = f"Failed to start a conversation with ChatGPT: {e}"
        logger.exception(text, e)
        if wip_reply is not None:
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=text,
            )


def reply_if_necessary(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    wip_reply = None
    try:
        thread_ts = payload.get("thread_ts")
        if thread_ts is None:
            return
        if (
            payload.get("bot_id") is not None
            and payload.get("bot_id") != context.bot_id
        ):
            # Skip a new message by a different app
            return

        openai_api_key = context.get("OPENAI_API_KEY")
        if openai_api_key is None:
            return

        replies = client.conversations_replies(
            channel=context.channel_id,
            ts=thread_ts,
            include_all_metadata=True,
            limit=1000,
        )
        messages = []
        user_id = context.user_id
        last_assistant_idx = -1
        reply_messages = replies.get("messages", [])
        indices_to_remove = []
        for idx, reply in enumerate(reply_messages):
            maybe_event_type = reply.get("metadata", {}).get("event_type")
            if maybe_event_type == "chat-gpt-convo":
                if context.bot_id != reply.get("bot_id"):
                    # Remove messages by a different app
                    indices_to_remove.append(idx)
                    continue
                maybe_new_messages = (
                    reply.get("metadata", {}).get("event_payload", {}).get("messages")
                )
                if maybe_new_messages is not None:
                    if len(messages) == 0 or user_id is None:
                        new_user_id = (
                            reply.get("metadata", {})
                            .get("event_payload", {})
                            .get("user")
                        )
                        if new_user_id is not None:
                            user_id = new_user_id
                    messages = maybe_new_messages
                    last_assistant_idx = idx

        if last_assistant_idx == -1:
            return

        filtered_reply_messages = []
        for idx, reply in enumerate(reply_messages):
            if idx not in indices_to_remove:
                filtered_reply_messages.append(reply)
        if len(filtered_reply_messages) == last_assistant_idx + 1:
            return

        start_idx = last_assistant_idx + 1
        for reply in filtered_reply_messages[start_idx:]:
            messages.append(
                {
                    "content": format_openai_message_content(reply.get("text")),
                    "role": "user",
                }
            )

        wip_reply = post_wip_message(
            client=client,
            channel=context.channel_id,
            thread_ts=payload["ts"],
            messages=messages,
            user=user_id,
        )
        response = call_openai(
            api_key=openai_api_key,
            openai_timeout_seconds=OPENAI_TIMEOUT_SECONDS,
            messages=messages,
            user=user_id,
            logger=logger,
        )

        latest_replies = client.conversations_replies(
            channel=context.channel_id,
            ts=thread_ts,
            include_all_metadata=True,
            limit=1000,
        )
        if latest_replies.get("messages", [])[-1]["ts"] != wip_reply["message"]["ts"]:
            # Since a new reply will come soon, this app abandons this reply
            client.chat_delete(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
            )
            return

        assistant_reply: Dict[str, str] = response["choices"][0]["message"]
        assistant_reply_text = format_assistant_reply(assistant_reply["content"])
        messages.append(
            {"content": assistant_reply_text, "role": assistant_reply["role"]}
        )
        update_wip_message(
            client=client,
            channel=context.channel_id,
            ts=wip_reply["message"]["ts"],
            text=assistant_reply_text,
            messages=messages,
            user=user_id,
        )
    except Timeout:
        if wip_reply is not None:
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=TIMEOUT_ERROR_MESSAGE,
            )
    except Exception as e:
        text = f"Failed to reply in the conversation with ChatGPT: {e}"
        logger.exception(text, e)
        if wip_reply is not None:
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=text,
            )


def register_listeners(app: App):
    app.event("app_mention")(ack=just_ack, lazy=[start_convo])
    app.event("message")(ack=just_ack, lazy=[reply_if_necessary])


if __name__ == "__main__":
    #
    # Local development
    #

    from slack_bolt.adapter.socket_mode import SocketModeHandler

    logging.basicConfig(level=logging.DEBUG)

    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))
    app = App(client=client, process_before_response=True)
    register_listeners(app)

    @app.middleware
    def set_openai_api_key(context: BoltContext, next_):
        context["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        next_()

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
