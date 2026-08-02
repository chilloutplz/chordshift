"""DB 없이 임시 업로드 파일 관리. 보정본 저장 전까지만 사용."""
import json
import time
import uuid
from pathlib import Path
from io import BytesIO

from django.conf import settings
from PIL import Image, ImageOps


TMP_DIR = Path(settings.MEDIA_ROOT) / 'tmp'
TMP_MAX_AGE_SEC = 6 * 3600  # 6시간
MAX_IMAGE_SIZE = 1080  # OCR 최적화: 긴 변 최대 1080px
JPEG_QUALITY = 85


def _ensure_dir():
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_old_temps(max_age=TMP_MAX_AGE_SEC):
    _ensure_dir()
    now = time.time()
    try:
        for p in TMP_DIR.iterdir():
            try:
                if now - p.stat().st_mtime > max_age:
                    p.unlink(missing_ok=True)
            except Exception:
                pass
    except FileNotFoundError:
        pass


def save_temp_image(content_file) -> dict:
    """ContentFile → tmp 저장 (1080px 리사이즈 + EXIF 보정 + RGB JPEG). 
    returns {temp_id, path, url}
    """
    cleanup_old_temps()
    _ensure_dir()
    temp_id = uuid.uuid4().hex
    name = f'{temp_id}.jpg'
    path = TMP_DIR / name

    try:
        # Django UploadedFile는 file pointer가 끝에 있을 수 있음
        if hasattr(content_file, 'seek'):
            try:
                content_file.seek(0)
            except Exception:
                pass

        img = Image.open(content_file)
        img = ImageOps.exif_transpose(img)

        # 리사이즈: 긴 변 기준 MAX_IMAGE_SIZE
        if max(img.size) > MAX_IMAGE_SIZE:
            img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.LANCZOS)

        # JPEG 저장을 위해 RGB로 변환
        if img.mode in ('RGBA', 'LA', 'P', 'CMYK'):
            # 투명 배경은 흰색으로
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img, mask=img.split()[-1])
                img = background
            else:
                img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        img.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)

    except Exception as e:
        # Pillow 실패 시 fallback: 원본 그대로 저장
        print(f"[temp_store] Pillow optimize failed: {e}, fallback to raw save")
        try:
            if hasattr(content_file, 'seek'):
                content_file.seek(0)
        except Exception:
            pass
        with open(path, 'wb') as out:
            if hasattr(content_file, 'chunks'):
                for chunk in content_file.chunks():
                    out.write(chunk)
            else:
                data = content_file.read() if hasattr(content_file, 'read') else content_file
                if isinstance(data, bytes):
                    out.write(data)
                else:
                    # BytesIO 등
                    out.write(data)

    meta = {'temp_id': temp_id, 'image': name, 'chords': [], 'ocr_raw_text': '', 'title': ''}
    (TMP_DIR / f'{temp_id}.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    return {
        'temp_id': temp_id,
        'path': str(path),
        'url': f'{settings.MEDIA_URL}tmp/{name}',
    }


def load_meta(temp_id: str) -> dict | None:
    path = TMP_DIR / f'{temp_id}.json'
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def save_meta(temp_id: str, meta: dict):
    _ensure_dir()
    (TMP_DIR / f'{temp_id}.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')


def image_path(temp_id: str) -> Path | None:
    meta = load_meta(temp_id)
    if not meta:
        p = TMP_DIR / f'{temp_id}.jpg'
        return p if p.is_file() else None
    p = TMP_DIR / meta.get('image', f'{temp_id}.jpg')
    return p if p.is_file() else None


def delete_temp(temp_id: str):
    for suffix in ('.jpg', '.json', '.png', '.jpeg'):
        try:
            (TMP_DIR / f'{temp_id}{suffix}').unlink(missing_ok=True)
        except Exception:
            pass
    meta = load_meta(temp_id)
    if meta and meta.get('image'):
        try:
            (TMP_DIR / meta['image']).unlink(missing_ok=True)
        except Exception:
            pass
    try:
        (TMP_DIR / f'{temp_id}.json').unlink(missing_ok=True)
    except Exception:
        pass
