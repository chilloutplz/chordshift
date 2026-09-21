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

# quality 조각 (루트 뒤)
_QUALITY = (
    r'(?:maj|min|dim|aug|sus|add|maj7|min7|m7|M7|dim7|sus2|sus4|add9|add11|m|M|°)?'
    r'(?:\d{0,2})?'
    r'(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9|add11)?'
)
# 루트 + quality (+ 선택적 슬래시 베이스)
_ROOT = r'[A-G](?:#|b)?'
_SLASH_CHARS = r'[／∕⁄｜|\\/]'

CHORD_FULL = re.compile(
    rf'^({_ROOT}{_QUALITY})(?:{_SLASH_CHARS}({_ROOT}))?$',
    re.IGNORECASE,
)
# 텍스트 중간에서도 D/E, D／E, D / E 형태를 잡음 (\b 만으로는 / 주변이 깨지기 쉬움)
CHORD_IN_TEXT = re.compile(
    rf'(?<![A-Za-z0-9])({_ROOT}{_QUALITY})(?:\s*{_SLASH_CHARS}\s*({_ROOT}))?(?![A-Za-z0-9])',
    re.IGNORECASE,
)

# 슬래시 단독 토큰
SLASH_ONLY = re.compile(rf'^{_SLASH_CHARS}$')
# 베이스로 쓸 수 있는 단순 루트 (A, F#, Bb)
BASS_ONLY = re.compile(rf'^{_ROOT}$', re.IGNORECASE)

# 같은 줄 판단 y 차이
LINE_Y_THRESHOLD = 0.025  

# 최초 OCR 결과 표시 위치 보정
OCR_CHORD_Y_OFFSET = 0.035

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


def _normalize_chord_token(token: str) -> str:
    """전각 슬래시·공백 정리: 'D／E', 'D / E' → 'D/E'"""
    if not token:
        return ''
    t = token.strip()
    t = re.sub(_SLASH_CHARS, '/', t)
    t = re.sub(r'\s*/\s*', '/', t)
    t = re.sub(r'\s+', '', t)  # 코드 안 공백 제거 (D m → 유지하지 않음: quality는 보통 붙음)
    return t


def _looks_like_chord(token: str) -> bool:
    token = _normalize_chord_token(token or '')
    if not token or len(token) > 14:
        return False
    return bool(CHORD_FULL.match(token))


def _format_chord_match(root_part: str, bass_part: str | None = None) -> str:
    root_part = _normalize_chord_token(root_part)
    if bass_part:
        bass_part = _normalize_chord_token(bass_part)
        return f'{root_part}/{bass_part}'
    return root_part


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
    """Vision 단어 단위 결과에서 코드 후보 + 슬래시 토큰 추출."""
    hits = []
    for line in ocr_lines:
        text = (line.get('text') or '').strip()
        if not text:
            continue
        norm = line.get('norm')
        conf = line.get('confidence', 0.9)
        y = (norm or {}).get('y', 0.1)
        x = (norm or {}).get('x', 0.05)
        w = (norm or {}).get('w', 0.02)

        # 1) 슬래시만 있는 토큰 → 이후 병합용 마커
        if SLASH_ONLY.match(text):
            hits.append({
                'chord': '/',
                'x': x,
                'y': y,
                'confidence': conf,
                'is_slash': True,
            })
            continue

        # 2) 토큰 전체가 코드 (D, F#m, D/E, D／E …)
        normed = _normalize_chord_token(text)
        if _looks_like_chord(normed):
            hits.append({
                'chord': normed,
                'x': x,
                'y': y,
                'confidence': conf,
                'is_slash': False,
            })
            continue

        # 3) 긴 텍스트 안에서 코드 패턴 검색 (가사+코드 혼재)
        for m in CHORD_IN_TEXT.finditer(text):
            root_part = m.group(1)
            bass_part = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            token = _format_chord_match(root_part, bass_part)
            if not _looks_like_chord(token):
                continue
            if norm:
                ratio = m.start() / max(len(text), 1)
                cx = round(norm['x'] + w * ratio, 5)
                cy = y
            else:
                cx, cy = 0.05, 0.1
            hits.append({
                'chord': token,
                'x': cx,
                'y': cy,
                'confidence': conf,
                'is_slash': False,
            })
    return hits


