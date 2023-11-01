import json
import logging
import re
import time

from openai.error import Timeout
from slack_bolt import App, Ack, BoltContext, BoltResponse
from slack_bolt.request.payload_utils import is_event
from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient

from app.env import (
    OPENAI_TIMEOUT_SECONDS,
    SYSTEM_TEXT,
    TRANSLATE_MARKDOWN,
)
from app.i18n import translate
from app.openai_ops import (
    start_receiving_openai_response,
    format_openai_message_content,
    consume_openai_stream_to_write_reply,
    build_system_text,
    messages_within_context_window,
    generate_slack_thread_summary,
    generate_proofreading_result,
    generate_chatgpt_response,
)
from app.slack_ops import (
    find_parent_message,
    is_no_mention_thread,
    post_wip_message,
    update_wip_message,
    extract_state_value,
    build_thread_replies_as_combined_text,
)

from app.utils import redact_string

#
# Listener functions
#


def just_ack(ack: Ack):
    ack()


TIMEOUT_ERROR_MESSAGE = (
    f":warning: Apologies! It seems that OpenAI didn't respond within the {OPENAI_TIMEOUT_SECONDS}-second timeframe. "
    "Please try your request again later. "
    "If you wish to extend the timeout limit, "
    "you may consider deploying this app with customized settings on your infrastructure. :bow:"
)
DEFAULT_LOADING_TEXT = ":hourglass_flowing_sand: Wait a second, please ..."


#
# Chat with the bot
#


