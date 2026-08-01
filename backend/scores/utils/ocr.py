"""
PaddleOCR → 줄(line) 단위 코드 그룹
같은 높이(y)의 코드를 한 줄로 묶음
"""
import os
import re
import uuid
from functools import lru_cache

os.environ.setdefault('FLAGS_enable_pir_api', '0')
os.environ.setdefault('FLAGS_use_mkldnn', '0')
os.environ.setdefault('PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT', '0')

CHORD_FULL = re.compile(
    r'^('
    r'[A-G](?:#|b)?'
    r'(?:maj|min|m|dim|aug|sus|add|M|°)?'
    r'(?:\d{1,2})?'
    r'(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9|add11)?'
    r'(?:/[A-G](?:#|b)?)?'
    r')$',
    re.IGNORECASE,
)
CHORD_IN_TEXT = re.compile(
    r'\b('
    r'[A-G](?:#|b)?'
    r'(?:maj|min|m|dim|aug|sus|add|M)?'
    r'(?:\d{0,2})?'
    r'(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9)?'
    r'(?:/[A-G](?:#|b)?)?'
    r')\b',
    re.IGNORECASE,
)

# y 좌표가 이 값 이내면 같은 줄
LINE_Y_THRESHOLD = 0.025


def _is_empty(obj) -> bool:
    if obj is None:
        return True
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.size == 0
    except Exception:
        pass
    if isinstance(obj, (list, tuple, set, dict, str)):
        return len(obj) == 0
    return False


def _to_list(obj):
    if obj is None:
        return []
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except Exception:
        pass
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    if hasattr(obj, 'tolist'):
        try:
            return obj.tolist()
        except Exception:
            pass
    try:
        return list(obj)
    except Exception:
        return []


