import logging

from openai.error import Timeout
from slack_bolt import App, Ack, BoltContext, BoltResponse
from slack_bolt.request.payload_utils import is_event
from slack_sdk.web import WebClient

from app.env import OPENAI_TIMEOUT_SECONDS, SYSTEM_TEXT, OPENAI_MODEL
from app.i18n import translate
from app.openai_ops import (
    start_receiving_openai_response,
    format_openai_message_content,
    consume_openai_stream_to_write_reply,
)
from app.wip_message import (
    post_wip_message,
)

#
# Listener functions
#


def just_ack(ack: Ack):
    ack()


TIMEOUT_ERROR_MESSAGE = (
    f":warning: Sorry! It looks like OpenAI didn't respond within {OPENAI_TIMEOUT_SECONDS} seconds. "
    "Please try again later. :bow:"
)
DEFAULT_LOADING_TEXT = ":hourglass_flowing_sand: Wait a second, please ..."


def start_convo(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
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

        # Replace placeholder for Slack user ID in the system prompt
        new_system_text = SYSTEM_TEXT.format(bot_user_id=context.bot_user_id)
        messages = [
            {"role": "system", "content": new_system_text},
            {"role": "user", "content": format_openai_message_content(payload["text"])},
        ]
        loading_text = translate(
            openai_api_key=openai_api_key, context=context, text=DEFAULT_LOADING_TEXT
        )
        wip_reply = post_wip_message(
            client=client,
            channel=context.channel_id,
            thread_ts=payload["ts"],
            loading_text=loading_text,
            messages=messages,
            user=context.user_id,
        )
        steam = start_receiving_openai_response(
            openai_api_key=openai_api_key,
            model=OPENAI_MODEL,
            messages=messages,
            user=context.user_id,
        )
        consume_openai_stream_to_write_reply(
            client=client,
            wip_reply=wip_reply,
            context=context,
            user_id=context.actor_user_id or context.user_id,
            messages=messages,
            steam=steam,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )

    except Timeout:
        if wip_reply is not None:
            text = (
                (
                    wip_reply.get("message", {}).get("text", "")
                    if wip_reply is not None
                    else ""
                )
                + "\n\n"
                + translate(
                    openai_api_key=openai_api_key,
                    context=context,
                    text=TIMEOUT_ERROR_MESSAGE,
                )
            )
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=text,
            )
    except Exception as e:
        text = (
            (
                wip_reply.get("message", {}).get("text", "")
                if wip_reply is not None
                else ""
            )
            + "\n\n"
            + translate(
                openai_api_key=openai_api_key,
                context=context,
                text=f":warning: Failed to start a conversation with ChatGPT: {e}",
            )
        )
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
        user_id = context.actor_user_id or context.user_id
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
        if len(filtered_reply_messages) == 0:
            return

        for reply in filtered_reply_messages:
            messages.append(
                {
                    "content": format_openai_message_content(reply.get("text")),
                    "role": "user",
                }
            )

        loading_text = translate(
            openai_api_key=openai_api_key, context=context, text=DEFAULT_LOADING_TEXT
        )
        wip_reply = post_wip_message(
            client=client,
            channel=context.channel_id,
            thread_ts=payload["ts"],
            loading_text=loading_text,
            messages=messages,
            user=user_id,
        )
        steam = start_receiving_openai_response(
            openai_api_key=openai_api_key,
            model=OPENAI_MODEL,
            messages=messages,
            user=user_id,
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

        consume_openai_stream_to_write_reply(
            client=client,
            wip_reply=wip_reply,
            context=context,
            user_id=user_id,
            messages=messages,
            steam=steam,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )

    except Timeout:
        if wip_reply is not None:
            text = (
                (
                    wip_reply.get("message", {}).get("text", "")
                    if wip_reply is not None
                    else ""
                )
                + "\n\n"
                + translate(
                    openai_api_key=openai_api_key,
                    context=context,
                    text=TIMEOUT_ERROR_MESSAGE,
                )
            )
            client.chat_update(
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=text,
            )
    except Exception as e:
        text = (
            (
                wip_reply.get("message", {}).get("text", "")
                if wip_reply is not None
                else ""
            )
            + "\n\n"
            + f":warning: Failed to reply: {e}"
        )
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


MESSAGE_SUBTYPES_TO_SKIP = ["message_changed", "message_deleted"]


# To reduce unnecessary workload in this app,
# this before_authorize function skips message changed/deleted events.
# Especially, "message_changed" events can be triggered many times when the app rapidly updates its reply.
def before_authorize(
    body: dict,
    payload: dict,
    logger: logging.Logger,
    next_,
):
    if (
        is_event(body)
        and payload.get("type") == "message"
        and payload.get("subtype") in MESSAGE_SUBTYPES_TO_SKIP
    ):
        logger.debug(
            "Skipped the following middleware and listeners "
            f"for this message event (subtype: {payload.get('subtype')})"
        )
        return BoltResponse(status=200, body="")
    next_()
