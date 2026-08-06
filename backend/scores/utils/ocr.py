"""
Google Cloud Vision OCR → 줄(line) 단위 코드 그룹
RapidOCR 제거 → 서버 메모리 부담 0
"""
import base64
import os
import re
import uuid
from pathlib import Path

import requests
from django.conf import settings

CHORD_FULL = re.compile(
    r'^([A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add|M|°)?(?:\d{1,2})?(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9|add11)?(?:/[A-G](?:#|b)?)?)$',
    re.IGNORECASE,
)
CHORD_IN_TEXT = re.compile(
    r'\b([A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add|M)?(?:\d{0,2})?(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9)?(?:/[A-G](?:#|b)?)?)\b',
    re.IGNORECASE,
)

LINE_Y_THRESHOLD = 0.025  # 같은 줄 판단 y 차이

# Google Vision 무료 티어 (월 단위, TEXT_DETECTION 1 unit = 1 image)
OCR_MONTHLY_LIMIT = int(os.getenv('OCR_MONTHLY_LIMIT', '1000'))


class OcrQuotaExceeded(Exception):
    """월간 OCR 한도 초과"""
    def __init__(self, used: int, limit: int):
        self.used = used
        self.limit = limit
        super().__init__(f'OCR 월간 한도 초과 ({used}/{limit})')


class OcrConfigError(Exception):
    """API 키/설정 누락"""
    pass


def _looks_like_chord(token: str) -> bool:
    token = (token or '').strip()
    if not token or len(token) > 12:
        return False
    return bool(CHORD_FULL.match(token))


def _vertices_to_norm(vertices, img_w: int, img_h: int):
    if not vertices or not img_w or not img_h:
        return None
    try:
        xs, ys = [], []
        for v in vertices:
            if 'x' in v:
                xs.append(float(v.get('x', 0)))
            if 'y' in v:
                ys.append(float(v.get('y', 0)))
        if not xs or not ys:
            return None
        return {
            'x': round(min(xs) / img_w, 5),
            'y': round(min(ys) / img_h, 5),
            'w': round(max(max(xs) - min(xs), 1) / img_w, 5),
            'h': round(max(max(ys) - min(ys), 1) / img_h, 5),
        }
    except Exception:
        return None


def _flat_chord_hits(ocr_lines: list) -> list:
    hits = []
    for line in ocr_lines:
        text = (line.get('text') or '').strip()
        norm = line.get('norm')
        conf = line.get('confidence', 0.9)
        y = (norm or {}).get('y', 0.1)
        x = (norm or {}).get('x', 0.05)
        if _looks_like_chord(text):
            hits.append({'chord': text, 'x': x, 'y': y, 'confidence': conf})
            continue
        for m in CHORD_IN_TEXT.finditer(text):
            token = m.group(1)
            if not _looks_like_chord(token):
                continue
            if norm:
                ratio = m.start() / max(len(text), 1)
                cx = round(norm['x'] + norm['w'] * ratio, 5)
                cy = norm['y']
            else:
                cx, cy = 0.05, 0.1
            hits.append({'chord': token, 'x': cx, 'y': cy, 'confidence': conf})
    return hits


def group_hits_into_lines(hits: list) -> list:
    if not hits:
        return []
    sorted_hits = sorted(hits, key=lambda h: (h.get('y', 0), h.get('x', 0)))
    clusters = []
    for h in sorted_hits:
        placed = False
        for cl in clusters:
            avg_y = sum(c['y'] for c in cl) / len(cl)
            if abs(h['y'] - avg_y) <= LINE_Y_THRESHOLD:
                cl.append(h)
                placed = True
                break
        if not placed:
            clusters.append([h])
    lines_out = []
    for cl in clusters:
        cl.sort(key=lambda c: c.get('x', 0))
        y = sum(c['y'] for c in cl) / len(cl)
        items = [
            {
                'id': uuid.uuid4().hex[:8],
                'chord': c['chord'],
                't': round(max(0.02, min(0.98, c['x'])), 5),
                'x_abs': round(c['x'], 5),
            }
            for c in cl
        ]
        lines_out.append({
            'id': 'L' + uuid.uuid4().hex[:6],
            'y': round(min(0.98, max(0.02, y)), 5),
            'xStart': 0.01,
            'xEnd': 0.99,
            'height': 0.028,
            'items': items,
        })
    lines_out.sort(key=lambda L: L['y'])
    return lines_out