@lru_cache(maxsize=1)
def get_ocr_engine():
    from paddleocr import PaddleOCR
    kwargs = dict(
        lang='en',
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    try:
        return PaddleOCR(**kwargs, enable_mkldnn=False)
    except TypeError:
        return PaddleOCR(**kwargs)


def _box_to_norm(box, img_w, img_h):
    if _is_empty(box) or not img_w or not img_h:
        return None
    try:
        pts = _to_list(box)
        if not pts:
            return None
        xs, ys = [], []
        if isinstance(pts[0], (list, tuple)):
            for pt in pts:
                if pt is None or len(pt) < 2:
                    continue
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
        else:
            coords = [float(v) for v in pts]
            if len(coords) < 4:
                return None
            xs, ys = coords[0::2], coords[1::2]
        if not xs or not ys:
            return None
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return {
            'x': round(min_x / img_w, 5),
            'y': round(min_y / img_h, 5),
            'w': round(max(max_x - min_x, 1) / img_w, 5),
            'h': round(max(max_y - min_y, 1) / img_h, 5),
        }
    except Exception:
        return None


def _looks_like_chord(token: str) -> bool:
    token = (token or '').strip()
    if not token or len(token) > 12:
        return False
    return bool(CHORD_FULL.match(token))


def _append_line(lines, texts, text, conf, box, img_w, img_h):
    text = str(text).strip() if text is not None else ''
    if not text:
        return
    try:
        conf = float(conf)
    except Exception:
        conf = 0.0
    norm = _box_to_norm(box, img_w, img_h)
    lines.append({
        'text': text,
        'confidence': conf,
        'box': _to_list(box) if not _is_empty(box) else None,
        'norm': norm,
    })
    texts.append(text)


def _extract_from_page(page, img_w, img_h, lines, texts):
    if isinstance(page, dict):
        rec_texts = _to_list(page.get('rec_texts') or page.get('texts'))
        rec_scores = _to_list(page.get('rec_scores') or page.get('scores'))
        boxes = _to_list(
            page.get('rec_polys')
            or page.get('dt_polys')
            or page.get('rec_boxes')
            or page.get('boxes')
        )
        for i, text in enumerate(rec_texts):
            conf = rec_scores[i] if i < len(rec_scores) else 0.0
            box = boxes[i] if i < len(boxes) else None
            _append_line(lines, texts, text, conf, box, img_w, img_h)
        return

    for t_attr, s_attr, b_attr in [
        ('rec_texts', 'rec_scores', 'rec_polys'),
        ('rec_texts', 'rec_scores', 'dt_polys'),
        ('rec_texts', 'rec_scores', 'rec_boxes'),
        ('texts', 'scores', 'boxes'),
    ]:
        if not hasattr(page, t_attr):
            continue
        rec_texts = _to_list(getattr(page, t_attr, None))
        if not rec_texts:
            continue
        rec_scores = _to_list(getattr(page, s_attr, None))
        boxes = _to_list(getattr(page, b_attr, None))
        for i, text in enumerate(rec_texts):
            conf = rec_scores[i] if i < len(rec_scores) else 0.0
            box = boxes[i] if i < len(boxes) else None
            _append_line(lines, texts, text, conf, box, img_w, img_h)
        return

    if isinstance(page, (list, tuple)):
        for line in page:
            try:
                if not isinstance(line, (list, tuple)) or len(line) < 2:
                    continue
                box, rec = line[0], line[1]
                if isinstance(rec, (list, tuple)) and len(rec) >= 2:
                    _append_line(lines, texts, rec[0], rec[1], box, img_w, img_h)
                elif isinstance(rec, dict):
                    _append_line(
                        lines, texts,
                        rec.get('text') or rec.get('transcription'),
                        rec.get('score') or rec.get('confidence') or 0,
                        box, img_w, img_h,
                    )
            except Exception:
                continue


def _parse_ocr_result(result, img_w=None, img_h=None):
    lines, texts = [], []
    if result is None:
        return lines, ''
    items = result
    if hasattr(result, '__iter__') and not isinstance(result, (list, tuple, dict, str)):
        try:
            items = list(result)
        except Exception:
            items = [result]
    if not isinstance(items, list):
        items = [items]
    for page in items:
        _extract_from_page(page, img_w, img_h, lines, texts)
    return lines, '\n'.join(texts)


def _flat_chord_hits(ocr_lines: list) -> list:
    """OCR 라인 → 개별 코드 후보 {chord, x, y, conf}"""
    hits = []
    for line in ocr_lines:
        text = (line.get('text') or '').strip()
        norm = line.get('norm')
        conf = line.get('confidence', 0)
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
    """
    y 기준으로 줄 묶기.
    반환 형식 (chords JSON):
    [
      {
        "id": "Lxxxx",
        "y": 0.15,
        "xStart": 0.08,
        "xEnd": 0.92,
        "items": [{"id": "...", "chord": "C"}, ...]
      },
      ...
    ]
    """
    if not hits:
        return []

    sorted_hits = sorted(hits, key=lambda h: (h.get('y', 0), h.get('x', 0)))
    clusters = []  # list of list of hits

    for h in sorted_hits:
        placed = False
        for cluster in clusters:
            avg_y = sum(c['y'] for c in cluster) / len(cluster)
            if abs(h['y'] - avg_y) <= LINE_Y_THRESHOLD:
                cluster.append(h)
                placed = True
                break
        if not placed:
            clusters.append([h])

    lines_out = []
    for cluster in clusters:
        cluster.sort(key=lambda c: c.get('x', 0))
        ys = [c['y'] for c in cluster]
        xs = [c['x'] for c in cluster]
        y = sum(ys) / len(ys)
        x_start = max(0.02, min(xs) - 0.02) if xs else 0.08
        x_end = min(0.98, max(xs) + 0.08) if xs else 0.92
        span = max(x_end - x_start, 0.01)
        items = []
        for c in cluster:
            t = (c['x'] - x_start) / span
            t = max(0.02, min(0.98, t))
            items.append({
                'id': uuid.uuid4().hex[:8],
                'chord': c['chord'],
                't': round(t, 5),
            })
        # 표시 보정: 대략 한글자만큼 오른쪽·아래로
        OX, OY = 0.018, -0.016  # 오른쪽으로 약간, 위로 코드 하나 크기
        lines_out.append({
            'id': 'L' + uuid.uuid4().hex[:6],
            'y': round(min(0.98, max(0.02, y + OY)), 5),
            'xStart': round(min(0.9, x_start + OX), 5),
            'xEnd': round(min(0.99, x_end + OX), 5),
            'height': 0.028,
            'items': items,
        })

    lines_out.sort(key=lambda L: L['y'])
    return lines_out


def run_ocr(image_path: str) -> dict:
    from PIL import Image

    img_w = img_h = None
    try:
        with Image.open(image_path) as im:
            img_w, img_h = im.size
    except Exception:
        pass

    ocr = get_ocr_engine()
    result = None
    last_err = None
    for method in ('predict', 'ocr'):
        try:
            result = getattr(ocr, method)(image_path)
            break
        except Exception as e:
            last_err = e
            result = None

    if result is None and last_err is not None:
        raise RuntimeError(f'OCR engine failed: {last_err}') from last_err

    ocr_lines, raw_text = _parse_ocr_result(result, img_w, img_h)
    hits = _flat_chord_hits(ocr_lines)
    lines = group_hits_into_lines(hits)

    # 하위 호환: flat 목록도 제공
    flat = []
    for L in lines:
        n = max(len(L['items']), 1)
        for i, it in enumerate(L['items']):
            t = L['xStart'] + (L['xEnd'] - L['xStart']) * (i + 0.5) / n
            flat.append({
                'id': it['id'],
                'chord': it['chord'],
                'x': round(t, 5),
                'y': L['y'],
                'w': 0.04,
                'h': 0.02,
                'lineId': L['id'],
            })

    return {
        'raw_text': raw_text,
        'lines': [
            {'text': l.get('text'), 'confidence': l.get('confidence'), 'norm': l.get('norm')}
            for l in ocr_lines
        ],
        'chord_lines': lines,   # 줄 단위 (주 데이터)
        'chords': lines,        # DB 저장용 — 줄 배열
        'chord_candidates': [it['chord'] for L in lines for it in L['items']],
        'image_size': {'width': img_w, 'height': img_h},
    }
