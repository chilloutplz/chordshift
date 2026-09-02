import { EDIT_X0, EDIT_X1, SAVE_LINE_PAD, SAVE_MIN_SPAN } from '@/constants/chords.js'

function ensureItemT(items) {
  const n = Math.max(items.length, 1)
  return items.map((it, i) => {
    const base = { ...it, manual: !!it.manual }
    if (typeof it.t === 'number' && !Number.isNaN(it.t)) {
      base.t = Math.min(0.98, Math.max(0.02, it.t))
      return base
    }
    base.t = (i + 0.5) / n
    return base
  })
}

/** 편집 중 전체 폭으로 펼칠 때 사용 (OCR 직후 등) */
function expandLinesToFullWidth(list) {
  const spanEdit = EDIT_X1 - EDIT_X0
  return list.map((L) => {
    const x0 = L.xStart ?? EDIT_X0
    const x1 = L.xEnd ?? EDIT_X1
    const span = Math.max(0.001, x1 - x0)
    const items = (L.items || []).map((it) => {
      const tOld = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
      const abs = x0 + tOld * span
      const tNew = (abs - EDIT_X0) / spanEdit
      return { ...it, t: Math.min(0.98, Math.max(0.02, tNew)) }
    })
    return { ...L, xStart: EDIT_X0, xEnd: EDIT_X1, items }
  })
}

function compactLinesForSave(list) {
  const out = []
  for (const L of list) {
    const items = (L.items || []).filter((it) => (it.chord || '').trim())
    if (!items.length) continue
    const x0 = L.xStart ?? EDIT_X0
    const x1 = L.xEnd ?? EDIT_X1
    const span = Math.max(0.001, x1 - x0)
    const absItems = items.map((it) => {
      const t = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
      return { it, abs: x0 + t * span }
    })
    absItems.sort((a, b) => a.abs - b.abs)
    let newStart = absItems[0].abs - SAVE_LINE_PAD
    let newEnd = absItems[absItems.length - 1].abs + SAVE_LINE_PAD
    newStart = Math.max(0.005, newStart)
    newEnd = Math.min(0.995, newEnd)
    if (newEnd - newStart < SAVE_MIN_SPAN) {
      const mid = (newStart + newEnd) / 2
      newStart = Math.max(0.005, mid - SAVE_MIN_SPAN / 2)
      newEnd = Math.min(0.995, newStart + SAVE_MIN_SPAN)
    }
    const newSpan = Math.max(0.001, newEnd - newStart)
    out.push({
      id: L.id,
      y: Math.round((L.y ?? 0.1) * 1e5) / 1e5,
      height: L.height ?? 0.032,
      xStart: Math.round(newStart * 1e5) / 1e5,
      xEnd: Math.round(newEnd * 1e5) / 1e5,
      items: absItems.map(({ it, abs }) => ({
        id: it.id,
        chord: String(it.chord).trim(),
        t: Math.min(0.98, Math.max(0.02, Math.round(((abs - newStart) / newSpan) * 1e5) / 1e5)),
        ...(it.manual ? { manual: true } : {}),
      })),
    })
  }
  return out
}

/**
 * toLines
 * - 이미 lines 형식(저장본): y/x/t 그대로 유지 (expand 하지 않음 → 조옮김 좌표와 일치)
 * - OCR 절대좌표: 줄을 화면 상단(0.12 + 0.06*i)에 배치해 보정하기 쉽게
 */
function toLines(raw) {
  if (!Array.isArray(raw) || !raw.length) return []

  // === 저장본 / 편집 중 lines 형식 ===
  if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].items)) {
    return raw.map((L, i) => ({
      id: L.id || `L${i}`,
      y: typeof L.y === 'number' && !Number.isNaN(L.y) ? L.y : 0.1 + i * 0.08,
      xStart: typeof L.xStart === 'number' ? L.xStart : EDIT_X0,
      xEnd: typeof L.xEnd === 'number' ? L.xEnd : EDIT_X1,
      height: L.height ?? 0.032,
      items: ensureItemT(
        (L.items || []).map((it, j) => ({
          id: it.id || `i${i}_${j}`,
          chord: it.chord || it.text || '',
          t: it.t ?? 0.5,
          manual: !!it.manual,
        }))
      ),
    }))
  }

  // === OCR 절대좌표 모드 ===
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

  // OCR 직후: 상단부터 일정 간격으로 배치 → 모바일에서 보정하기 쉬움
  // x는 전체 폭, t는 OCR x 비율 유지
  return groups.map((g, gi) => {
    g.sort((a, b) => a.x - b.x)
    return {
      id: `L${gi}`,
      y: 0.12 + 0.06 * gi,
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
  return { toLines, ensureItemT, expandLinesToFullWidth, compactLinesForSave }
}
