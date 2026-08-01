"""DB 없이 임시 업로드 파일 관리. 보정본 저장 전까지만 사용."""
import json
import os
import time
import uuid
from pathlib import Path

from django.conf import settings


TMP_DIR = Path(settings.MEDIA_ROOT) / 'tmp'
TMP_MAX_AGE_SEC = 6 * 3600  # 6시간


def _ensure_dir():
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_old_temps(max_age=TMP_MAX_AGE_SEC):
    _ensure_dir()
    now = time.time()
    for p in TMP_DIR.iterdir():
        try:
            if now - p.stat().st_mtime > max_age:
                p.unlink(missing_ok=True)
        except Exception:
            pass


def save_temp_image(content_file) -> dict:
    """ContentFile → tmp 저장. returns {temp_id, path, relative_url}"""
    cleanup_old_temps()
    _ensure_dir()
    temp_id = uuid.uuid4().hex
    name = f'{temp_id}.jpg'
    path = TMP_DIR / name
    with open(path, 'wb') as out:
        for chunk in content_file.chunks() if hasattr(content_file, 'chunks') else [content_file.read()]:
            out.write(chunk)
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
        # try direct image
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
