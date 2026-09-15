"""Asset preparation: background removal, cropping, and alignment."""
from PIL import Image


def crop_to_content(img: Image.Image) -> Image.Image:
    """Crop an RGBA image to the bounding box of its opaque pixels."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def scale_to_height(img: Image.Image, height: int) -> Image.Image:
    """Resize preserving aspect ratio so the height equals `height`."""
    w, h = img.size
    new_w = max(1, round(w * height / h))
    return img.resize((new_w, height), Image.LANCZOS)


def align_pair(open_img, closed_img, height):
    """Align two images to the same height, bottom-aligned, horizontally centered.

    Returns two RGBA images of identical size on transparent canvases.
    """
    a = scale_to_height(open_img.convert("RGBA"), height)
    b = scale_to_height(closed_img.convert("RGBA"), height)
    w = max(a.width, b.width)
    canvas_a = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    canvas_b = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    canvas_a.paste(a, ((w - a.width) // 2, height - a.height))
    canvas_b.paste(b, ((w - b.width) // 2, height - b.height))
    return canvas_a, canvas_b


def remove_background(src: str, dst: str) -> None:
    """Remove the background from an image using rembg; write a transparent PNG."""
    from rembg import remove, new_session

    session = new_session("isnet-general-use")
    with open(src, "rb") as f:
        input_bytes = f.read()
    output_bytes = remove(input_bytes, session=session)
    with open(dst, "wb") as f:
        f.write(output_bytes)
