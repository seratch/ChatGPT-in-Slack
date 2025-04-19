import json
import logging
import re
import threading
import time
from typing import List

import requests
from openai import APITimeoutError
from slack_bolt import App, Ack, BoltContext, BoltResponse
from slack_bolt.request.payload_utils import is_event
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError

from app.env import (
    OPENAI_TIMEOUT_SECONDS,
    SYSTEM_TEXT,
    TRANSLATE_MARKDOWN,
    OPENAI_IMAGE_GENERATION_MODEL,
)
from app.i18n import translate
from app.openai_image_ops import (
    append_image_content_if_exists,
    generate_image,
    generate_image_variations,
)
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
from app.slack_constants import DEFAULT_LOADING_TEXT, TIMEOUT_ERROR_MESSAGE
from app.slack_ops import (
    find_parent_message,
    is_this_app_mentioned,
    post_wip_message,
    update_wip_message,
    extract_state_value,
    build_thread_replies_as_combined_text,
    can_send_image_url_to_openai,
)

from app.sensitive_info_redaction import redact_string
from app.slack_ui import (
    build_proofreading_input_modal,
    build_proofreading_wip_modal,
    build_summarize_option_modal,
    build_summarize_wip_modal,
    build_summarize_message_modal,
    build_summarize_result_modal,
    build_summarize_timeout_error_modal,
    build_summarize_error_modal,
    build_proofreading_result_modal,
    build_proofreading_timeout_error_modal,
    build_proofreading_error_modal,
    build_proofreading_result_no_dm_button_modal,
    build_from_scratch_modal,
    build_from_scratch_wip_modal,
    build_from_scratch_result_modal,
    build_from_scratch_timeout_modal,
    build_from_scratch_error_modal,
    build_image_generation_input_modal,
    build_image_generation_wip_modal,
    build_image_generation_result_modal,
    build_image_generation_text_modal,
    build_image_generation_result_blocks,
    build_image_variations_text_modal,
    build_image_variations_result_blocks,
    build_image_variations_result_modal,
    build_image_variations_wip_modal,
    build_image_variations_input_modal,
    build_translation_result_modal,
    build_translation_modal,
    build_translation_wip_modal,
)


#
# Listener functions
#


def just_ack(ack: Ack):
    ack()


#
# Chat with the bot
#


