"""
업로드 이미지를 모바일 최적화 사이즈로 변환하고 원본을 삭제한다.
"""
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image


def optimize_for_mobile(uploaded_file) -> ContentFile:
    """
    업로드된 이미지를 모바일 최적화 크기로 리사이즈/압축한다.
    - 최대 너비: MOBILE_IMAGE_MAX_WIDTH (기본 1080)
    - 최대 높이: MOBILE_IMAGE_MAX_HEIGHT (기본 1920)
    - JPEG quality: MOBILE_IMAGE_QUALITY (기본 85)
    - EXIF 회전 보정 적용
    - 원본 파일은 호출측에서 삭제해야 함 (이 함수는 새 ContentFile만 반환)
    """
    max_w = getattr(settings, 'MOBILE_IMAGE_MAX_WIDTH', 1080)
    max_h = getattr(settings, 'MOBILE_IMAGE_MAX_HEIGHT', 1920)
    quality = getattr(settings, 'MOBILE_IMAGE_QUALITY', 85)

    img = Image.open(uploaded_file)

    # EXIF orientation 보정
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # RGBA → RGB (JPEG 저장용)
    if img.mode in ('RGBA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # 비율 유지 리사이즈
    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)

    # 파일명: 원본 stem + .jpg
    original_name = Path(getattr(uploaded_file, 'name', 'score.jpg')).stem
    new_name = f"{original_name}_opt.jpg"

    return ContentFile(buffer.read(), name=new_name)
