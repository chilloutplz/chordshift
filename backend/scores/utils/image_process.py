"""
업로드 이미지를 일정 규격으로 맞춘 뒤 JPEG로 저장.
- 최대 1080×1600 안에 비율 유지 리사이즈
- 가로가 짧은 이미지도 최소 너비 720까지는 맞춤(너무 작은 원본 대비)
- EXIF 회전 보정, RGB JPEG
"""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def optimize_for_mobile(uploaded_file) -> ContentFile:
    max_w = getattr(settings, 'MOBILE_IMAGE_MAX_WIDTH', 1080)
    max_h = getattr(settings, 'MOBILE_IMAGE_MAX_HEIGHT', 1600)
    min_w = getattr(settings, 'MOBILE_IMAGE_MIN_WIDTH', 720)
    quality = getattr(settings, 'MOBILE_IMAGE_QUALITY', 85)

    img = Image.open(uploaded_file)

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode in ('RGBA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size

    # 1) 너무 작으면 최소 너비까지 확대 (비율 유지)
    if w < min_w:
        scale = min_w / w
        img = img.resize((min_w, max(1, int(h * scale))), Image.Resampling.LANCZOS)
        w, h = img.size

    # 2) 최대 박스 안으로 축소
    if w > max_w or h > max_h:
        img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)

    original_name = Path(getattr(uploaded_file, 'name', 'score.jpg')).stem
    new_name = f"{original_name}_opt.jpg"
    return ContentFile(buffer.read(), name=new_name)
