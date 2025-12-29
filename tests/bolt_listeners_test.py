import logging
from unittest.mock import MagicMock

from app import bolt_listeners


def make_context(*, openai_api_key: str = "key"):
    context = MagicMock()
    context.channel_id = "C1"
    context.bot_user_id = "BUSER"
    context.bot_id = "BID"
    context.user_id = "U1"
    context.actor_user_id = "U1"
    context.bot_token = "xoxb-test"

    def _get(key, default=None):
        values = {"OPENAI_API_KEY": openai_api_key}
        return values.get(key, default)

    context.get.side_effect = _get
    return context


def test_app_mention_in_thread_uses_thread_root_ts(monkeypatch):
    context = make_context()
    client = MagicMock()
    logger = logging.getLogger(__name__)
    payload = {"ts": "CHILD", "thread_ts": "ROOT", "text": "<@BUSER> hi"}

    monkeypatch.setattr(bolt_listeners, "find_parent_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(bolt_listeners, "translate", lambda **kwargs: "loading")
    client.conversations_replies.return_value = {"messages": []}

    post_wip_message_mock = MagicMock()

    def fake_post_wip_message(**kwargs):
        post_wip_message_mock(**kwargs)
        return {"message": {"ts": "WIP", "thread_ts": kwargs["thread_ts"]}}

    monkeypatch.setattr(bolt_listeners, "post_wip_message", fake_post_wip_message)

    def fake_messages_within_context_window(messages, context):
        return ([messages[0]], 0, 0)

    monkeypatch.setattr(bolt_listeners, "messages_within_context_window", fake_messages_within_context_window)

    update_wip_message_mock = MagicMock()
    monkeypatch.setattr(bolt_listeners, "update_wip_message", update_wip_message_mock)

    bolt_listeners.respond_to_app_mention(
        context=context,
        payload=payload,
        client=client,
        logger=logger,
    )

    assert post_wip_message_mock.call_args.kwargs["thread_ts"] == "ROOT"
    assert update_wip_message_mock.call_args.kwargs["root_thread_ts"] == "ROOT"


def test_threaded_channel_message_uses_thread_root_ts(monkeypatch):
    context = make_context()
    client = MagicMock()
    logger = logging.getLogger(__name__)
    payload = {
        "ts": "CHILD",
        "thread_ts": "ROOT",
        "channel_type": "channel",
        "text": "hello",
    }

    monkeypatch.setattr(bolt_listeners, "translate", lambda **kwargs: "loading")
    monkeypatch.setattr(bolt_listeners, "can_send_image_url_to_openai", lambda *args, **kwargs: False)

    client.conversations_replies.return_value = {
        "messages": [
            {
                "ts": "ROOT",
                "user": "U2",
                "text": "<@BUSER> question",
                "metadata": {},
            }
        ]
    }

    post_wip_message_mock = MagicMock()

    def fake_post_wip_message(**kwargs):
        post_wip_message_mock(**kwargs)
        return {"message": {"ts": "WIP", "thread_ts": kwargs.get("thread_ts")}}

    monkeypatch.setattr(bolt_listeners, "post_wip_message", fake_post_wip_message)

    def fake_messages_within_context_window(messages, context):
        return ([messages[0]], 0, 0)

    monkeypatch.setattr(bolt_listeners, "messages_within_context_window", fake_messages_within_context_window)

    update_wip_message_mock = MagicMock()
    monkeypatch.setattr(bolt_listeners, "update_wip_message", update_wip_message_mock)

    bolt_listeners.respond_to_new_message(
        context=context,
        payload=payload,
        client=client,
        logger=logger,
    )

    assert post_wip_message_mock.call_args.kwargs["thread_ts"] == "ROOT"
    assert update_wip_message_mock.call_args.kwargs["root_thread_ts"] == "ROOT"

