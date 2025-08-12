import json
from typing import Optional, List
from slack_bolt import BoltContext
from slack_sdk.errors import SlackApiError
from app.i18n import translate
from app.openai_constants import (
    GPT_4O_MODEL,
    GPT_4O_MINI_MODEL,
    GPT_4_1_MODEL,
    GPT_4_1_MINI_MODEL,
    GPT_5_CHAT_LATEST_MODEL,
)
from app.slack_constants import TIMEOUT_ERROR_MESSAGE, MAX_MESSAGE_LENGTH
from app.slack_ops import extract_state_value


# ----------------------------
# Translate
# ----------------------------


def _build_translation_result_modal(blocks: List[dict]) -> dict:
    return {
        "type": "modal",
        "callback_id": "translate-message",
        "title": {"type": "plain_text", "text": "Translate the thread"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks,
    }


def build_translation_result_modal(*, context: BoltContext, payload: dict) -> dict:
    text = json.loads(payload["private_metadata"]).get("text")
    openai_api_key = context.get("OPENAI_API_KEY")

    try:
        translated = translate(
            openai_api_key=openai_api_key, context=context, text=text
        )
        blocks = []
        remaining = translated

        while remaining:
            chunk = remaining[: MAX_MESSAGE_LENGTH - 6]
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{chunk}```"},
                }
            )
            remaining = remaining[MAX_MESSAGE_LENGTH - 6 :]

        return _build_translation_result_modal(blocks)
    except Exception as e:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *My apologies!* An error occurred while translating the text: `{e}`",
                },
            }
        ]
        return _build_translation_result_modal(blocks)


def build_translation_modal(*, body: dict) -> dict:
    text = body.get("message", {}).get("text")

    if len(text) >= (MAX_MESSAGE_LENGTH - 6):  # 6 is for the Markdown formatting
        return build_translation_wip_modal(
            text="Text is too long. Translation is only available for text under 3000 characters."
        )

    return {
        "type": "modal",
        "callback_id": "translate-message",
        "title": {"type": "plain_text", "text": "Translate the thread"},
        "private_metadata": json.dumps({"text": text}),
        "submit": {"type": "plain_text", "text": "Translate"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{text}```"},
            }
        ],
    }


def build_translation_wip_modal(text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "translate-message",
        "title": {"type": "plain_text", "text": "Translate the thread"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "plain_text", "text": text},
            },
        ],
    }


# ----------------------------
# Summarize
# ----------------------------


def build_summarize_option_modal(*, context: BoltContext, body: dict) -> dict:
    openai_api_key = context.get("OPENAI_API_KEY")
    prompt = translate(
        openai_api_key=openai_api_key,
        context=context,
        text=(
            "All replies posted in a Slack thread will be provided below. "
            "Could you summarize the discussion in 200 characters or less?"
        ),
    )
    thread_ts = body["message"].get("thread_ts", body["message"].get("ts"))
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
        context.client.conversations_replies(
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
    return view


def _build_summarize_wip_modal(section_text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "request-thread-summary",
        "title": {"type": "plain_text", "text": "Summarize the thread"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "plain_text", "text": section_text},
            },
        ],
    }


def build_summarize_wip_modal() -> dict:
    return _build_summarize_wip_modal(
        "Got it! Working on the summary now ... :hourglass:"
    )


def build_summarize_message_modal() -> dict:
    return _build_summarize_wip_modal(
        "Got it! Once the summary is ready, I will post it in the thread."
    )


def _build_summary_result_modal(section_text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "request-thread-summary",
        "title": {"type": "plain_text", "text": "Summarize the thread"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text or " "},
            },
        ],
    }


def build_summarize_result_modal(*, here_is_summary: str, summary: str) -> dict:
    return _build_summary_result_modal(f"{here_is_summary}\n\n{summary}")


def build_summarize_timeout_error_modal() -> dict:
    return _build_summary_result_modal(TIMEOUT_ERROR_MESSAGE)


