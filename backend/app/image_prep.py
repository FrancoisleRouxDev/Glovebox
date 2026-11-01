"""Image preparation: make uploads small, uniform and privacy-safe before they reach a model.

Steps:
1. Apply the EXIF orientation tag so the pixels are upright (phones often store
   rotated pixels and just set a flag).
2. Convert to RGB (drops alpha and handles PNG, palette and greyscale images).
3. Shrink so the longest side is at most 1024px. Smaller images are never enlarged.
4. Re-encode as JPEG at ~80% quality *without* EXIF, which removes GPS location,
   camera serial numbers and other metadata.
5. Base64-encode it as a `data:` URL, which is what OpenAI-compatible APIs accept.
"""

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE_PX = 1024
JPEG_QUALITY = 80


class InvalidImageError(ValueError):
    """The uploaded bytes are not an image Pillow can read."""


@dataclass(frozen=True)
class PreparedImage:
    jpeg_bytes: bytes
    width: int
    height: int

    @property
    def data_url(self) -> str:
        encoded = base64.b64encode(self.jpeg_bytes).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"


def prepare_image(
    raw: bytes, *, max_side: int = MAX_SIDE_PX, quality: int = JPEG_QUALITY
) -> PreparedImage:
    """Turn arbitrary uploaded image bytes into a small, EXIF-free JPEG."""
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()  # Force a full decode now so corrupt files fail here.
            # Must happen before EXIF is dropped, otherwise the photo ends up sideways.
            upright = ImageOps.exif_transpose(img)
            rgb = _to_rgb(upright)  # Always a new in-memory image, safe after `with` closes.
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError(f"Could not read image: {exc}") from exc

    # thumbnail() keeps the aspect ratio and only ever shrinks.
    rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    # No `exif=` argument, so Pillow writes no metadata.
    rgb.save(out, format="JPEG", quality=quality, optimize=True)
    return PreparedImage(jpeg_bytes=out.getvalue(), width=rgb.width, height=rgb.height)


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert to RGB, flattening any transparency onto a white background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")
