"""Image preparation: resize, JPEG conversion, EXIF stripping, orientation."""

import base64
import io

import pytest
from PIL import Image

from app.image_prep import InvalidImageError, prepare_image

ORIENTATION_TAG = 0x0112
GPS_TAG = 0x8825


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_large_image_is_resized_to_1024_longest_side() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), "blue").save(buf, format="JPEG")

    prepared = prepare_image(buf.getvalue())

    assert (prepared.width, prepared.height) == (1024, 768)
    assert _open(prepared.jpeg_bytes).format == "JPEG"


def test_small_image_is_not_upscaled() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200)).save(buf, format="JPEG")
    assert (prepare_image(buf.getvalue()).width, prepare_image(buf.getvalue()).height) == (300, 200)


def test_png_with_transparency_becomes_rgb_jpeg() -> None:
    buf = io.BytesIO()
    Image.new("RGBA", (50, 50), (255, 0, 0, 0)).save(buf, format="PNG")

    out = _open(prepare_image(buf.getvalue()).jpeg_bytes)

    assert out.format == "JPEG" and out.mode == "RGB"


def test_exif_is_stripped_and_orientation_applied() -> None:
    exif = Image.Exif()
    exif[ORIENTATION_TAG] = 6  # "rotate 90° clockwise to display"
    exif[0x010F] = "SecretCam"  # camera make
    buf = io.BytesIO()
    Image.new("RGB", (200, 100)).save(buf, format="JPEG", exif=exif.tobytes())

    prepared = prepare_image(buf.getvalue())

    assert (prepared.width, prepared.height) == (100, 200)  # pixels now upright
    assert len(_open(prepared.jpeg_bytes).getexif()) == 0
    assert b"SecretCam" not in prepared.jpeg_bytes


def test_data_url_is_base64_jpeg() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    prepared = prepare_image(buf.getvalue())

    prefix = "data:image/jpeg;base64,"
    assert prepared.data_url.startswith(prefix)
    assert base64.b64decode(prepared.data_url[len(prefix):]) == prepared.jpeg_bytes


def test_non_image_raises() -> None:
    with pytest.raises(InvalidImageError):
        prepare_image(b"definitely not an image")
