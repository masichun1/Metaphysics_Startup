"""One-time CLI: turn the two source photos into aligned transparent PNGs.

Usage (from the online/ directory):
    python -m pet.prepare_assets
"""
import os

from pet.assets import chroma_key_remove, crop_to_content, align_pair

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "assets", "src")
OUT = os.path.join(ROOT, "assets")
HEIGHT = 800  # output height in px before the app scales down at runtime


def main():
    os.makedirs(OUT, exist_ok=True)

    open_raw = os.path.join(OUT, "_cat_open_raw.png")
    closed_raw = os.path.join(OUT, "_cat_closed_raw.png")
    chroma_key_remove(os.path.join(SRC, "cat_open.png"), open_raw)
    chroma_key_remove(os.path.join(SRC, "cat_closed.png"), closed_raw)

    from PIL import Image

    open_img = crop_to_content(Image.open(open_raw))
    closed_img = crop_to_content(Image.open(closed_raw))
    open_img, closed_img = align_pair(open_img, closed_img, HEIGHT)

    open_img.save(os.path.join(OUT, "cat_open.png"))
    closed_img.save(os.path.join(OUT, "cat_closed.png"))

    os.remove(open_raw)
    os.remove(closed_raw)
    print("assets written:", os.path.join(OUT, "cat_open.png"),
          os.path.join(OUT, "cat_closed.png"))


if __name__ == "__main__":
    main()