def respond_to_app_mention(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    if payload.get("thread_ts") is not None:
        parent_message = find_parent_message(
            client, context.channel_id, payload.get("thread_ts")
        )
        if parent_message is not None:
            if is_no_mention_thread(context, parent_message):
                # The message event handler will reply to this
                return

    wip_reply = None
    # Replace placeholder for Slack user ID in the system prompt
    system_text = build_system_text(SYSTEM_TEXT, TRANSLATE_MARKDOWN, context)
    messages = [{"role": "system", "content": system_text}]

    openai_api_key = context.get("OPENAI_API_KEY")
    try:
        if openai_api_key is None:
            client.chat_postMessage(
                channel=context.channel_id,
                text="To use this app, please configure your OpenAI API key first",
            )
            return

        user_id = context.actor_user_id or context.user_id

        if payload.get("thread_ts") is not None:
            # Mentioning the bot user in a thread
            replies_in_thread = client.conversations_replies(
                channel=context.channel_id,
                ts=payload.get("thread_ts"),
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])
            for reply in replies_in_thread:
                reply_text = redact_string(reply.get("text"))
                messages.append(
                    {
                        "role": (
                            "assistant"
                            if reply["user"] == context.bot_user_id
                            else "user"
                        ),
                        "content": (
                            f"<@{reply['user']}>: "
                            + format_openai_message_content(
                                reply_text, TRANSLATE_MARKDOWN
                            )
                        ),
                    }
                )
        else:
            # Strip bot Slack user ID from initial message
            msg_text = re.sub(f"<@{context.bot_user_id}>\\s*", "", payload["text"])
            msg_text = redact_string(msg_text)
            messages.append(
                {
                    "role": "user",
                    "content": f"<@{user_id}>: "
                    + format_openai_message_content(msg_text, TRANSLATE_MARKDOWN),
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
            user=context.user_id,
        )

        (
            messages,
            num_context_tokens,
            max_context_tokens,
        ) = messages_within_context_window(messages, context=context)
        num_messages = len([msg for msg in messages if msg.get("role") != "system"])
        if num_messages == 0:
            update_wip_message(
                client=client,
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=f":warning: The previous message is too long ({num_context_tokens}/{max_context_tokens} prompt tokens).",
                messages=messages,
                user=context.user_id,
            )
        else:
            stream = start_receiving_openai_response(
                openai_api_key=openai_api_key,
                model=context["OPENAI_MODEL"],
                temperature=context["OPENAI_TEMPERATURE"],
                messages=messages,
                user=context.user_id,
                openai_api_type=context["OPENAI_API_TYPE"],
                openai_api_base=context["OPENAI_API_BASE"],
                openai_api_version=context["OPENAI_API_VERSION"],
                openai_deployment_id=context["OPENAI_DEPLOYMENT_ID"],
                function_call_module_name=context["OPENAI_FUNCTION_CALL_MODULE_NAME"],
            )
            consume_openai_stream_to_write_reply(
                client=client,
                wip_reply=wip_reply,
                context=context,
                user_id=user_id,
                messages=messages,
                stream=stream,
                timeout_seconds=OPENAI_TIMEOUT_SECONDS,
                translate_markdown=TRANSLATE_MARKDOWN,
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


def respond_to_new_message(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    if payload.get("bot_id") is not None and payload.get("bot_id") != context.bot_id:
        # Skip a new message by a different app
        return

    wip_reply = None
    try:
        is_in_dm_with_bot = payload.get("channel_type") == "im"
        is_no_mention_required = False
        thread_ts = payload.get("thread_ts")
        if is_in_dm_with_bot is False and thread_ts is None:
            return

        openai_api_key = context.get("OPENAI_API_KEY")
        if openai_api_key is None:
            return

        messages_in_context = []
        if is_in_dm_with_bot is True and thread_ts is None:
            # In the DM with the bot
            past_messages = client.conversations_history(
                channel=context.channel_id,
                include_all_metadata=True,
                limit=100,
            ).get("messages", [])
            past_messages.reverse()
            # Remove old messages
            for message in past_messages:
                seconds = time.time() - float(message.get("ts"))
                if seconds < 86400:  # less than 1 day
                    messages_in_context.append(message)
            is_no_mention_required = True
        else:
            # In a thread with the bot in a channel
            messages_in_context = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])
            if is_in_dm_with_bot is True:
                is_no_mention_required = True
            else:
                the_parent_message_found = False
                for message in messages_in_context:
                    if message.get("ts") == thread_ts:
                        the_parent_message_found = True
                        is_no_mention_required = is_no_mention_thread(context, message)
                        break
                if the_parent_message_found is False:
                    parent_message = find_parent_message(
                        client, context.channel_id, thread_ts
                    )
                    if parent_message is not None:
                        is_no_mention_required = is_no_mention_thread(
                            context, parent_message
                        )

        messages = []
        user_id = context.actor_user_id or context.user_id
        last_assistant_idx = -1
        indices_to_remove = []
        for idx, reply in enumerate(messages_in_context):
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

        if is_no_mention_required is False:
            return

        if is_in_dm_with_bot is True or last_assistant_idx == -1:
            # To know whether this app needs to start a new convo
            if not next(filter(lambda msg: msg["role"] == "system", messages), None):
                # Replace placeholder for Slack user ID in the system prompt
                system_text = build_system_text(
                    SYSTEM_TEXT, TRANSLATE_MARKDOWN, context
                )
                messages.insert(0, {"role": "system", "content": system_text})

        filtered_messages_in_context = []
        for idx, reply in enumerate(messages_in_context):
            # Strip bot Slack user ID from initial message
            if idx == 0:
                reply["text"] = re.sub(
                    f"<@{context.bot_user_id}>\\s*", "", reply["text"]
                )
            if idx not in indices_to_remove:
                filtered_messages_in_context.append(reply)
        if len(filtered_messages_in_context) == 0:
            return

        for reply in filtered_messages_in_context:
            msg_user_id = reply.get("user")
            reply_text = redact_string(reply.get("text"))
            messages.append(
                {
                    "content": f"<@{msg_user_id}>: "
                    + format_openai_message_content(reply_text, TRANSLATE_MARKDOWN),
                    "role": (
                        "assistant" if reply["user"] == context.bot_user_id else "user"
                    ),
                }
            )

        loading_text = translate(
            openai_api_key=openai_api_key, context=context, text=DEFAULT_LOADING_TEXT
        )
        wip_reply = post_wip_message(
            client=client,
            channel=context.channel_id,
            thread_ts=payload.get("thread_ts") if is_in_dm_with_bot else payload["ts"],
            loading_text=loading_text,
            messages=messages,
            user=user_id,
        )

        (
            messages,
            num_context_tokens,
            max_context_tokens,
        ) = messages_within_context_window(messages, context=context)
        num_messages = len([msg for msg in messages if msg.get("role") != "system"])
        if num_messages == 0:
            update_wip_message(
                client=client,
                channel=context.channel_id,
                ts=wip_reply["message"]["ts"],
                text=f":warning: The previous message is too long ({num_context_tokens}/{max_context_tokens} prompt tokens).",
                messages=messages,
                user=context.user_id,
            )
        else:
            stream = start_receiving_openai_response(
                openai_api_key=openai_api_key,
                model=context["OPENAI_MODEL"],
                temperature=context["OPENAI_TEMPERATURE"],
                messages=messages,
                user=user_id,
                openai_api_type=context["OPENAI_API_TYPE"],
                openai_api_base=context["OPENAI_API_BASE"],
                openai_api_version=context["OPENAI_API_VERSION"],
                openai_deployment_id=context["OPENAI_DEPLOYMENT_ID"],
                function_call_module_name=context["OPENAI_FUNCTION_CALL_MODULE_NAME"],
            )

            latest_replies = client.conversations_replies(
                channel=context.channel_id,
                ts=wip_reply.get("ts"),
                include_all_metadata=True,
                limit=1000,
            )
            if (
                latest_replies.get("messages", [])[-1]["ts"]
                != wip_reply["message"]["ts"]
            ):
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
                stream=stream,
                timeout_seconds=OPENAI_TIMEOUT_SECONDS,
                translate_markdown=TRANSLATE_MARKDOWN,
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


#
# Summarize a thread
#


def show_summarize_option_modal(
    ack: Ack,
    client: WebClient,
    body: dict,
    context: BoltContext,
):
    openai_api_key = context.get("OPENAI_API_KEY")
    prompt = translate(
        openai_api_key=openai_api_key,
        context=context,
        text=(
            "All replies posted in a Slack thread will be provided below. "
            "Could you summarize the discussion in 200 characters or less?"
        ),
    )
    thread_ts = body.get("message").get("thread_ts", body.get("message").get("ts"))
    where_to_display_options = [
        {
            "text": {
                "type": "plain_text",
                "text": "Here, on this modal",
            },
            "value": "modal",
        },
        {
            "text": {
                "type": "plain_text",
                "text": "As a reply in the thread",
            },
            "value": "reply",
        },
    ]
    is_error = False
    blocks = []
    try:
        # Test if this bot is in the channel
        client.conversations_replies(
            channel=context.channel_id,
            ts=thread_ts,
            limit=1,
        )
        blocks = [
            {
                "type": "input",
                "block_id": "where-to-share-summary",
                "label": {
                    "type": "plain_text",
                    "text": "How would you like to see the summary?",
                },
                "element": {
                    "action_id": "input",
                    "type": "radio_buttons",
                    "initial_option": where_to_display_options[0],
                    "options": where_to_display_options,
                },
            },
            {
                "type": "input",
                "block_id": "prompt",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "multiline": True,
                    "initial_value": prompt,
                },
                "label": {
                    "type": "plain_text",
                    "text": "Customize the prompt as you prefer:",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Note that after the instruction you provide, this app will append all the replies in the thread.",
                    }
                ],
            },
        ]
    except SlackApiError as e:
        is_error = True
        error_code = e.response["error"]
        if error_code == "not_in_channel":
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "It appears that this app's bot user is not a member of the specified channel. "
                        f"Could you please invite <@{context.bot_user_id}> to <#{context.channel_id}> "
                        "to make this app functional?",
                    },
                }
            ]
        else:
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Something is wrong! (error: {error_code})",
                    },
                }
            ]

    view = {
        "type": "modal",
        "callback_id": "request-thread-summary",
        "title": {"type": "plain_text", "text": "Summarize the thread"},
        "submit": {"type": "plain_text", "text": "Summarize"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": json.dumps(
            {
                "thread_ts": thread_ts,
                "channel": context.channel_id,
            }
        ),
        "blocks": blocks,
    }
    if is_error is True:
        del view["submit"]

    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=view,
    )
    ack()


