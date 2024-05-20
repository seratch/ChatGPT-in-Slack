import logging
from typing import List, Tuple

import base64
from io import BytesIO
from PIL import Image

from app.slack_ops import download_slack_image_content


SUPPORTED_IMAGE_FORMATS = ["jpeg", "png", "gif"]


def append_image_content_if_exists(
    *,
    bot_token: str,
    files: List[dict],
    content: List[dict],
    logger: logging.Logger,
) -> None:
    if files is None or len(files) == 0:
        return

    for file in files:
        mime_type = file.get("mimetype")
        if mime_type is not None and mime_type.startswith("image"):
            file_url = file.get("url_private")
            image_bytes = download_slack_image_content(file_url, bot_token)
            encoded_image, image_format = encode_image_and_guess_format(image_bytes)
            if image_format.lower() not in SUPPORTED_IMAGE_FORMATS:
                skipped_file_message = (
                    f"Skipped an unsupported image format file "
                    f"(url: {file_url}, format: {image_format})"
                )
                logger.info(skipped_file_message)
                continue

            # https://platform.openai.com/docs/guides/vision?lang=python
            image_url_item = {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
            }
            content.append(image_url_item)


def encode_image_and_guess_format(image_data: bytes) -> Tuple[str, str]:
    try:
        image = Image.open(BytesIO(image_data))
        image_format = image.format
    except Exception as e:
        raise RuntimeError(f"Failed to open an image data: {e}")

    base64encoded_image_data = base64.b64encode(image_data).decode("utf-8")
    return base64encoded_image_data, image_format
