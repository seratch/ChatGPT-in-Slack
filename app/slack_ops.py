from typing import Optional
from typing import List, Dict

from slack_sdk.web import WebClient, SlackResponse
from slack_bolt import BoltContext

from app.i18n import translate
from app.markdown import slack_to_markdown


# ----------------------------
# General operations in a channel
# ----------------------------


def find_parent_message(
    client: WebClient, channel_id: Optional[str], thread_ts: Optional[str]
) -> Optional[dict]:
    if channel_id is None or thread_ts is None:
        return None

    messages = client.conversations_history(
        channel=channel_id,
        latest=thread_ts,
        limit=1,
        inclusive=1,
    ).get("messages", [])

    return messages[0] if len(messages) > 0 else None


def is_no_mention_thread(context: BoltContext, parent_message: dict) -> bool:
    parent_message_text = parent_message.get("text", "")
    return f"<@{context.bot_user_id}>" in parent_message_text


def build_thread_replies_as_combined_text(
    *,
    context: BoltContext,
    client: WebClient,
    channel: str,
    thread_ts: str,
) -> str:
    thread_content = ""
    for page in client.conversations_replies(
        channel=channel,
        ts=thread_ts,
        limit=1000,
    ):
        for reply in page.get("messages", []):
            user = reply.get("user")
            if user == context.bot_user_id:  # Skip replies by this app
                continue
            if user is None:
                user = client.bots_info(bot=reply.get("bot_id"))["bot"]["user_id"]
                if user is None or user == context.bot_user_id:
                    continue
            text = slack_to_markdown("".join(reply["text"].splitlines()))
            thread_content += f"<@{user}>: {text}\n"
    return thread_content


# ----------------------------
# WIP reply message stuff
# ----------------------------


def post_wip_message(
    *,
    client: WebClient,
    channel: str,
    thread_ts: str,
    loading_text: str,
    messages: List[Dict[str, str]],
    user: str,
) -> SlackResponse:
    system_messages = [msg for msg in messages if msg["role"] == "system"]
    return client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=loading_text,
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": {"messages": system_messages, "user": user},
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
    system_messages = [msg for msg in messages if msg["role"] == "system"]
    return client.chat_update(
        channel=channel,
        ts=ts,
        text=text,
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": {"messages": system_messages, "user": user},
        },
    )


# ----------------------------
# Home tab
# ----------------------------

DEFAULT_HOME_TAB_MESSAGE = (
    "To enable this app in this Slack workspace, you need to save your OpenAI API key. "
    "Visit <https://platform.openai.com/account/api-keys|your developer page> to grap your key!"
)

DEFAULT_HOME_TAB_CONFIGURE_LABEL = "Configure"


def build_home_tab(
    openai_api_key: str,
    context: BoltContext,
    message: str = DEFAULT_HOME_TAB_MESSAGE,
) -> dict:
    original_sentences = "\n".join(
        [
            f"* {message}",
            f"* {DEFAULT_HOME_TAB_CONFIGURE_LABEL}",
            "* Can you proofread the following sentence without changing its meaning at all?",
            "* (Start a chat from scratch)",
            "* Start",
            "* Chat Templates",
            "* Configuration",
        ]
    )
    translated_sentences = list(
        map(
            lambda s: s.replace("* ", ""),
            translate(
                openai_api_key=openai_api_key,
                context=context,
                text=original_sentences,
            ).split("\n"),
        )
    )
    message = translated_sentences[0]
    configure_label = translated_sentences[1]
    proofreading = translated_sentences[2]
    from_scratch = translated_sentences[3]
    start = translated_sentences[4]
    chat_templates = translated_sentences[5]
    configuration = translated_sentences[6]

    return {
        "type": "home",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{configuration}*"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
                "accessory": {
                    "action_id": "configure",
                    "type": "button",
                    "text": {"type": "plain_text", "text": configure_label},
                    "style": "primary",
                    "value": "api_key",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{chat_templates}*"},
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": proofreading},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": start},
                    "value": proofreading,
                    "action_id": "templates-proofread",
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": from_scratch},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": start},
                    "value": " ",
                    "action_id": "templates-from-scratch",
                },
            },
        ],
    }


# ----------------------------
# Modals
# ----------------------------


def extract_state_value(payload: dict, block_id: str, action_id: str = "input") -> dict:
    state_values = payload["state"]["values"]
    return state_values[block_id][action_id]