def ack_summarize_options_modal_submission(
    ack: Ack,
    payload: dict,
):
    where_to_display = (
        extract_state_value(payload, "where-to-share-summary")
        .get("selected_option")
        .get("value", "modal")
    )
    if where_to_display == "modal":
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "request-thread-summary",
                "title": {"type": "plain_text", "text": "Summarize the thread"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "Got it! Working on the summary now ... :hourglass:",
                        },
                    },
                ],
            },
        )
    else:
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "request-thread-summary",
                "title": {"type": "plain_text", "text": "Summarize the thread"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "Got it! Once the summary is ready, I will post it in the thread.",
                        },
                    },
                ],
            },
        )


def prepare_and_share_thread_summary(
    payload: dict,
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
):
    try:
        openai_api_key = context.get("OPENAI_API_KEY")
        where_to_display = (
            extract_state_value(payload, "where-to-share-summary")
            .get("selected_option")
            .get("value", "modal")
        )
        prompt = extract_state_value(payload, "prompt").get("value")
        private_metadata = json.loads(payload.get("private_metadata"))
        thread_content = build_thread_replies_as_combined_text(
            context=context,
            client=client,
            channel=private_metadata.get("channel"),
            thread_ts=private_metadata.get("thread_ts"),
        )
        here_is_summary = translate(
            openai_api_key=openai_api_key,
            context=context,
            text="Here is the summary:",
        )
        summary = generate_slack_thread_summary(
            context=context,
            logger=logger,
            openai_api_key=openai_api_key,
            prompt=prompt,
            thread_content=thread_content,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )

        if where_to_display == "modal":
            client.views_update(
                view_id=payload["id"],
                view={
                    "type": "modal",
                    "callback_id": "request-thread-summary",
                    "title": {"type": "plain_text", "text": "Summarize the thread"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{here_is_summary}\n\n{summary}",
                            },
                        },
                    ],
                },
            )
        else:
            client.chat_postMessage(
                channel=private_metadata.get("channel"),
                thread_ts=private_metadata.get("thread_ts"),
                text=f"{here_is_summary}\n\n{summary}",
            )
    except Timeout:
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "request-thread-summary",
                "title": {"type": "plain_text", "text": "Summarize the thread"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": TIMEOUT_ERROR_MESSAGE,
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"Failed to share a thread summary: {e}")
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "request-thread-summary",
                "title": {"type": "plain_text", "text": "Summarize the thread"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":warning: My apologies! "
                            f"An error occurred while generating the summary of this thread: {e}",
                        },
                    },
                ],
            },
        )


