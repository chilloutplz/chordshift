import { EDIT_X0, EDIT_X1 } from '@/constants/chords.js'

function ensureItemT(items) {
  const n = Math.max(items.length, 1)
  return items.map((it, i) => {
    const base = { ...it, manual: !!it.manual }
    if (typeof it.t === 'number' && !Number.isNaN(it.t)) {
      base.t = Math.min(0.98, Math.max(0.02, it.t))
      return base
    }
    // t가 아예 없을 때만 기본값 (기존 좌표를 건드리지 않음)
    base.t = (i + 0.5) / n
    return base
  })
}

/**
 * 저장: 빈 코드만 제거하고 좌표는 그대로 둔다.
 * xStart/xEnd/t/y 를 다시 계산하지 않는다.
 * item.t 는 이미지 전체 기준 절대 가로 위치.
 * topOffset/bottomOffset 이 있으면 함께 저장.
 */
function compactLinesForSave(list) {
  const out = []
  for (const L of list) {
    const items = (L.items || [])
      .filter((it) => (it.chord || '').trim())
      .map((it) => ({
        id: it.id,
        chord: String(it.chord).trim(),
        t: typeof it.t === 'number' && !Number.isNaN(it.t)
          ? Math.min(0.98, Math.max(0.02, it.t))
          : 0.5,
        ...(it.manual ? { manual: true } : {}),
      }))
    if (!items.length) continue
    out.push({
      id: L.id,
      y: Math.round((L.y ?? 0.1) * 1e5) / 1e5,
      height: L.height ?? 0.032,
      ...(typeof L.topOffset === 'number'
        ? { topOffset: Math.round(L.topOffset * 1e5) / 1e5 }
        : {}),
      ...(typeof L.bottomOffset === 'number'
        ? { bottomOffset: Math.round(L.bottomOffset * 1e5) / 1e5 }
        : {}),
      xStart: typeof L.xStart === 'number' ? L.xStart : EDIT_X0,
      xEnd: typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1,
      items,
    })
  }
  return out
}

/**
 * 로드 시 좌표 정규화.
 * item.t 는 항상 이미지 절대 가로 위치.
 * xStart/xEnd 는 사용자가 조정한 박스 경계를 그대로 유지한다.
 * (예전: 비-전체폭이면 t를 상대→절대 변환하며 박스를 전체폭으로 리셋했음 → Left/Right 저장이 사라짐)
 */
function normalizeLoadedLines(list) {
  return list.map((L) => {
    const x0 = typeof L.xStart === 'number' ? L.xStart : EDIT_X0
    const x1 = typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1
    // 예전 데이터: xStart/xEnd 가 전체폭이 아니고 t 가 박스 상대값일 수 있음.
    // 그 경우에만 한 번 절대 t 로 환산. 이미 절대 t + 사용자 박스면 그대로 둔다.
    // 휴리스틱: 박스 폭이 전체(EDIT)와 거의 같으면 t 는 이미 절대.
    const alreadyFull =
      Math.abs(x0 - EDIT_X0) < 0.002 && Math.abs(x1 - EDIT_X1) < 0.002
    if (alreadyFull) {
      return {
        ...L,
        xStart: x0,
        xEnd: x1,
        items: ensureItemT(L.items || []),
      }
    }
    // 박스만 좁혀진 저장본: t 가 상대값이었을 수 있으므로 절대값으로 승격하고
    // xStart/xEnd 는 사용자 설정을 유지한다 (리셋하지 않음).
    const span = Math.max(0.001, x1 - x0)
    const items = ensureItemT(
      (L.items || []).map((it) => {
        const tOld = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
        // tOld 가 이미 절대(대략 박스 밖 포함 가능)인지 상대인지 구분하기 어려움.
        // 상대였다면 abs = x0 + t*span, 절대였다면 t 그대로.
        // 안전한 쪽: t 가 [0,1] 이고 x0+t*span 이 이미지 안에 있으면
        // "상대 해석"으로 절대화. 이미 절대면 값이 크게 안 바뀌는 경우가 많음.
        // 여기서는 상대 해석을 유지하되 박스는 리셋하지 않는다.
        const abs = x0 + tOld * span
        return {
          ...it,
          t: Math.min(0.98, Math.max(0.02, abs)),
        }
      })
    )
    return { ...L, xStart: x0, xEnd: x1, items }
  })
}

/**
 * toLines
 * - OCR: t = x/W (읽은 가로 위치 그대로), 세로만 상단 배치
 * - 저장본: xStart/xEnd 유지, t 는 절대 가로 위치로 정규화
 */
function toLines(raw) {
  if (!Array.isArray(raw) || !raw.length) return []

  // === 저장본 / lines 형식 ===
  if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].items)) {
    return normalizeLoadedLines(
      raw.map((L, i) => ({
        id: L.id || `L${i}`,
        y: typeof L.y === 'number' && !Number.isNaN(L.y) ? L.y : 0.1 + i * 0.08,
        xStart: typeof L.xStart === 'number' ? L.xStart : EDIT_X0,
        xEnd: typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1,
        height: L.height ?? 0.032,
        topOffset: typeof L.topOffset === 'number' ? L.topOffset : undefined,
        bottomOffset: typeof L.bottomOffset === 'number' ? L.bottomOffset : undefined,
        items: (L.items || []).map((it, j) => ({
          id: it.id || `i${i}_${j}`,
          chord: it.chord || it.text || '',
          t: it.t ?? 0.5,
          manual: !!it.manual,
        })),
      }))
    )
  }

  // === OCR 절대좌표: 가로 위치 = 읽은 그대로 ===
  const W = 750
  const filtered = raw.filter((c) => {
    if (typeof c === 'string') return true
    const x = c.x ?? 0
    if (x < 35 || x > 700) return false
    return !!(c.chord || c.text)
  })
  const sorted = [...filtered].sort((a, b) => (a.y ?? 0) - (b.y ?? 0))
  const groups = []
  let cur = []
  let lastY = null
  const Y_GAP = 45

  for (const c of sorted) {
    const y = c.y ?? 0
    const x = c.x ?? 0
    const name = typeof c === 'string' ? c : (c.chord || c.text || '')
    if (lastY === null || Math.abs(y - lastY) <= Y_GAP) {
      cur.push({
        id: c.id || `c_${groups.length}_${cur.length}`,
        chord: name,
        x,
        y,
        t: x / W,
      })
      lastY = lastY === null ? y : lastY * 0.7 + y * 0.3
    } else {
      if (cur.length) groups.push(cur)
      cur = [{
        id: c.id || `c_${groups.length}_0`,
        chord: name,
        x,
        y,
        t: x / W,
      }]
      lastY = y
    }
  }
  if (cur.length) groups.push(cur)

  return groups.map((g, gi) => {
    g.sort((a, b) => a.x - b.x)
    return {
      id: `L${gi}`,
      y: 0.06 + 0.06 * gi,
      xStart: EDIT_X0,
      xEnd: EDIT_X1,
      height: 0.032,
      items: ensureItemT(
        g.map((it) => ({
          id: it.id,
          chord: it.chord,
          t: Math.min(0.98, Math.max(0.02, it.t)),
        }))
      ),
    }
  })
}

export function useLinesData() {
  return { toLines, ensureItemT, compactLinesForSave }
}
