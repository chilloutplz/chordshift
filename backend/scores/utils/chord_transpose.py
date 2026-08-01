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


def transpose_chord_str(chord_str: str, semitones: int, prefer_flat: bool = False) -> str:
    """단일 코드 문자열 조옮김 (슬래시 코드 지원: C/E → D/F#)"""
    if not chord_str or semitones == 0:
        return chord_str

    # 슬래시 코드 처리
    if '/' in chord_str:
        parts = chord_str.split('/', 1)
        base = transpose_chord_str(parts[0], semitones, prefer_flat)
        bass = transpose_chord_str(parts[1], semitones, prefer_flat)
        return f"{base}/{bass}"

    root, quality = _parse_chord(chord_str)
    if root is None:
        return chord_str
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
