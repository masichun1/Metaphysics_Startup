from PIL import Image

from pet.assets import crop_to_content, scale_to_height, align_pair, chroma_key_remove


def _make_rgba(size, opaque_box):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(opaque_box[0], opaque_box[2]):
        for y in range(opaque_box[1], opaque_box[3]):
            img.putpixel((x, y), (255, 0, 0, 255))
    return img


def test_crop_to_content_trims_transparent_margins():
    img = _make_rgba((100, 100), (20, 30, 60, 80))
    cropped = crop_to_content(img)
    assert cropped.size == (40, 50)


def test_crop_to_content_fully_transparent_stays_same_size():
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    assert crop_to_content(img).size == (50, 50)


def test_scale_to_height():
    img = Image.new("RGBA", (100, 50), (255, 255, 255, 255))
    scaled = scale_to_height(img, 100)
    assert scaled.size == (200, 100)


def test_align_pair_produces_same_size_bottom_aligned():
    open_img = Image.new("RGBA", (100, 80), (255, 0, 0, 255))
    closed_img = Image.new("RGBA", (80, 60), (0, 255, 0, 255))
    a, b = align_pair(open_img, closed_img, height=100)
    assert a.size == b.size
    assert a.size[1] == 100


def test_chroma_key_removes_solid_background(tmp_path):
    src = tmp_path / "src.png"
    dst = tmp_path / "out.png"
    img = Image.new("RGB", (100, 100), (70, 115, 199))  # 蓝色背景
    for x in range(40, 60):
        for y in range(40, 60):
            img.putpixel((x, y), (255, 0, 0))  # 红色主体
    img.save(src)

    chroma_key_remove(str(src), str(dst))

    out = Image.open(dst)
    assert out.mode == "RGBA"
    assert out.getpixel((5, 5))[3] == 0          # 背景透明
    assert out.getpixel((50, 50))[3] > 200       # 主体不透明


def test_chroma_key_preserves_blue_subject(tmp_path):
    src = tmp_path / "src.png"
    dst = tmp_path / "out.png"
    img = Image.new("RGB", (100, 100), (70, 115, 199))  # 亮蓝背景
    for x in range(45, 55):
        for y in range(45, 55):
            img.putpixel((x, y), (32, 64, 160))  # 深蓝主体（远离背景蓝）
    img.save(src)

    chroma_key_remove(str(src), str(dst))

    out = Image.open(dst)
    assert out.getpixel((50, 50))[3] > 200       # 深蓝主体保留
