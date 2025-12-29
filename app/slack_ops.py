from typing import Optional
from typing import List, Dict
import hashlib
import threading
from collections import OrderedDict

import requests

from slack_sdk.web import WebClient, SlackResponse
from slack_sdk.errors import SlackApiError
from slack_bolt import BoltContext

from app.env import IMAGE_FILE_ACCESS_ENABLED
from app.markdown_conversion import slack_to_markdown
from app.slack_constants import (
    SLACK_INTERIM_MESSAGE_BYTE_LIMIT,
    SLACK_POST_MESSAGE_BYTE_LIMIT,
    LOADING_SUFFIX,
)


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
        inclusive=True,
    ).get("messages", [])

    return messages[0] if len(messages) > 0 else None


def is_this_app_mentioned(context: BoltContext, parent_message: dict) -> bool:
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
                bot_response = client.bots_info(bot=reply.get("bot_id"))
                user = bot_response.get("bot", {}).get("user_id")
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
    metadata_payload = {"user": user, "system_message_count": len(system_messages)}
    chunks = _split_slack_text(loading_text)
    return client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=chunks[0],
        metadata={
            "event_type": "chat-gpt-convo",
            "event_payload": metadata_payload,
        },
    )


def update_wip_message(
    client: WebClient,
    channel: str,
    ts: str,
    text: str,
    messages: List[Dict[str, str]],
    user: str,
    is_final: bool = False,
    root_thread_ts: str = None,
) -> SlackResponse:
    """Update or finalize the WIP Slack message.

    - Interim: only updates the original message with a small chunk.
    - Final: tries chat.update once; on msg_too_long, posts only the remaining
      tail in thread-safe chunks, avoiding duplicate sends.
    """

    system_messages = [msg for msg in messages if msg["role"] == "system"]
    metadata_payload = {"user": user, "system_message_count": len(system_messages)}
    text = text or ""
    root_ts = root_thread_ts or ts

    # Interim updates: only update the original message with the first chunk.
    if not is_final:
        interim_prefix, interim_display = _build_interim_update(text)
        try:
            resp = client.chat_update(
                channel=channel,
                ts=ts,
                text=interim_display,
                metadata={
                    "event_type": "chat-gpt-convo",
                    "event_payload": metadata_payload,
                },
            )
            _CACHE.remember_sent_text(ts, interim_prefix)
            return resp
        except SlackApiError as e:
            # If interim update is still too long, skip posting a fallback to avoid flooding.
            if e.response.get("error") == "msg_too_long":
                return e.response
            raise

    # Final replies:
    text_hash = hashlib.md5(text.encode("utf-8") if text else b"").hexdigest()
    if not _CACHE.try_claim_final_send(root_ts, text_hash):
        return None

    final_marked = False
    try:
        try:
            resp = client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                metadata={
                    "event_type": "chat-gpt-convo",
                    "event_payload": metadata_payload,
                },
            )
            _CACHE.remember_sent_text(ts, text)
            _CACHE.mark_final_sent(root_ts, text_hash)
            final_marked = True
            return resp
        except SlackApiError as e:
            if e.response.get("error") != "msg_too_long":
                raise

        # Update failed with msg_too_long; post only the remaining tail to avoid duplication.
        prior = _CACHE.get_last_sent_text(ts)
        sent_prefix: Optional[str] = None
        if prior:
            common_prefix: Optional[str] = None
            if text.startswith(prior):
                sent_prefix = prior
                candidate_prefix = prior
            else:
                common_prefix = _common_prefix(prior, text)
                candidate_prefix = _split_slack_text(
                    text, byte_limit=SLACK_INTERIM_MESSAGE_BYTE_LIMIT
                )[0]

            # Best-effort: remove LOADING_SUFFIX and align the visible prefix with what we treat as sent.
            try:
                client.chat_update(
                    channel=channel,
                    ts=ts,
                    text=candidate_prefix,
                    metadata={
                        "event_type": "chat-gpt-convo",
                        "event_payload": metadata_payload,
                    },
                )
                if sent_prefix is None:
                    sent_prefix = candidate_prefix
            except SlackApiError:
                if sent_prefix is None:
                    sent_prefix = common_prefix

        remainder = _compute_remainder(sent_prefix, text)
        if remainder.strip() == "":
            _CACHE.mark_final_sent(root_ts, text_hash)
            final_marked = True
            return None

        chunks = _split_slack_text(remainder, byte_limit=SLACK_POST_MESSAGE_BYTE_LIMIT)
        response: SlackResponse = None  # type: ignore
        for chunk in chunks:
            response = client.chat_postMessage(
                channel=channel,
                thread_ts=root_ts,
                text=chunk,
                metadata={
                    "event_type": "chat-gpt-convo",
                    "event_payload": metadata_payload,
                },
            )

        _CACHE.mark_final_sent(root_ts, text_hash)
        final_marked = True
        return response
    finally:
        if not final_marked:
            _CACHE.release_final_claim(root_ts, text_hash)