def build_summarize_error_modal(e: Exception) -> dict:
    return _build_summary_result_modal(
        ":warning: *My apologies!* "
        f"An error occurred while generating the summary of this thread: `{e}`"
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
    *,
    openai_api_key: Optional[str],
    context: BoltContext,
    message: str = DEFAULT_HOME_TAB_MESSAGE,
    single_workspace_mode: bool = False,
) -> dict:
    original_sentences = "\n".join(
        [
            f"* {message}",
            f"* {DEFAULT_HOME_TAB_CONFIGURE_LABEL}",
            "* Can you proofread the following sentence without changing its meaning?",
            "* (Start a chat from scratch)",
            "* Start",
            "* Chat Templates",
            "* Configuration",
            "* Can you generate an image as I instruct you?",
            "* Can you generate variations for my images?",
        ]
    )
    translated_sentences = list(
        map(
            lambda s: s.replace("* ", ""),
            filter(
                # Consider that translation results might contain extra newlines
                lambda s: s != "",
                translate(
                    openai_api_key=openai_api_key,
                    context=context,
                    text=original_sentences,
                ).split("\n"),
            ),
        )
    )
    message = translated_sentences[0]
    configure_label = translated_sentences[1]
    proofreading = translated_sentences[2]
    from_scratch = translated_sentences[3]
    start = translated_sentences[4]
    chat_templates = translated_sentences[5]
    configuration = translated_sentences[6]
    image_generation = translated_sentences[7]
    image_variations = translated_sentences[8]

    blocks = []
    if single_workspace_mode is False:
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{configuration}* "},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message or " "},
                    "accessory": {
                        "action_id": "configure",
                        "type": "button",
                        "text": {"type": "plain_text", "text": configure_label or " "},
                        "style": "primary",
                        "value": "api_key",
                    },
                },
            ]
        )
    if openai_api_key is not None:
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{chat_templates}* "},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": proofreading or " "},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": start or " "},
                        "value": proofreading or " ",
                        "action_id": "templates-proofread",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": image_generation or " "},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": start or " "},
                        "value": image_generation or " ",
                        "action_id": "templates-image-generation",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": image_variations or " "},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": start or " "},
                        "value": image_variations or " ",
                        "action_id": "templates-image-variations",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": from_scratch or " "},
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": start or " "},
                        "value": " ",
                        "action_id": "templates-from-scratch",
                    },
                },
            ]
        )

    return {"type": "home", "blocks": blocks}


def build_configure_modal(context: BoltContext) -> dict:
    already_set_api_key = context.get("OPENAI_API_KEY")
    saved_model = context.get("OPENAI_MODEL")
    api_key_text = "Save your OpenAI API key:"
    submit = "Submit"
    cancel = "Cancel"
    if already_set_api_key is not None:
        api_key_text = translate(
            openai_api_key=already_set_api_key, context=context, text=api_key_text
        )
        submit = translate(
            openai_api_key=already_set_api_key, context=context, text=submit
        )
        cancel = translate(
            openai_api_key=already_set_api_key, context=context, text=cancel
        )

    options = [
        {
            "text": {"type": "plain_text", "text": "GPT-5-chat-latest"},
            "value": GPT_5_CHAT_LATEST_MODEL,
        },
        {
            "text": {"type": "plain_text", "text": "GPT-4.1"},
            "value": GPT_4_1_MODEL,
        },
        {
            "text": {"type": "plain_text", "text": "GPT-4.1-mini"},
            "value": GPT_4_1_MINI_MODEL,
        },
        {
            "text": {"type": "plain_text", "text": "GPT-4o"},
            "value": GPT_4O_MODEL,
        },
        {
            "text": {"type": "plain_text", "text": "GPT-4o-mini"},
            "value": GPT_4O_MINI_MODEL,
        },
    ]
    return {
        "type": "modal",
        "callback_id": "configure",
        "title": {"type": "plain_text", "text": "OpenAI API Key"},
        "submit": {"type": "plain_text", "text": submit},
        "close": {"type": "plain_text", "text": cancel},
        "blocks": [
            {
                "type": "input",
                "block_id": "api_key",
                "label": {"type": "plain_text", "text": api_key_text or " "},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Paste your API key starting with sk-...",
                    },
                },
                "optional": already_set_api_key is not None,
            },
            {
                "type": "input",
                "block_id": "model",
                "label": {"type": "plain_text", "text": "OpenAI Model"},
                "element": {
                    "type": "static_select",
                    "action_id": "input",
                    "options": options,
                    **(
                        {
                            "initial_option": next(
                                (opt for opt in options if opt["value"] == saved_model),
                                options[0],
                            )
                        }
                        if already_set_api_key is not None
                        else {"initial_option": options[0]}
                    ),
                },
            },
        ],
    }


#
# Proofread user inputs
#