def respond_to_app_mention(
    context: BoltContext,
    payload: dict,
    client: WebClient,
    logger: logging.Logger,
):
    thread_ts = payload.get("thread_ts")
    if thread_ts is not None:
        parent_message = find_parent_message(client, context.channel_id, thread_ts)
        if parent_message is not None and is_this_app_mentioned(
            context, parent_message
        ):
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
        if thread_ts is not None:
            # Mentioning the bot user in a thread
            replies_in_thread = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])
            for reply in replies_in_thread:
                reply_text = redact_string(reply.get("text"))
                message_text_item = {
                    "type": "text",
                    "text": f"<@{reply['user'] if 'user' in reply else reply['username']}>: "
                    + format_openai_message_content(reply_text, TRANSLATE_MARKDOWN),
                }
                content = [message_text_item]

                if reply.get("bot_id") is None and can_send_image_url_to_openai(
                    context
                ):
                    append_image_content_if_exists(
                        bot_token=context.bot_token,
                        files=reply.get("files"),
                        content=content,
                        logger=context.logger,
                    )

                messages.append(
                    {
                        "role": (
                            "assistant"
                            if "user" in reply and reply["user"] == context.bot_user_id
                            else "user"
                        ),
                        "content": content,
                    }
                )
        else:
            # Strip bot Slack user ID from initial message
            msg_text = re.sub(f"<@{context.bot_user_id}>\\s*", "", payload["text"])
            msg_text = redact_string(msg_text)
            message_text_item = {
                "type": "text",
                "text": f"<@{user_id}>: "
                + format_openai_message_content(msg_text, TRANSLATE_MARKDOWN),
            }
            content = [message_text_item]

            if payload.get("bot_id") is None and can_send_image_url_to_openai(context):
                append_image_content_if_exists(
                    bot_token=context.bot_token,
                    files=payload.get("files"),
                    content=content,
                    logger=context.logger,
                )

            messages.append({"role": "user", "content": content})

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
                openai_organization_id=context["OPENAI_ORG_ID"],
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

    except (APITimeoutError, TimeoutError):
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

    openai_api_key = context.get("OPENAI_API_KEY")
    if openai_api_key is None:
        return

    wip_reply = None
    try:
        is_in_dm_with_bot = payload.get("channel_type") == "im"
        is_thread_for_this_app = False
        thread_ts = payload.get("thread_ts")
        if is_in_dm_with_bot is False and thread_ts is None:
            return

        messages_in_context = []
        if is_in_dm_with_bot is True and thread_ts is None:
            # In the DM with the bot; this is not within a thread
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
            is_thread_for_this_app = True
        else:
            # Within a thread
            messages_in_context = client.conversations_replies(
                channel=context.channel_id,
                ts=thread_ts,
                include_all_metadata=True,
                limit=1000,
            ).get("messages", [])
            if is_in_dm_with_bot is True:
                # In the DM with this bot
                is_thread_for_this_app = True
            else:
                # In a channel
                the_parent_message_found = False
                for message in messages_in_context:
                    if message.get("ts") == thread_ts:
                        the_parent_message_found = True
                        is_thread_for_this_app = is_this_app_mentioned(context, message)
                        break
                if the_parent_message_found is False:
                    parent_message = find_parent_message(
                        client, context.channel_id, thread_ts
                    )
                    if parent_message is not None:
                        is_thread_for_this_app = is_this_app_mentioned(
                            context, parent_message
                        )

        if is_thread_for_this_app is False:
            return

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
            content = [
                {
                    "type": "text",
                    "text": f"<@{msg_user_id}>: "
                    + format_openai_message_content(reply_text, TRANSLATE_MARKDOWN),
                }
            ]
            if reply.get("bot_id") is None and can_send_image_url_to_openai(context):
                append_image_content_if_exists(
                    bot_token=context.bot_token,
                    files=reply.get("files"),
                    content=content,
                    logger=context.logger,
                )

            messages.append(
                {
                    "content": content,
                    "role": (
                        "assistant"
                        if "user" in reply and reply["user"] == context.bot_user_id
                        else "user"
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
                openai_organization_id=context["OPENAI_ORG_ID"],
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

    except (APITimeoutError, TimeoutError):
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
# Translate a message
#


def start_translation_modal(
    client: WebClient,
    body: dict,
):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_translation_modal(body=body),
    )


def ack_translation_modal_submission(
    ack: Ack,
):
    ack(
        response_action="update",
        view=build_translation_wip_modal(
            "Got it! Working on the translation now ... :hourglass:"
        ),
    )


def display_translation_result(
    context: BoltContext,
    payload: dict,
    client: WebClient,
):
    client.views_update(
        view_id=payload["id"],
        view=build_translation_result_modal(context=context, payload=payload),
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
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_summarize_option_modal(context=context, body=body),
    )
    ack()


def ack_summarize_options_modal_submission(
    ack: Ack,
    payload: dict,
):
    selected_option = extract_state_value(payload, "where-to-share-summary")[
        "selected_option"
    ]
    where_to_display = selected_option.get("value", "modal")
    if where_to_display == "modal":
        ack(response_action="update", view=build_summarize_wip_modal())
    else:
        ack(response_action="update", view=build_summarize_message_modal())


def prepare_and_share_thread_summary(
    payload: dict,
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
):
    try:
        openai_api_key = context.get("OPENAI_API_KEY")
        selected_option = extract_state_value(payload, "where-to-share-summary")[
            "selected_option"
        ]
        where_to_display = selected_option.get("value", "modal")
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
                view=build_summarize_result_modal(
                    here_is_summary=here_is_summary,
                    summary=summary,
                ),
            )
        else:
            client.chat_postMessage(
                channel=private_metadata.get("channel"),
                thread_ts=private_metadata.get("thread_ts"),
                text=f"{here_is_summary}\n\n{summary}",
            )
    except (APITimeoutError, TimeoutError):
        client.views_update(
            view_id=payload["id"],
            view=build_summarize_timeout_error_modal(),
        )
    except Exception as e:
        logger.exception(f"Failed to share a thread summary: {e}")
        client.views_update(
            view_id=payload["id"],
            view=build_summarize_error_modal(e),
        )


#
# Proofread user inputs
#


def start_proofreading(client: WebClient, body: dict, payload: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_proofreading_input_modal(payload.get("value"), None),
    )


def ack_proofreading_modal_submission(
    ack: Ack,
    payload: dict,
    context: BoltContext,
):
    original_text = extract_state_value(payload, "original_text")["value"]
    text = "\n".join(map(lambda s: f">{s}", original_text.split("\n")))
    view = build_proofreading_wip_modal(
        payload=payload,
        context=context,
        text=text,
    )
    ack(response_action="update", view=view)


def display_proofreading_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    text = ""
    try:
        openai_api_key = context.get("OPENAI_API_KEY")
        original_text = extract_state_value(payload, "original_text")["value"]
        tone_and_voice = extract_state_value(payload, "tone_and_voice")
        tone_and_voice = (
            tone_and_voice["selected_option"].get("value")
            if tone_and_voice.get("selected_option")
            else None
        )
        text = "\n".join(map(lambda s: f">{s}", original_text.split("\n")))
        result = generate_proofreading_result(
            context=context,
            logger=logger,
            openai_api_key=openai_api_key,
            original_text=original_text,
            tone_and_voice=tone_and_voice,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )
        view = build_proofreading_result_modal(
            context=context,
            payload=payload,
            result=result,
        )
        client.views_update(view_id=payload["id"], view=view)

    except (APITimeoutError, TimeoutError):
        client.views_update(
            view_id=payload["id"],
            view=build_proofreading_timeout_error_modal(payload=payload, text=text),
        )
    except Exception as e:
        logger.exception(f"Failed to share a proofreading result: {e}")
        client.views_update(
            view_id=payload["id"],
            view=build_proofreading_error_modal(payload=payload, text=text, e=e),
        )


def display_proofreading_modal_again(ack: Ack, payload):
    private_metadata = json.loads(payload["private_metadata"])
    ack(
        response_action="update",
        view=build_proofreading_input_modal(
            private_metadata["prompt"], private_metadata.get("tone_and_voice")
        ),
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
            client.views_update(
                view_id=body["view"]["id"],
                view=build_proofreading_result_no_dm_button_modal(
                    private_metadata=view["private_metadata"],
                    blocks=view_blocks,
                ),
            )
    except Exception as e:
        logger.exception(f"Failed to send a DM: {e}")


#
# Image generation
#


def start_image_generation(client: WebClient, body: dict, payload: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_image_generation_input_modal(payload.get("value")),
    )


def ack_image_generation_modal_submission(ack: Ack):
    ack(response_action="update", view=build_image_generation_wip_modal())


def display_image_generation_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    text = ""
    try:
        prompt = extract_state_value(payload, "image_generation_prompt")["value"]
        size = extract_state_value(payload, "size")["selected_option"].get("value")
        quality = extract_state_value(payload, "quality")["selected_option"].get(
            "value"
        )
        style = extract_state_value(payload, "style")["selected_option"].get("value")
        model = context.get(
            "OPENAI_IMAGE_GENERATION_MODEL", OPENAI_IMAGE_GENERATION_MODEL
        )

        start_time = time.time()
        image_url = generate_image(
            context=context,
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )
        spent_seconds = str(round((time.time() - start_time), 2))
        logger.debug(
            f"Image generated (url: {image_url} , spent time: {spent_seconds})"
        )

        image_content = requests.get(image_url).content
        users = [context.actor_user_id]
        dm_id = client.conversations_open(users=users)["channel"]["id"]
        text = "\n".join(map(lambda s: f">{s}", prompt.split("\n")))
        message_text = (
            "Here's a new image generated using this prompt:\n"
            f"{text}\n"
            f"model: {model}, size: {size}, quality: {quality}, style: {style}, time spent: {spent_seconds} s"
        )
        upload = client.files_upload_v2(
            filename="generated_image.png",
            file=image_content,
            alt_txt=f"Generated using {model}",
            title=f"Generated using {model}",
            initial_comment=message_text,
            channel=dm_id,
        )
        file_id = upload["files"][0]["id"]
        uploaded_file_url = upload["files"][0]["url_private"]
        shared = False
        time.sleep(1.5)
        while not shared:
            latest_file_info = client.files_info(file=file_id)
            shares = latest_file_info.get("file").get("shares")
            shared = shares and len(shares.get("private")) > 0
            if not shared:
                time.sleep(0.5)

        blocks = build_image_generation_result_blocks(
            text=message_text, image_url=uploaded_file_url, model=model
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_generation_result_modal(blocks),
        )

    except (APITimeoutError, TimeoutError):
        client.chat_postMessage(
            channel=context.actor_user_id,
            text=TIMEOUT_ERROR_MESSAGE,
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_generation_text_modal(TIMEOUT_ERROR_MESSAGE),
        )
    except SlackApiError as e:
        logger.exception(f"Failed to call Slack APIs for image generation: {e}")
        client.views_update(
            view_id=payload["id"],
            view=build_image_generation_text_modal(
                f"{text}\n\n:warning: *My apologies!* "
                f"An error occurred while calling Slack APIs: `{e}`"
            ),
        )
    except Exception as e:
        logger.exception(f"Failed to share a generated image: {e}")
        error = (
            f"{text}\n\n:warning: *My apologies!* "
            f"An error occurred while generating an image: `{e}`"
        )
        client.chat_postMessage(
            channel=context.actor_user_id,
            text=error,
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_generation_text_modal(error),
        )


def start_image_variations(client: WebClient, body: dict, payload: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_image_variations_input_modal(payload.get("value")),
    )


def ack_image_variations_modal_submission(ack: Ack):
    ack(response_action="update", view=build_image_variations_wip_modal())


def display_image_variations_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    try:
        # https://platform.openai.com/docs/guides/images/variations-dall-e-2-only
        model = "dall-e-2"  # DALL·E 2 only
        size = extract_state_value(payload, "size")["selected_option"].get("value")
        image_files = extract_state_value(payload, "input_files").get("files")

        start_time = time.time()
        threads = []
        file_uploads: List[dict] = []
        try:
            for image_file in image_files:

                def generate_variations():
                    uploaded_image_url = image_file["url_private"]
                    image_data: bytes = requests.get(
                        uploaded_image_url,
                        headers={"Authorization": f"Bearer {context.bot_token}"},
                    ).content

                    image_url = generate_image_variations(
                        context=context,
                        image=image_data,
                        size=size,
                        timeout_seconds=OPENAI_TIMEOUT_SECONDS,
                    )
                    image_content = requests.get(image_url).content
                    file_uploads.append(
                        {"file": image_content, "filename": image_file["name"]}
                    )

                thread = threading.Thread(target=generate_variations)
                thread.daemon = True
                thread.start()
                threads.append(thread)

        finally:
            for t in threads:
                try:
                    if t.is_alive():
                        t.join()
                except Exception:
                    pass

        spent_seconds = str(round((time.time() - start_time), 2))

        if len(file_uploads) == 0:
            logger.error("Failed to prepare any upload content")
            client.views_update(
                view_id=payload["id"],
                view=build_image_variations_text_modal(
                    "Failed to generate variations. Please check your OpenAI platform usage."
                ),
            )
            return

        users = [context.actor_user_id]
        dm_id = client.conversations_open(users=users)["channel"]["id"]
        message_text = (
            "Here are the generated image variations for your inputs:\n"
            f"model: {model}, size: {size}, time spent: {spent_seconds} s"
        )
        upload = client.files_upload_v2(
            initial_comment=message_text,
            channel=dm_id,
            file_uploads=file_uploads,
        )
        uploaded_files = upload["files"]
        file_id = upload["files"][0]["id"]
        shared = False
        time.sleep(1.5)
        while not shared:
            latest_file_info = client.files_info(file=file_id)
            shares = latest_file_info.get("file").get("shares")
            shared = shares and len(shares.get("private")) > 0
            if not shared:
                time.sleep(0.5)

        blocks = build_image_variations_result_blocks(
            text=message_text,
            generated_image_urls=[f["url_private"] for f in upload["files"]],
            model=model,
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_variations_result_modal(blocks),
        )

    except (APITimeoutError, TimeoutError):
        client.chat_postMessage(
            channel=context.actor_user_id,
            text=TIMEOUT_ERROR_MESSAGE,
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_variations_text_modal(TIMEOUT_ERROR_MESSAGE),
        )
    except SlackApiError as e:
        logger.exception(f"Failed to call Slack APIs for image variations: {e}")
        client.views_update(
            view_id=payload["id"],
            view=build_image_variations_text_modal(
                f":warning: *My apologies!* "
                f"An error occurred while calling Slack APIs: `{e}`"
            ),
        )
    except Exception as e:
        logger.exception(f"Failed to share a generated image: {e}")
        error = (
            f"\n\n:warning: *My apologies!* "
            f"An error occurred while generating image variations: `{e}`"
        )
        client.chat_postMessage(
            channel=context.actor_user_id,
            text=error,
        )
        client.views_update(
            view_id=payload["id"],
            view=build_image_variations_text_modal(error),
        )


#
# Chat from scratch
#


def start_chat_from_scratch(client: WebClient, body: dict):
    client.views_open(
        trigger_id=body.get("trigger_id"),
        view=build_from_scratch_modal(),
    )


def ack_chat_from_scratch_modal_submission(
    ack: Ack,
    payload: dict,
):
    prompt = extract_state_value(payload, "prompt")["value"]
    text = "\n".join(map(lambda s: f">{s}", prompt.split("\n")))
    view = build_from_scratch_wip_modal(text)
    ack(response_action="update", view=view)


def display_chat_from_scratch_result(
    client: WebClient,
    context: BoltContext,
    logger: logging.Logger,
    payload: dict,
):
    text = ""
    openai_api_key = context.get("OPENAI_API_KEY")
    try:
        prompt = extract_state_value(payload, "prompt")["value"]
        text = "\n".join(map(lambda s: f">{s}", prompt.split("\n")))
        result = generate_chatgpt_response(
            context=context,
            logger=logger,
            openai_api_key=openai_api_key,
            prompt=prompt,
            timeout_seconds=OPENAI_TIMEOUT_SECONDS,
        )
        view = build_from_scratch_result_modal(text=text, result=result)
        client.views_update(view_id=payload["id"], view=view)
    except (APITimeoutError, TimeoutError):
        client.views_update(
            view_id=payload["id"],
            view=build_from_scratch_timeout_modal(text),
        )
    except Exception as e:
        logger.exception(f"Failed to share a thread summary: {e}")
        client.views_update(
            view_id=payload["id"],
            view=build_from_scratch_error_modal(text=text, e=e),
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

    # Translate a message
    app.shortcut("translate-message")(ack=just_ack, lazy=[start_translation_modal])
    app.view("translate-message")(
        ack=ack_translation_modal_submission, lazy=[display_translation_result]
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

    # Image generation
    app.action("templates-image-generation")(
        ack=just_ack,
        lazy=[start_image_generation],
    )
    app.view("image-generation")(
        ack=ack_image_generation_modal_submission,
        lazy=[display_image_generation_result],
    )
    app.action("templates-image-variations")(
        ack=just_ack,
        lazy=[start_image_variations],
    )
    app.view("image-variations")(
        ack=ack_image_variations_modal_submission,
        lazy=[display_image_variations_result],
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
