"""
간단한 코드 조옮김 유틸.
코드 문자열을 반음 단위로 이동한다.
지원 예: C, C#, Db, Dm, F#m7, Gmaj7, Bb, etc.
"""
import re

# 12음 스케일 (샤프 기준 + 플랫 매핑)
NOTES_SHARP = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTES_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

# 루트 노트 → 인덱스
NOTE_TO_IDX = {}
for i, n in enumerate(NOTES_SHARP):
    NOTE_TO_IDX[n] = i
for i, n in enumerate(NOTES_FLAT):
    NOTE_TO_IDX[n] = i
# 추가 별칭
NOTE_TO_IDX.update({'E#': 5, 'B#': 0, 'Fb': 4, 'Cb': 11})


def _parse_chord(chord_str: str):
    """코드 문자열에서 root + quality 분리"""
    if not chord_str or not isinstance(chord_str, str):
        return None, ''
    chord_str = chord_str.strip()
    # 루트: A-G + optional #/b
    m = re.match(r'^([A-Ga-g])([#b]?)(.*)$', chord_str)
    if not m:
        return None, chord_str
    root = m.group(1).upper() + m.group(2)
    quality = m.group(3)
    return root, quality


def normalize_semitones(n: int) -> int:
    """
    12음 동등 기질로 반음 수를 정규화.
    +2 와 +14 → 2, -1 과 +11 → -1 (범위 -5 ~ +6)
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 0
    n = n % 12
    if n > 6:
        n -= 12
    return n


def transpose_note(root: str, semitones: int, prefer_flat: bool = False) -> str:
    """단일 루트 노트를 반음 이동"""
    idx = NOTE_TO_IDX.get(root)
    if idx is None:
        return root
    new_idx = (idx + semitones) % 12
    if prefer_flat:
        return NOTES_FLAT[new_idx]
    return NOTES_SHARP[new_idx]


# OCR/입력에서 흔히 나오는 슬래시 유사 문자 → ASCII '/' 로 통일
_SLASH_RE = re.compile(r'[／∕⁄｜|\\]')


def _normalize_slash(s: str) -> str:
    """전각/유니코드 슬래시·파이프 등을 '/' 로 정규화하고 양옆 공백 제거"""
    if not s:
        return s
    s = _SLASH_RE.sub('/', s)
    # "D / E", "D/ E" → "D/E"
    s = re.sub(r'\s*/\s*', '/', s)
    return s.strip()


def transpose_chord_str(chord_str: str, semitones: int, prefer_flat: bool = False) -> str:
    """단일 코드 문자열 조옮김 (슬래시 코드 지원: C/E → D/F#, Dm7/G → Em7/A)

    베이스(슬래시 뒤)도 반드시 같은 반음만큼 이동한다.
    """
    if not chord_str or semitones == 0:
        return chord_str if not chord_str else _normalize_slash(str(chord_str))

    chord_str = _normalize_slash(str(chord_str))

    # 슬래시 코드: 앞(코드) / 뒤(베이스) 각각 조옮김
    if '/' in chord_str:
        parts = chord_str.split('/', 1)
        base = transpose_chord_str(parts[0].strip(), semitones, prefer_flat)
        bass = transpose_chord_str(parts[1].strip(), semitones, prefer_flat) if parts[1].strip() else ''
        return f"{base}/{bass}" if bass else base

    root, quality = _parse_chord(chord_str)
    if root is None:
        return chord_str
    # quality 안에 슬래시가 남은 경우(정규화 누락 등) 안전망
    if '/' in quality:
        q_main, q_bass = quality.split('/', 1)
        new_root = transpose_note(root, semitones, prefer_flat)
        bass = transpose_chord_str(q_bass.strip(), semitones, prefer_flat) if q_bass.strip() else ''
        return f"{new_root}{q_main}/{bass}" if bass else f"{new_root}{q_main}"
    new_root = transpose_note(root, semitones, prefer_flat)
    return new_root + quality


def transpose_chords(chords: list, semitones: int, prefer_flat: bool = False) -> list:
    """
    chords 리스트 조옮김.
    지원 형식:
      - ["C", "Am", "F", "G"]
      - [{"chord": "C", "position": 0}, ...]
    """
    if not chords or semitones == 0:
        return chords

    result = []
    for item in chords:
        if isinstance(item, str):
            result.append(transpose_chord_str(item, semitones, prefer_flat))
        elif isinstance(item, dict) and 'chord' in item:
            new_item = dict(item)
            new_item['chord'] = transpose_chord_str(item['chord'], semitones, prefer_flat)
            result.append(new_item)
        else:
            result.append(item)
    return result


def first_chord_name(chords) -> str:
    """보정된 chords 에서 가장 위·왼쪽 코드 이름을 반환.

    OCR 배열 순서가 아니라 line.y → item.t(또는 x) 순으로 고른다.
    보정 단계에서 앞에 코드를 추가해도 원곡 키가 맞게 잡히도록 함.
    """
    if not chords or not isinstance(chords, list):
        return ''

    # line 형식: [{y, items:[{chord, t, x}, ...]}, ...]
    if isinstance(chords[0], dict) and 'items' in chords[0]:
        lines = [L for L in chords if isinstance(L, dict)]
        lines.sort(key=lambda L: float(L.get('y') or 0))
        for L in lines:
            items = [it for it in (L.get('items') or []) if isinstance(it, dict)]
            items = [it for it in items if (it.get('chord') or '').strip()]
            if not items:
                continue
            def _pos(it):
                if it.get('t') is not None:
                    try:
                        return float(it['t'])
                    except (TypeError, ValueError):
                        pass
                if it.get('x') is not None:
                    try:
                        return float(it['x'])
                    except (TypeError, ValueError):
                        pass
                return 0.5
            items.sort(key=_pos)
            return (items[0].get('chord') or '').strip()
        return ''

    # flat list
    for c in chords:
        if isinstance(c, str) and c.strip():
            return c.strip()
        if isinstance(c, dict):
            name = (c.get('chord') or '').strip()
            if name:
                return name
    return ''


def infer_original_key(chords) -> str:
    """첫 코드의 루트만 추출 (A, F#, Bb …). 없으면 빈 문자열."""
    name = first_chord_name(chords)
    if not name:
        return ''
    name = _normalize_slash(name)
    # 슬래시 코드면 앞부분만
    if '/' in name:
        name = name.split('/', 1)[0]
    m = re.match(r'^([A-Ga-g])([#b]?)', name.strip())
    if not m:
        return ''
    root = m.group(1).upper() + (m.group(2) or '')
    # 별칭 정규화
    aliases = {'B#': 'C', 'E#': 'F', 'Cb': 'B', 'Fb': 'E'}
    return aliases.get(root, root)