# 같은 줄로 보고 슬래시 병합할 최대 x 간격 (정규화 좌표)
SLASH_MERGE_DX = 0.045
SLASH_MERGE_DY = 0.02


def _merge_slash_hits(hits: list) -> list:
    """인접 토큰을 슬래시 코드로 합친다.

    Vision 은 'D' '/' 'E' 또는 'D' 'E' 로 쪼개는 경우가 많다.
    - 사이에 '/' 마커가 있으면 무조건 병합
    - '/' 없이도 매우 가깝고 오른쪽이 단순 루트(베이스)이면 병합
    """
    if not hits:
        return []

    ordered = sorted(hits, key=lambda h: (h.get('y', 0), h.get('x', 0)))
    out = []
    i = 0
    n = len(ordered)
    while i < n:
        cur = ordered[i]
        if cur.get('is_slash'):
            # 단독 슬래시는 코드가 아님 — 앞뒤 병합에서만 사용, 남기지 않음
            i += 1
            continue

        # 이미 D/E 형태면 그대로
        chord = cur.get('chord') or ''
        if '/' in chord:
            out.append({**cur, 'is_slash': False})
            i += 1
            continue

        # 다음이 슬래시 마커 → 그 다음 코드와 병합
        if i + 1 < n and ordered[i + 1].get('is_slash'):
            if i + 2 < n and not ordered[i + 2].get('is_slash'):
                nxt = ordered[i + 2]
                if abs(nxt['y'] - cur['y']) <= SLASH_MERGE_DY:
                    bass = (nxt.get('chord') or '').split('/')[0]
                    if BASS_ONLY.match(_normalize_chord_token(bass)) or _looks_like_chord(bass):
                        merged = {
                            'chord': f"{chord}/{_normalize_chord_token(bass)}",
                            'x': cur['x'],
                            'y': (cur['y'] + nxt['y']) / 2,
                            'confidence': min(cur.get('confidence', 1), nxt.get('confidence', 1)),
                            'is_slash': False,
                        }
                        out.append(merged)
                        i += 3
                        continue
            i += 1
            continue

        # 슬래시 없이 바로 다음 토큰이 가까운 단순 베이스
        if i + 1 < n and not ordered[i + 1].get('is_slash'):
            nxt = ordered[i + 1]
            dx = nxt['x'] - cur['x']
            dy = abs(nxt['y'] - cur['y'])
            bass = _normalize_chord_token((nxt.get('chord') or '').split('/')[0])
            # 오른쪽·같은 높이·간격 좁음·베이스는 루트만 (C, F# …)
            if (
                0 < dx <= SLASH_MERGE_DX
                and dy <= SLASH_MERGE_DY
                and BASS_ONLY.match(bass)
                and '/' not in (nxt.get('chord') or '')
            ):
                merged = {
                    'chord': f'{chord}/{bass}',
                    'x': cur['x'],
                    'y': (cur['y'] + nxt['y']) / 2,
                    'confidence': min(cur.get('confidence', 1), nxt.get('confidence', 1)),
                    'is_slash': False,
                }
                out.append(merged)
                i += 2
                continue

        out.append({**cur, 'is_slash': False})
        i += 1
    return out


def group_hits_into_lines(hits: list) -> list:
    if not hits:
        return []

    sorted_hits = sorted(
        hits,
        key=lambda h: (h.get('y', 0), h.get('x', 0))
    )

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

        # 최초 OCR 결과에서만 코드줄을 위쪽으로 표시
        display_y = max(0.02, y - OCR_CHORD_Y_OFFSET)

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
            'y': round(display_y, 5),
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
    hits = _merge_slash_hits(hits)
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