#
# Proofread user inputs
#


def build_proofreading_input_modal(prompt: str):
    return {
        "type": "modal",
        "callback_id": "proofread",
        "title": {"type": "plain_text", "text": "Proofreading"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": json.dumps({"prompt": prompt}),
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": prompt},
            },
            {
                "type": "input",
                "block_id": "original_text",
                "label": {"type": "plain_text", "text": "Your Text"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "multiline": True,
                },
            },
        ],
    }


def start_proofreading(client: WebClient, body: dict, payload: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_proofreading_input_modal(payload.get("value")),
    )


def ack_proofreading_modal_submission(
    ack: Ack,
    payload: dict,
    context: BoltContext,
):
    original_text = extract_state_value(payload, "original_text").get("value")
    text = "\n".join(map(lambda s: f">{s}", original_text.split("\n")))
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "proofread",
            "title": {"type": "plain_text", "text": "Proofreading"},
            "close": {"type": "plain_text", "text": "Close"},
            "private_metadata": payload["private_metadata"],
            "blocks": [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Running OpenAI's *{context['OPENAI_MODEL']}* model:",
                        },
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{text}\n\nProofreading your input now ... :hourglass:",
                    },
                },
            ],
        },
    )


def display_proofreading_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    try:
        openai_api_key = context.get("OPENAI_API_KEY")
        original_text = extract_state_value(payload, "original_text").get("value")
        text = "\n".join(map(lambda s: f">{s}", original_text.split("\n")))
        result = generate_proofreading_result(
            context=context,
            logger=logger,
            openai_api_key=openai_api_key,
            original_text=original_text,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "proofread-result",
                "title": {"type": "plain_text", "text": "Proofreading"},
                "submit": {"type": "plain_text", "text": "Try Another"},
                "close": {"type": "plain_text", "text": "Close"},
                "private_metadata": payload["private_metadata"],
                "blocks": [
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Provided using OpenAI's *{context['OPENAI_MODEL']}* model:",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n{result}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": " "},
                        "accessory": {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Send this result in DM",
                            },
                            "value": "clicked",
                            "action_id": "send-proofread-result-in-dm",
                        },
                    },
                ],
            },
        )
    except Timeout:
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "proofread-result",
                "title": {"type": "plain_text", "text": "Proofreading"},
                "submit": {"type": "plain_text", "text": "Try Another"},
                "close": {"type": "plain_text", "text": "Close"},
                "private_metadata": payload["private_metadata"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n{TIMEOUT_ERROR_MESSAGE}",
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"Failed to share a thread summary: {e}")
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "proofread-result",
                "title": {"type": "plain_text", "text": "Proofreading"},
                "submit": {"type": "plain_text", "text": "Try Another"},
                "close": {"type": "plain_text", "text": "Close"},
                "private_metadata": payload["private_metadata"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n:warning: My apologies! "
                            f"An error occurred while generating the summary of this thread: {e}",
                        },
                    },
                ],
            },
        )


