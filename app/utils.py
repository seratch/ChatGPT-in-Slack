import base64
from io import BytesIO
import re

from PIL import Image
import requests
from app.env import (
    REDACT_EMAIL_PATTERN,
    REDACT_PHONE_PATTERN,
    REDACT_CREDIT_CARD_PATTERN,
    REDACT_SSN_PATTERN,
    REDACT_USER_DEFINED_PATTERN,
    REDACTION_ENABLED,
)


def redact_string(input_string: str) -> str:
    """
    Redact sensitive information from a string (inspired by @quangnhut123)

    Args:
        - input_string (str): the string to redact

    Returns:
        - str: the redacted string
    """
    output_string = input_string
    if REDACTION_ENABLED:
        output_string = re.sub(REDACT_EMAIL_PATTERN, "[EMAIL]", output_string)
        output_string = re.sub(
            REDACT_CREDIT_CARD_PATTERN, "[CREDIT CARD]", output_string
        )
        output_string = re.sub(REDACT_PHONE_PATTERN, "[PHONE]", output_string)
        output_string = re.sub(REDACT_SSN_PATTERN, "[SSN]", output_string)
        output_string = re.sub(REDACT_USER_DEFINED_PATTERN, "[REDACTED]", output_string)

    return output_string


def download_and_encode_image(image_url, token):
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(image_url, headers=headers)
    if response.status_code != 200:
        raise ValueError(f"Request to {image_url} failed with status code {response.status_code}")
    else:
        content_type = response.headers['content-type']
        if 'image' not in content_type:
            raise ValueError(f"Content type {content_type} is not an image")

        return encode_image(response.content)


def encode_image(image_data):
    try:
        image = Image.open(BytesIO(image_data))
        image_format = image.format
    except Exception as e:
        raise ValueError(f"Error opening image: {e}")
    return base64.b64encode(image_data).decode('utf-8'), image_format
