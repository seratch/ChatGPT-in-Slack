import os
import re
from slack_sdk.web import WebClient
from BingImageCreator import ImageGen
from app.env import (
    BING_AUTH_COOKIE,
)


def get_bing_images(prompt: str):
    gen = ImageGen(auth_cookie=BING_AUTH_COOKIE)
    imageList = gen.get_images(prompt)
    return imageList


def upload_image_to_slack(
    *,
    client: WebClient,
    prompt: str,
    channel_id: str,
    thread_ts: str,
    wip_reply_ts: str,
    user_id: str,
):
    image_list = get_bing_images(prompt=prompt)
    attachments = []
    for image_url in image_list:
        attachments.append(
            {
                "fallback": "Image preview",
                "image_url": image_url,
            }
        )

    client.chat_delete(
        channel=channel_id,
        ts=wip_reply_ts,
    )

    # Send the image URL as an attachment with a preview
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text="<@" + user_id + ">, Generated images of '" + prompt + "'",
        attachments=attachments,
    )


def censor_string(input_string: str):
    # Regex pattern to identify email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    # Regex pattern to identify phone numbers in format (123) 456-7890 or 123-456-7890
    phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"

    # Regex pattern to identify credit card numbers in format 1234-5678-9012-3456 or 1234567890123456
    credit_card_pattern = r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"

    # Regex pattern to identify social security numbers in format 123-45-6789
    ssn_pattern = r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b"

    # Regex pattern to identify access tokens in format Bearer <token> or <token>
    token_pattern = r"\bBearer\s+\S+|\b\S{64}\b"

    # Replace email addresses with [EMAIL]
    output_string = re.sub(email_pattern, "[EMAIL]", input_string)

    # Replace phone numbers with [PHONE]
    output_string = re.sub(phone_pattern, "[PHONE]", output_string)

    # Replace credit card numbers with [CREDIT CARD]
    output_string = re.sub(credit_card_pattern, "[CREDIT CARD]", output_string)

    # Replace social security numbers with [SSN]
    output_string = re.sub(ssn_pattern, "[SSN]", output_string)

    # Replace tokens with [TOKEN]
    output_string = re.sub(token_pattern, "[TOKEN]", output_string)

    return output_string
