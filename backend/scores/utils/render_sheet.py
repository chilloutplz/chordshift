"""
줄 단위 렌더.
- 줄마다 height 기준 흰 띠
- 각 코드는 items[].t (0~1, 줄 안 상대 위치)로 좌우 배치
"""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int):
    size = max(11, min(int(size), 30))
    for path in [
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/malgunbd.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _normalize_lines(chords) -> list:
    if not chords:
        return []
    if isinstance(chords, list) and chords and isinstance(chords[0], dict) and 'items' in chords[0]:
        return chords
    items = []
    for c in chords:
        if isinstance(c, str):
            items.append({'chord': c})
        elif isinstance(c, dict):
            items.append({'chord': c.get('chord', ''), 't': c.get('t')})
    return [{'id': 'L0', 'y': 0.12, 'xStart': 0.08, 'xEnd': 0.92, 'height': 0.028, 'items': items}]


def render_transposed_sheet(image_path: str, chords: list) -> ContentFile:
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    draw = ImageDraw.Draw(img)

    for line in _normalize_lines(chords):
        items = [it for it in (line.get('items') or []) if (it.get('chord') or '').strip()]
        if not items:
            continue

        y = float(line.get('y', 0.1))
        x0 = float(line.get('xStart', 0.06))
        x1 = float(line.get('xEnd', 0.94))
        band_h_n = float(line.get('height') or 0.028)
        if x1 <= x0:
            x1 = min(0.98, x0 + 0.5)

        band_h = max(int(h * band_h_n), 14)
        font_size = max(12, min(int(band_h * 0.85), int(h * 0.016) + 2))
        font = _get_font(font_size)

        # 프론트와 동일 오프셋: top = y - h
        py0 = max(0, int((y - band_h_n) * h))
        py1 = min(h, py0 + band_h)
        px0 = max(0, int(x0 * w) - 2)
        px1 = min(w, int(x1 * w) + 2)

        # 흰 띠 — 원본 코드 가림
        draw.rectangle([px0, py0, px1, py1], fill=(255, 255, 255))

        span = x1 - x0
        n = len(items)
        for i, it in enumerate(items):
            chord = it['chord'].strip()
            t = it.get('t')
            if t is None or not isinstance(t, (int, float)):
                t = (i + 0.5) / n
            t = max(0.02, min(0.98, float(t)))
            cx = x0 + span * t

            try:
                bbox = draw.textbbox((0, 0), chord, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                tw, th = len(chord) * font_size // 2, font_size

            tx = int(cx * w - tw / 2)
            ty = py0 + max(0, (band_h - th) // 2)
            draw.text((tx, ty), chord, fill=(25, 25, 40), font=font)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=92, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read(), name=Path(image_path).stem + '_result.jpg')
