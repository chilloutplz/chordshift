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
      xStart: typeof L.xStart === 'number' ? L.xStart : EDIT_X0,
      xEnd: typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1,
      items,
    })
  }
  return out
}

/**
 * 예전 저장본(줄 구간이 축소되고 t가 상대값인 경우)만
 * 절대 좌표(전체 폭 기준 t)로 한 번 맞춰 준다.
 * 절대 위치(abs)는 유지하고, 간격을 다시 나누지 않는다.
 */
function legacyToAbsoluteIfNeeded(list) {
  return list.map((L) => {
    const x0 = typeof L.xStart === 'number' ? L.xStart : EDIT_X0
    const x1 = typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1
    const alreadyFull =
      Math.abs(x0 - EDIT_X0) < 0.002 && Math.abs(x1 - EDIT_X1) < 0.002
    if (alreadyFull) {
      return {
        ...L,
        xStart: EDIT_X0,
        xEnd: EDIT_X1,
        items: ensureItemT(L.items || []),
      }
    }
    const span = Math.max(0.001, x1 - x0)
    const spanEdit = EDIT_X1 - EDIT_X0
    const items = ensureItemT(
      (L.items || []).map((it) => {
        const tOld = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
        const abs = x0 + tOld * span
        return {
          ...it,
          t: Math.min(0.98, Math.max(0.02, (abs - EDIT_X0) / spanEdit)),
        }
      })
    )
    return { ...L, xStart: EDIT_X0, xEnd: EDIT_X1, items }
  })
}

/**
 * toLines
 * - OCR: t = x/W (읽은 가로 위치 그대로), 세로만 상단 배치
 * - 저장본: 좌표 그대로 (필요 시 예전 상대 t만 절대 t로 복원)
 */
function toLines(raw) {
  if (!Array.isArray(raw) || !raw.length) return []

  // === 저장본 / lines 형식 ===
  if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].items)) {
    return legacyToAbsoluteIfNeeded(
      raw.map((L, i) => ({
        id: L.id || `L${i}`,
        y: typeof L.y === 'number' && !Number.isNaN(L.y) ? L.y : 0.1 + i * 0.08,
        xStart: typeof L.xStart === 'number' ? L.xStart : EDIT_X0,
        xEnd: typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1,
        height: L.height ?? 0.032,
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