def build_proofreading_input_modal(prompt: str, tone_and_voice: Optional[str]) -> dict:
    tone_and_voice_options = [
        {"text": {"type": "plain_text", "text": persona}, "value": persona}
        for persona in [
            "Friendly and humble individual in Slack",
            "Software developer discussing issues on GitHub",
            "Engaging yet insightful social media poster",
            "Customer service representative handling inquiries",
            "Marketing manager creating a product launch script",
            "Technical writer documenting software procedures",
            "Product manager creating a roadmap",
            "HR manager composing a job description",
            "Public relations officer drafting statements",
            "Scientific researcher publicizing findings",
            "Travel blogger sharing experiences",
            "Speechwriter crafting a persuasive speech",
        ]
    ]

    modal: dict = {
        "type": "modal",
        "callback_id": "proofread",
        "title": {"type": "plain_text", "text": "Proofreading"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": json.dumps({"prompt": prompt}),
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": prompt or " "},
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
            {
                "type": "input",
                "block_id": "tone_and_voice",
                "label": {"type": "plain_text", "text": "Tone and voice"},
                "element": {
                    "type": "static_select",
                    "action_id": "input",
                    "options": tone_and_voice_options,
                },
                "optional": True,
            },
        ],
    }
    initial_option = tone_and_voice_options[0]
    if tone_and_voice is not None:
        matched_items = [
            o for o in tone_and_voice_options if o["value"] == tone_and_voice
        ]
        if matched_items and len(matched_items) >= 1:
            initial_option = matched_items[0]
    modal["blocks"][2]["element"]["initial_option"] = initial_option
    return modal


def build_proofreading_wip_modal(
    payload: dict, context: BoltContext, text: str
) -> dict:
    return {
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
    }


def _build_proofreading_result_modal(
    *,
    private_metadata: str,
    blocks: list,
) -> dict:
    return {
        "type": "modal",
        "callback_id": "proofread-result",
        "title": {"type": "plain_text", "text": "Proofreading"},
        "submit": {"type": "plain_text", "text": "Try Another"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": private_metadata,
        "blocks": blocks,
    }


def build_proofreading_result_modal(
    *,
    context: BoltContext,
    result: str,
    payload: dict,
) -> dict:
    original_text = extract_state_value(payload, "original_text")["value"]
    tone_and_voice = extract_state_value(payload, "tone_and_voice")
    tone_and_voice = (
        tone_and_voice["selected_option"].get("value")
        if tone_and_voice.get("selected_option")
        else None
    )
    text = "\n".join(map(lambda s: f">{s}", original_text.split("\n")))
    private_metadata = payload["private_metadata"]
    if tone_and_voice is not None:
        pm = json.loads(payload["private_metadata"])
        pm["tone_and_voice"] = tone_and_voice
        private_metadata = json.dumps(pm)

    blocks = [
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
            "text": {"type": "mrkdwn", "text": f"{text}\n\n{result}"},
        },
    ]
    if tone_and_voice is not None:
        context_block = {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Tone and voice: {tone_and_voice}"}
            ],
        }
        blocks.append(context_block)

    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": " "},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Send this result in DM"},
                "value": "clicked",
                "action_id": "send-proofread-result-in-dm",
            },
        }
    )
    return _build_proofreading_result_modal(
        private_metadata=private_metadata,
        blocks=blocks,
    )


def build_proofreading_timeout_error_modal(
    *,
    payload: dict,
    text: str,
) -> dict:
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{text}\n\n{TIMEOUT_ERROR_MESSAGE}"},
        },
    ]
    return _build_proofreading_result_modal(
        private_metadata=payload["private_metadata"],
        blocks=blocks,
    )


def build_proofreading_error_modal(
    *,
    payload: dict,
    text: str,
    e: Exception,
) -> dict:
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{text}\n\n:warning: *My apologies!* "
                f"An error occurred while generating the summary of this thread: `{e}`",
            },
        },
    ]
    return _build_proofreading_result_modal(
        private_metadata=payload["private_metadata"],
        blocks=blocks,
    )


def build_proofreading_result_no_dm_button_modal(
    *,
    private_metadata: str,
    blocks: list,
) -> dict:
    return {
        "type": "modal",
        "callback_id": "proofread-result",
        "title": {"type": "plain_text", "text": "Proofreading"},
        "submit": {"type": "plain_text", "text": "Try Another"},
        "close": {"type": "plain_text", "text": "Close"},
        "private_metadata": private_metadata,
        "blocks": blocks,
    }


#
# Image generation
#


def build_image_generation_input_modal(prompt: str) -> dict:
    size_options = [
        {"text": {"type": "plain_text", "text": v}, "value": v}
        for v in ["1024x1024", "1792x1024", "1024x1792"]
    ]
    quality_options = [
        {"text": {"type": "plain_text", "text": v}, "value": v}
        for v in ["standard", "hd"]
    ]
    style_options = [
        {"text": {"type": "plain_text", "text": v}, "value": v}
        for v in ["vivid", "natural"]
    ]
    return {
        "type": "modal",
        "callback_id": "image-generation",
        "title": {"type": "plain_text", "text": "Image Generation"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": prompt or " "},
            },
            {
                "type": "input",
                "block_id": "image_generation_prompt",
                "label": {"type": "plain_text", "text": "Prompt"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "multiline": True,
                },
            },
            # https://platform.openai.com/docs/api-reference/images/create
            {
                "type": "input",
                "block_id": "size",
                "label": {"type": "plain_text", "text": "Size"},
                "element": {
                    "type": "static_select",
                    "options": size_options,
                    "initial_option": size_options[0],
                    "action_id": "input",
                },
            },
            {
                "type": "input",
                "block_id": "quality",
                "label": {"type": "plain_text", "text": "Quality"},
                "element": {
                    "type": "static_select",
                    "options": quality_options,
                    "initial_option": quality_options[0],
                    "action_id": "input",
                },
            },
            {
                "type": "input",
                "block_id": "style",
                "label": {"type": "plain_text", "text": "Style"},
                "element": {
                    "type": "static_select",
                    "options": style_options,
                    "initial_option": style_options[0],
                    "action_id": "input",
                },
            },
        ],
    }


