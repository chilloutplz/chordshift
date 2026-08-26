"""
줄 단위 렌더.
- 줄마다 height 기준 흰 띠
- 각 코드는 items[].t (0~1, 줄 안 상대 위치)로 좌우 배치
- 루트(A–G, #/b)는 본문 크기, sus/maj/m/7 등 quality 는 작은 글씨
- 슬래시 베이스(/E)는 루트와 같은 크기
"""
from io import BytesIO
from pathlib import Path
import re

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int):
    size = max(7, min(int(size), 36))
    for path in [
        'C:/Windows/Fonts/arialbd.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/malgunbd.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
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


# 슬래시 유사 문자 정규화
_SLASH_RE = re.compile(r'[／∕⁄｜|\\]')


def _normalize_slash(s: str) -> str:
    s = _SLASH_RE.sub('/', s)
    s = re.sub(r'\s*/\s*', '/', s)
    return s.strip()


def _split_chord_parts(chord: str):
    """
    코드 문자열을 렌더용 조각으로 분리.
    반환: [(text, role), ...]
      role: 'root' | 'acc' | 'quality' | 'slash' | 'bass' | 'bass_acc' | 'bass_quality'
    예: "Dsus4/F#" → [('D','root'), ('sus4','quality'), ('/','slash'), ('F','bass'), ('#','bass_acc')]
        "F#m7"     → [('F','root'), ('#','acc'), ('m7','quality')]
        "Cmaj7"    → [('C','root'), ('maj7','quality')]
    """
    chord = _normalize_slash(chord or '')
    if not chord:
        return []

    # 슬래시 분리
    if '/' in chord:
        base, bass = chord.split('/', 1)
        parts = _split_chord_parts(base.strip()) if base.strip() else []
        parts.append(('/', 'slash'))
        if bass.strip():
            for t, role in _split_chord_parts(bass.strip()):
                # 베이스 쪽 root/acc/quality → bass*
                if role == 'root':
                    parts.append((t, 'bass'))
                elif role == 'acc':
                    parts.append((t, 'bass_acc'))
                elif role == 'quality':
                    parts.append((t, 'bass_quality'))
                else:
                    parts.append((t, role))
        return parts

    m = re.match(r'^([A-Ga-g])([#b]?)(.*)$', chord)
    if not m:
        return [(chord, 'root')]
    root = m.group(1).upper()
    acc = m.group(2) or ''
    quality = m.group(3) or ''
    parts = [(root, 'root')]
    if acc:
        parts.append((acc, 'acc'))
    if quality:
        parts.append((quality, 'quality'))
    return parts


def _measure(draw, text: str, font) -> tuple:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        size = getattr(font, 'size', 12) or 12
        return max(1, len(text) * size // 2), size


def _draw_styled_chord(draw, chord: str, cx: float, py0: int, band_h: int, fs: int, color=(25, 25, 40)):
    """
    루트·베이스는 fs, quality·acc는 작은 글씨로 그려 전체 너비를 반환.
    세로 정렬: 루트와 같은 중심선 (작은 글씨가 위로 뜨지 않음).
    #/b 만 아주 살짝 올림.
    """
    parts = _split_chord_parts(chord)
    if not parts:
        return 0

    font_main = _get_font(fs)
    # quality: 약 70% — 너무 작으면 위로 떠 보이기 쉬움
    fs_qual = max(8, int(round(fs * 0.70)))
    # #/b: 조금 더 작게
    fs_acc = max(7, int(round(fs * 0.62)))
    font_qual = _get_font(fs_qual)
    font_acc = _get_font(fs_acc)

    def font_for(role: str):
        if role in ('acc', 'bass_acc'):
            return font_acc
        if role in ('quality', 'bass_quality'):
            return font_qual
        return font_main

    widths = []
    heights = []
    for text, role in parts:
        f = font_for(role)
        tw, th = _measure(draw, text, f)
        if role == 'slash':
            tw = max(tw, fs // 3)
        widths.append(tw)
        heights.append(th)

    gaps = []
    for i, (_, role) in enumerate(parts):
        if i == 0:
            gaps.append(0)
        elif role == 'slash' or parts[i - 1][1] == 'slash':
            gaps.append(max(1, fs // 10))
        else:
            gaps.append(0)
    total_w = sum(widths) + sum(gaps)

    root_h = next((h for (t, r), h in zip(parts, heights) if r in ('root', 'bass')), heights[0])
    # 루트를 밴드 세로 중앙에
    root_ty = py0 + max(0, (band_h - root_h) // 2)
    root_center = root_ty + root_h / 2.0

    def clamp_ty(ty, th):
        return max(py0, min(int(round(ty)), py0 + band_h - th))

    x = int(cx - total_w / 2)
    for i, ((text, role), tw, th) in enumerate(zip(parts, widths, heights)):
        x += gaps[i]
        f = font_for(role)
        if role in ('quality', 'bass_quality'):
            # 루트 중심보다 약간 아래 (작은 글씨가 루트 중~하단과 맞춤)
            ty = clamp_ty(root_center - th / 2.0 + root_h * 0.12, th)
        elif role in ('acc', 'bass_acc'):
            # #/b: 루트 중심선 근처 (거의 같은 높이, 아주 살짝만 위)
            ty = clamp_ty(root_center - th / 2.0 - root_h * 0.04, th)
        else:
            # root / bass / slash
            ty = clamp_ty(root_ty + max(0, (root_h - th) // 2), th)
        draw.text((x, ty), text, fill=color, font=f)
        x += tw

    return total_w


def render_transposed_sheet(image_path: str, chords: list, font_size: int = None) -> ContentFile:
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
        if font_size is not None:
            fs = max(9, min(int(font_size), 30))
        else:
            fs = max(12, min(int(band_h * 0.85), int(h * 0.016) + 2))

        # y = 코드줄 세로 중앙 (프론트 lineStyle 과 동일)
        py0 = max(0, int((y - band_h_n / 2) * h))
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
            cx = (x0 + span * t) * w

            _draw_styled_chord(draw, chord, cx, py0, band_h, fs)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=92, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read(), name=Path(image_path).stem + '_result.jpg')