def display_proofreading_modal_again(ack: Ack, payload):
    private_metadata = json.loads(payload["private_metadata"])
    ack(
        response_action="update",
        view=build_proofreading_input_modal(private_metadata["prompt"]),
    )


def send_proofreading_result_in_dm(
    body: dict,
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
):
    view = body["view"]
    view_blocks = view["blocks"]
    if view_blocks is None or len(view_blocks) == 0:
        return
    try:
        result = view_blocks[1].get("text", {}).get("text")
        if result is not None:
            client.chat_postMessage(
                channel=context.actor_user_id,
                text=":wave: Here is the proofreading result:\n" + result,
            )
            # Remove the last block that displays the button
            view_blocks.pop((len(view_blocks) - 1))
            print(view_blocks)
            client.views_update(
                view_id=body["view"]["id"],
                view={
                    "type": "modal",
                    "callback_id": "proofread-result",
                    "title": {"type": "plain_text", "text": "Proofreading"},
                    "submit": {"type": "plain_text", "text": "Try Another"},
                    "close": {"type": "plain_text", "text": "Close"},
                    "private_metadata": view["private_metadata"],
                    "blocks": view_blocks,
                },
            )
    except Exception as e:
        logger.error(f"Failed to send a DM: {e}")


#
# Chat from scratch
#


def start_chat_from_scratch(client: WebClient, body: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view={
            "type": "modal",
            "callback_id": "chat-from-scratch",
            "title": {"type": "plain_text", "text": "ChatGPT"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "prompt",
                    "label": {"type": "plain_text", "text": "Prompt"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input",
                        "multiline": True,
                    },
                },
            ],
        },
    )


def ack_chat_from_scratch_modal_submission(
    ack: Ack,
    payload: dict,
):
    prompt = extract_state_value(payload, "prompt").get("value")
    text = "\n".join(map(lambda s: f">{s}", prompt.split("\n")))
    ack(
        response_action="update",
        view={
            "type": "modal",
            "callback_id": "chat-from-scratch",
            "title": {"type": "plain_text", "text": "ChatGPT"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{text}\n\nWorking on this now ... :hourglass:",
                    },
                },
            ],
        },
    )


def display_chat_from_scratch_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    openai_api_key = context.get("OPENAI_API_KEY")
    try:
        prompt = extract_state_value(payload, "prompt").get("value")
        text = "\n".join(map(lambda s: f">{s}", prompt.split("\n")))
        result = generate_chatgpt_response(
            context=context,
            logger=logger,
            openai_api_key=openai_api_key,
            prompt=prompt,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "chat-from-scratch",
                "title": {"type": "plain_text", "text": "ChatGPT"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n{result}",
                        },
                    },
                ],
            },
        )
    except Timeout:
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "chat-from-scratch",
                "title": {"type": "plain_text", "text": "ChatGPT"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n{TIMEOUT_ERROR_MESSAGE}",
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"Failed to share a thread summary: {e}")
        client.views_update(
            view_id=payload["id"],
            view={
                "type": "modal",
                "callback_id": "chat-from-scratch",
                "title": {"type": "plain_text", "text": "ChatGPT"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{text}\n\n:warning: My apologies! "
                            f"An error occurred while generating the summary of this thread: {e}",
                        },
                    },
                ],
            },
        )


def register_listeners(app: App):
    # Chat with the bot
    app.event("app_mention")(ack=just_ack, lazy=[respond_to_app_mention])
    app.event("message")(ack=just_ack, lazy=[respond_to_new_message])

    # Summarize a thread
    app.shortcut("summarize-thread")(show_summarize_option_modal)
    app.view("request-thread-summary")(
        ack=ack_summarize_options_modal_submission,
        lazy=[prepare_and_share_thread_summary],
    )

    # Use templates

    # Proofreading
    app.action("templates-proofread")(
        ack=just_ack,
        lazy=[start_proofreading],
    )
    app.view("proofread")(
        ack=ack_proofreading_modal_submission,
        lazy=[display_proofreading_result],
    )
    app.view("proofread-result")(display_proofreading_modal_again)
    app.action("send-proofread-result-in-dm")(
        ack=just_ack,
        lazy=[send_proofreading_result_in_dm],
    )

    # Free format chat
    app.action("templates-from-scratch")(
        ack=just_ack,
        lazy=[start_chat_from_scratch],
    )
    app.view("chat-from-scratch")(
        ack=ack_chat_from_scratch_modal_submission,
        lazy=[display_chat_from_scratch_result],
    )


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