def _split_slack_text(text: str, *, byte_limit: int = SLACK_POST_MESSAGE_BYTE_LIMIT) -> List[str]:
    """Split text into Slack-safe chunks based on UTF-8 byte length."""

    if text is None:
        return [""]

    chunks: List[str] = []
    current: List[str] = []
    current_bytes = 0

    for ch in text:
        ch_bytes = len(ch.encode("utf-8"))
        if current_bytes + ch_bytes > byte_limit:
            chunks.append("".join(current))
            current = [ch]
            current_bytes = ch_bytes
        else:
            current.append(ch)
            current_bytes += ch_bytes

    if current:
        chunks.append("".join(current))

    if not chunks:
        return [""]
    return chunks


def _common_prefix(a: str, b: str) -> str:
    """Return the longest common prefix of a and b."""

    max_len = min(len(a), len(b))
    idx = 0
    while idx < max_len and a[idx] == b[idx]:
        idx += 1
    return a[:idx]


def _build_interim_update(text: str) -> tuple[str, str]:
    """Return (sent_prefix, display_text) for interim chat.update.

    Always reserves room for the LOADING_SUFFIX to avoid partial suffixes and
    makes the stored prefix safe for final tail-only posting.
    """

    suffix_bytes = len(LOADING_SUFFIX.encode("utf-8"))
    prefix_limit = max(0, SLACK_INTERIM_MESSAGE_BYTE_LIMIT - suffix_bytes)
    prefix = _split_slack_text(text, byte_limit=prefix_limit)[0]
    return prefix, prefix + LOADING_SUFFIX


class _ReplyCache:
    """In-memory helpers to avoid duplicate final sends and track last updates."""

    def __init__(self, max_final: int = 200, max_last: int = 400):
        self._final_hashes: "OrderedDict[str, str]" = OrderedDict()
        self._final_inflight: "OrderedDict[str, str]" = OrderedDict()
        self._last_sent: "OrderedDict[str, str]" = OrderedDict()
        self._max_final = max_final
        self._max_last = max_last
        self._lock = threading.Lock()

    def try_claim_final_send(self, root_ts: str, text_hash: str) -> bool:
        with self._lock:
            if self._final_hashes.get(root_ts) == text_hash:
                return False
            if root_ts in self._final_inflight:
                return False
            self._final_inflight[root_ts] = text_hash
            if len(self._final_inflight) > self._max_final:
                self._final_inflight.popitem(last=False)
            return True

    def release_final_claim(self, root_ts: str, text_hash: str) -> None:
        with self._lock:
            if self._final_inflight.get(root_ts) == text_hash:
                self._final_inflight.pop(root_ts, None)

    def mark_final_sent(self, root_ts: str, text_hash: str) -> None:
        with self._lock:
            self._final_inflight.pop(root_ts, None)
            self._final_hashes[root_ts] = text_hash
            if len(self._final_hashes) > self._max_final:
                self._final_hashes.popitem(last=False)

    def remember_sent_text(self, ts: str, text: str) -> None:
        with self._lock:
            existing = self._last_sent.get(ts)
            if existing is None:
                self._last_sent[ts] = text
            elif len(text) > len(existing) and text.startswith(existing):
                self._last_sent[ts] = text
            else:
                return
            if len(self._last_sent) > self._max_last:
                self._last_sent.popitem(last=False)

    def get_last_sent_text(self, ts: str) -> Optional[str]:
        with self._lock:
            return self._last_sent.get(ts)


_CACHE = _ReplyCache()


def _compute_remainder(prior: Optional[str], full_text: str) -> str:
    """Return only the not-yet-sent tail of the full_text.

    If the prior text matches the start of full_text, only the remaining part
    is returned. Otherwise the entire full_text is returned.
    """

    if not full_text:
        return ""
    if not prior:
        return full_text
    return full_text[len(prior) :] if full_text.startswith(prior) else full_text


# ----------------------------
# Modals
# ----------------------------


def extract_state_value(payload: dict, block_id: str, action_id: str = "input") -> dict:
    state_values = payload["state"]["values"]
    return state_values[block_id][action_id]


# ----------------------------
# Files
# ----------------------------


def can_send_image_url_to_openai(context: BoltContext) -> bool:
    if IMAGE_FILE_ACCESS_ENABLED is False:
        return False
    bot_scopes = context.authorize_result.bot_scopes or []
    can_access_files = context and "files:read" in bot_scopes
    if can_access_files is False:
        return False

    openai_model = context.get("OPENAI_MODEL")
    # More supported models will come. This logic will need to be updated then.
    can_send_image_url = openai_model is not None and (
        openai_model.startswith("gpt-4o") or openai_model.startswith("gpt-4.1") or openai_model.startswith("gpt-5")
    )
    return can_send_image_url


def download_slack_image_content(image_url: str, bot_token: str) -> bytes:
    response = requests.get(
        image_url,
        headers={"Authorization": f"Bearer {bot_token}"},
    )
    if response.status_code != 200:
        error = f"Request to {image_url} failed with status code {response.status_code}"
        raise SlackApiError(error, response)

    content_type = response.headers["content-type"]
    if content_type.startswith("text/html"):
        error = f"You don't have the permission to download this file: {image_url}"
        raise SlackApiError(error, response)

    if not content_type.startswith("image/"):
        error = f"The responded content-type is not for image data: {content_type}"
        raise SlackApiError(error, response)

    return response.content
