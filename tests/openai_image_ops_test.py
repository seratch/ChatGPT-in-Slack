import pytest
from PIL import Image
from io import BytesIO
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import app.openai_image_ops as image_ops
from app.openai_image_ops import encode_image_and_guess_format

# Constants
IMAGE_DIMENSIONS = (100, 100)


def create_image_data(image_format):
    image = Image.new("RGB", IMAGE_DIMENSIONS, color="red")
    buffered = BytesIO()
    image.save(buffered, format=image_format)
    return buffered.getvalue()


@pytest.mark.parametrize(
    "image_format, expected_mode",
    [
        ("JPEG", "RGB"),
        ("PNG", "RGB"),
        ("GIF", "P"),
        ("BMP", "RGB"),
    ],
)
def test_encode_image_and_guess_format(image_format, expected_mode):
    mock_image_data = create_image_data(image_format)
    encoded_image, result_format = encode_image_and_guess_format(mock_image_data)

    # Decode the base64-encoded image to verify it was properly encoded
    decoded_image_data = base64.b64decode(encoded_image)
    decoded_image = Image.open(BytesIO(decoded_image_data))

    # Check if the decoded image format matches the original
    assert result_format == image_format
    assert decoded_image.format == image_format
    assert decoded_image.size == IMAGE_DIMENSIONS
    assert decoded_image.mode == expected_mode


def test_image_requests_use_azure_deployment(monkeypatch):
    images = MagicMock()
    images.generate.return_value = SimpleNamespace(
        data=[SimpleNamespace(url="https://example.com/image.png")]
    )
    images.create_variation.return_value = SimpleNamespace(
        data=[SimpleNamespace(url="https://example.com/variation.png")]
    )
    monkeypatch.setattr(
        image_ops,
        "create_openai_client",
        lambda context: SimpleNamespace(images=images),
    )
    context = {
        "OPENAI_IMAGE_GENERATION_MODEL": "dall-e-3",
        "OPENAI_API_TYPE": "azure",
        "OPENAI_DEPLOYMENT_ID": "image-deployment",
    }

    generated = image_ops.generate_image(
        context=context,  # type: ignore[arg-type]
        prompt="A test image",
        timeout_seconds=5,
    )
    variation = image_ops.generate_image_variations(
        context=context,  # type: ignore[arg-type]
        image=b"image",
        timeout_seconds=5,
    )

    assert generated == "https://example.com/image.png"
    assert variation == "https://example.com/variation.png"
    assert images.generate.call_args.kwargs["model"] == "image-deployment"
    assert images.create_variation.call_args.kwargs["model"] == "image-deployment"
