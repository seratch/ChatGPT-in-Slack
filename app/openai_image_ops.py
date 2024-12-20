import logging
from typing import List, Tuple, Literal

import base64
from io import BytesIO
from PIL import Image

from app.openai_ops import create_openai_client
from app.slack_ops import download_slack_image_content
from slack_bolt import BoltContext


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


def generate_image(
    *,
    context: BoltContext,
    prompt: str,
    size: Literal["1024x1024", "1792x1024", "1024x1792"] = "1024x1024",
    quality: Literal["standard", "hd"] = "standard",
    style: Literal["vivid", "natural"] = "vivid",
    timeout_seconds: int,
) -> str:
    client = create_openai_client(context)
    response = client.images.generate(
        model=context["OPENAI_IMAGE_GENERATION_MODEL"],
        prompt=prompt,
        size=size,
        quality=quality,
        style=style,
        timeout=timeout_seconds,
        n=1,
    )
    return response.data[0].url


def generate_image_variations(
    *,
    context: BoltContext,
    image: bytes,
    size: Literal["256x256", "512x512", "1024x1024"] = "256x256",
    timeout_seconds: int,
) -> str:
    client = create_openai_client(context)
    response = client.images.create_variation(
        model="dall-e-2",
        image=BytesIO(image),
        size=size,
        timeout=timeout_seconds,
        n=1,
    )
    return response.data[0].url