def get_usage_stats() -> dict:
    """이번 달 OCR 사용량 (DB 기준)"""
    from scores.models import OcrUsage
    from django.utils import timezone

    now = timezone.now()
    month_key = now.strftime('%Y-%m')
    obj, _ = OcrUsage.objects.get_or_create(
        month=month_key,
        defaults={'count': 0},
    )
    limit = OCR_MONTHLY_LIMIT
    return {
        'month': month_key,
        'used': obj.count,
        'limit': limit,
        'remaining': max(0, limit - obj.count),
        'exceeded': obj.count >= limit,
    }


def _increment_usage() -> dict:
    from scores.models import OcrUsage
    from django.db.models import F
    from django.utils import timezone

    month_key = timezone.now().strftime('%Y-%m')
    obj, _ = OcrUsage.objects.get_or_create(
        month=month_key,
        defaults={'count': 0},
    )
    OcrUsage.objects.filter(pk=obj.pk).update(count=F('count') + 1)
    obj.refresh_from_db()
    limit = OCR_MONTHLY_LIMIT
    return {
        'month': month_key,
        'used': obj.count,
        'limit': limit,
        'remaining': max(0, limit - obj.count),
        'exceeded': obj.count >= limit,
    }


def _call_google_vision(image_path: str) -> list:
    """
    Google Cloud Vision TEXT_DETECTION 호출.
    API Key 방식 (환경변수 GOOGLE_VISION_API_KEY).
    반환: textAnnotations 리스트
    """
    api_key = os.getenv('GOOGLE_VISION_API_KEY', '').strip()
    if not api_key:
        raise OcrConfigError(
            'GOOGLE_VISION_API_KEY 가 설정되지 않았습니다. '
            'Google Cloud Console에서 Vision API 키를 발급하세요.'
        )

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f'이미지 없음: {image_path}')

    with open(path, 'rb') as f:
        content_b64 = base64.b64encode(f.read()).decode('utf-8')

    url = f'https://vision.googleapis.com/v1/images:annotate?key={api_key}'
    payload = {
        'requests': [
            {
                'image': {'content': content_b64},
                'features': [
                    {'type': 'TEXT_DETECTION', 'maxResults': 200},
                ],
                'imageContext': {
                    'languageHints': ['ko', 'en'],
                },
            }
        ]
    }

    resp = requests.post(url, json=payload, timeout=30)
    data = resp.json()

    if resp.status_code != 200:
        err = data.get('error', {})
        msg = err.get('message', resp.text[:200])
        raise RuntimeError(f'Google Vision API 오류 ({resp.status_code}): {msg}')

    responses = data.get('responses') or []
    if not responses:
        return []

    first = responses[0]
    if 'error' in first:
        err = first['error']
        raise RuntimeError(f"Vision 오류: {err.get('message', err)}")

    annotations = first.get('textAnnotations') or []
    return annotations


def run_ocr(image_path: str) -> dict:
    """
    Google Vision으로 OCR 실행 후 chord_lines 구조 반환.
    한도 초과 시 OcrQuotaExceeded 발생.
    """
    from PIL import Image

    # 1) 한도 체크
    stats = get_usage_stats()
    if stats['exceeded']:
        raise OcrQuotaExceeded(stats['used'], stats['limit'])

    img_w = img_h = None
    try:
        with Image.open(image_path) as im:
            img_w, img_h = im.size
    except Exception:
        pass

    # 2) Vision 호출
    annotations = _call_google_vision(image_path)

    # 3) 성공 시 카운트 +1
    usage = _increment_usage()

    ocr_lines = []
    raw_texts = []

    # annotations[0]은 전체 문단, 이후가 개별 단어
    for i, ann in enumerate(annotations):
        text = (ann.get('description') or '').strip()
        if not text:
            continue
        if i == 0:
            raw_texts.append(text)
            continue

        vertices = (ann.get('boundingPoly') or {}).get('vertices') or []
        norm = _vertices_to_norm(vertices, img_w or 1, img_h or 1)
        ocr_lines.append({
            'text': text,
            'confidence': 0.95,
            'norm': norm,
        })

    if not raw_texts and ocr_lines:
        raw_texts = [l['text'] for l in ocr_lines]

    hits = _flat_chord_hits(ocr_lines)
    lines = group_hits_into_lines(hits)

    return {
        'raw_text': '\n'.join(raw_texts),
        'ocr_raw_text': '\n'.join(raw_texts),
        'txts': raw_texts,
        'lines': [{'text': l.get('text'), 'confidence': l.get('confidence'), 'norm': l.get('norm')} for l in ocr_lines],
        'chord_lines': lines,
        'chords': lines,
        'chord_candidates': [it['chord'] for L in lines for it in L['items']],
        'image_size': {'width': img_w, 'height': img_h},
        'ocr_usage': usage,
    }
