import pytest
from PIL import Image
from io import BytesIO
import base64
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