def build_image_generation_wip_modal() -> dict:
    return build_image_generation_text_modal(
        "Working on this now ... :hourglass:\n\n"
        "Once the image is ready, this app will send it to you in a DM. "
        "If you don't want to wait here, you can close this modal at any time."
    )


def build_image_generation_result_modal(blocks: list) -> dict:
    return {
        "type": "modal",
        "callback_id": "image-generation",
        "title": {"type": "plain_text", "text": "Image Generation"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks,
    }


def build_image_generation_result_blocks(
    *,
    text: str,
    image_url: str,
    model: str,
) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        },
        {
            "type": "image",
            "slack_file": {"url": image_url},
            "alt_text": f"Generated by {model}",
        },
    ]


def build_image_generation_text_modal(section_text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "image-generation",
        "title": {"type": "plain_text", "text": "Image Generation"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text or " "},
            },
        ],
    }


def build_image_variations_input_modal(prompt: str) -> dict:
    size_options = [
        {"text": {"type": "plain_text", "text": v}, "value": v}
        for v in ["256x256", "512x512", "1024x1024"]
    ]
    return {
        "type": "modal",
        "callback_id": "image-variations",
        "title": {"type": "plain_text", "text": "Image Variations"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": prompt or " "},
            },
            {
                "type": "input",
                "block_id": "input_files",
                "label": {"type": "plain_text", "text": "Files to edit"},
                "element": {
                    "type": "file_input",
                    "action_id": "input",
                    "filetypes": ["png"],
                    "max_files": 5,
                },
            },
            # https://platform.openai.com/docs/api-reference/images/create
            {
                "type": "input",
                "block_id": "size",
                "label": {"type": "plain_text", "text": "Size"},
                "element": {
                    "type": "static_select",
                    "options": size_options,
                    "initial_option": size_options[0],
                    "action_id": "input",
                },
            },
        ],
    }


def build_image_variations_wip_modal() -> dict:
    return build_image_variations_text_modal(
        "Working on this now ... :hourglass:\n\n"
        "Once the images are ready, this app will send them to you in a DM. "
        "If you don't want to wait here, you can close this modal at any time."
    )


def build_image_variations_result_modal(blocks: list) -> dict:
    return {
        "type": "modal",
        "callback_id": "image-variations",
        "title": {"type": "plain_text", "text": "Image Variations"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": blocks,
    }


def build_image_variations_result_blocks(
    *,
    text: str,
    generated_image_urls: List[str],
    model: str,
) -> list[dict]:
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        },
    ]
    for url in generated_image_urls:
        blocks.append(
            {
                "type": "image",
                "slack_file": {"url": url},
                "alt_text": f"Generated by {model}",
            }
        )
    return blocks


def build_image_variations_text_modal(section_text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "image_variations",
        "title": {"type": "plain_text", "text": "Image Variations"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text or " "},
            },
        ],
    }


#
# From-scratch modal
#


def build_from_scratch_modal() -> dict:
    return {
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
    }


def _build_from_scratch_modal(section_text: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "chat-from-scratch",
        "title": {"type": "plain_text", "text": "ChatGPT"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text or " "},
            },
        ],
    }


def build_from_scratch_wip_modal(text: str) -> dict:
    return _build_from_scratch_modal(f"{text}\n\nWorking on this now ... :hourglass:")


def build_from_scratch_result_modal(
    *,
    text: str,
    result: str,
) -> dict:
    return _build_from_scratch_modal(f"{text}\n\n{result}")


def build_from_scratch_timeout_modal(text: str) -> dict:
    return _build_from_scratch_modal(f"{text}\n\n{TIMEOUT_ERROR_MESSAGE}")


def build_from_scratch_error_modal(*, text: str, e: Exception) -> dict:
    return _build_from_scratch_modal(
        f"{text}\n\n:warning: *My apologies!* "
        f"An error occurred while generating the summary of this thread: `{e}`"
    )
