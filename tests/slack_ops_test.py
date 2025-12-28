import pytest
from unittest.mock import MagicMock

from slack_sdk.errors import SlackApiError

from app import slack_ops
from app.slack_constants import (
    SLACK_POST_MESSAGE_BYTE_LIMIT,
    SLACK_INTERIM_MESSAGE_BYTE_LIMIT,
    LOADING_SUFFIX,
)


@pytest.fixture(autouse=True)
def reset_reply_cache():
    """Clear per-test caches to avoid cross-test interference."""

    slack_ops._CACHE._final_hashes.clear()
    slack_ops._CACHE._final_inflight.clear()
    slack_ops._CACHE._last_sent.clear()
    yield
    slack_ops._CACHE._final_hashes.clear()
    slack_ops._CACHE._final_inflight.clear()
    slack_ops._CACHE._last_sent.clear()


def make_client(chat_update_side_effect=None):
    client = MagicMock()
    client.chat_update = MagicMock(side_effect=chat_update_side_effect)
    client.chat_postMessage = MagicMock()
    return client


def test_final_short_updates_in_place():
    client = make_client()
    text = "short reply"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    client.chat_update.assert_called_once()
    client.chat_postMessage.assert_not_called()


def test_final_long_posts_chunks_only():
    client = make_client(chat_update_side_effect=SlackApiError("err", {"error": "msg_too_long"}))
    text = "x" * (SLACK_POST_MESSAGE_BYTE_LIMIT + 5)

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    client.chat_update.assert_called_once()
    # Two chunks: full limit + remainder
    assert client.chat_postMessage.call_count == 2
    sent = "".join(call.kwargs["text"] for call in client.chat_postMessage.mock_calls)
    assert sent == text
    for call in client.chat_postMessage.mock_calls:
        assert len(call.kwargs["text"].encode("utf-8")) <= SLACK_POST_MESSAGE_BYTE_LIMIT


def test_msg_too_long_fallback_sends_only_tail():
    client = make_client(
        chat_update_side_effect=[
            SlackApiError("err", {"error": "msg_too_long"}),
            {"ok": True},
        ]
    )
    prefix = "already_sent"
    tail = "_tail"
    full_text = prefix + tail

    slack_ops._CACHE.remember_sent_text("TS1", prefix)

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=full_text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    # Best-effort: update the WIP message to the prefix to remove LOADING_SUFFIX
    assert client.chat_update.call_args_list[1].kwargs["text"] == prefix

    client.chat_postMessage.assert_called_once()
    assert client.chat_postMessage.call_args.kwargs["text"] == tail


def test_msg_too_long_without_prior_posts_full():
    client = make_client(chat_update_side_effect=SlackApiError("err", {"error": "msg_too_long"}))
    full_text = "complete"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=full_text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    client.chat_postMessage.assert_called_once()
    assert client.chat_postMessage.call_args.kwargs["text"] == full_text


def test_duplicate_final_is_skipped():
    client = make_client()
    text = "same reply"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )
    # Second time with same root/thread should short-circuit
    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_count == 1
    client.chat_postMessage.assert_not_called()


def test_final_msg_too_long_is_deduped_after_posting():
    client = make_client(chat_update_side_effect=SlackApiError("err", {"error": "msg_too_long"}))
    text = "hello"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )
    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_count == 1
    assert client.chat_postMessage.call_count == 1


def test_final_non_msg_too_long_error_is_not_deduped():
    client = make_client(
        chat_update_side_effect=[
            SlackApiError("err", {"error": "ratelimited"}),
            {"ok": True},
        ]
    )
    text = "retry me"

    with pytest.raises(SlackApiError):
        slack_ops.update_wip_message(
            client=client,
            channel="C1",
            ts="TS1",
            text=text,
            messages=[],
            user="U1",
            is_final=True,
            root_thread_ts="ROOT",
        )

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_count == 2


def test_msg_too_long_with_prior_but_prefix_update_fails_still_posts_only_tail():
    client = make_client(
        chat_update_side_effect=[
            SlackApiError("err", {"error": "msg_too_long"}),
            SlackApiError("err", {"error": "ratelimited"}),
        ]
    )
    prefix = "already_sent"
    tail = "_tail"
    full_text = prefix + tail

    slack_ops._CACHE.remember_sent_text("TS1", prefix)

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=full_text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_count == 2
    client.chat_postMessage.assert_called_once()
    assert client.chat_postMessage.call_args.kwargs["text"] == tail


def test_msg_too_long_with_mismatched_prior_and_prefix_update_fails_posts_full_text():
    client = make_client(
        chat_update_side_effect=[
            SlackApiError("err", {"error": "msg_too_long"}),
            SlackApiError("err", {"error": "ratelimited"}),
        ]
    )
    slack_ops._CACHE.remember_sent_text("TS1", "placeholder")
    full_text = "complete"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=full_text,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_count == 2
    client.chat_postMessage.assert_called_once()
    assert client.chat_postMessage.call_args.kwargs["text"] == full_text


def test_msg_too_long_with_slightly_mismatched_prior_and_prefix_update_fails_posts_tail():
    client = make_client(
        chat_update_side_effect=[
            SlackApiError("err", {"error": "msg_too_long"}),
            SlackApiError("err", {"error": "ratelimited"}),
        ]
    )
    prefix = "already_sent"
    tail = "_tail"
    slack_ops._CACHE.remember_sent_text("TS1", prefix + "*")

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=prefix + tail,
        messages=[],
        user="U1",
        is_final=True,
        root_thread_ts="ROOT",
    )

    client.chat_postMessage.assert_called_once()
    assert client.chat_postMessage.call_args.kwargs["text"] == tail


def test_interim_msg_too_long_does_not_fallback():
    client = make_client(chat_update_side_effect=SlackApiError("err", {"error": "msg_too_long"}))
    long_text = "x" * (SLACK_INTERIM_MESSAGE_BYTE_LIMIT + 50)

    resp = slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=long_text,
        messages=[],
        user="U1",
        is_final=False,
        root_thread_ts="ROOT",
    )

    # No fallback post when interim update is too long
    client.chat_postMessage.assert_not_called()
    assert isinstance(resp, dict)
    assert resp.get("error") == "msg_too_long"


def test_interim_update_appends_loading_suffix_and_caches_prefix():
    client = make_client()
    text = "abcDEF"

    slack_ops.update_wip_message(
        client=client,
        channel="C1",
        ts="TS1",
        text=text,
        messages=[],
        user="U1",
        is_final=False,
        root_thread_ts="ROOT",
    )

    assert client.chat_update.call_args.kwargs["text"].endswith(LOADING_SUFFIX)
    assert slack_ops._CACHE.get_last_sent_text("TS1") == text


def test_cache_remember_sent_text_does_not_regress():
    slack_ops._CACHE.remember_sent_text("TS1", "abcd")
    slack_ops._CACHE.remember_sent_text("TS1", "abc")
    assert slack_ops._CACHE.get_last_sent_text("TS1") == "abcd"


def test_final_claim_blocks_concurrent_sends():
    root_ts = "ROOT"
    text_hash = "hash"
    assert slack_ops._CACHE.try_claim_final_send(root_ts, text_hash) is True
    assert slack_ops._CACHE.try_claim_final_send(root_ts, text_hash) is False
