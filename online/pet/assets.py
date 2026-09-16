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


def chroma_key_remove(src: str, dst: str, threshold: int = 70, feather: int = 25) -> None:
    """Remove a solid-color background via chroma key; write a transparent PNG.

    Samples the background color from the four corners and sets each pixel's
    alpha by its color distance from that background. Best for images with a
    flat solid backdrop (e.g. the cartoon cat's blue background); use
    remove_background (rembg) for photos with complex backgrounds.
    """
    import numpy as np

    img = Image.open(src).convert("RGB")
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    bg = np.array([arr[3, 3], arr[3, w - 4], arr[h - 4, 3], arr[h - 4, w - 4]]).mean(axis=0)
    dist = np.abs(arr - bg).sum(axis=2)
    alpha = np.clip((dist - threshold) / feather * 255, 0, 255).astype(np.uint8)
    rgba = np.dstack([arr.astype(np.uint8), alpha])
    Image.fromarray(rgba, "RGBA").save(dst)
