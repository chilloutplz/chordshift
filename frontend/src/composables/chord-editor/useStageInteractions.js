import { EDIT_X0, EDIT_X1 } from '@/constants/chords.js'

function clampNorm(v) {
  return Math.min(0.99, Math.max(0.01, v))
}

export function useStageInteractions({
  lines, drag, activeLineId, placeChord, bottomTab, landscapeMode,
  stageRef, message, dirty,
  isChordSelected, toggleLineSelection, toggleChordSelection
}) {
  function normFromEvent(e) {
    const el = stageRef.value
    if (!el) return null
    const rect = el.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    if (!landscapeMode.value) {
      return {
        x: clampNorm((e.clientX - rect.left) / rect.width),
        y: clampNorm((e.clientY - rect.top) / rect.height),
      }
    }
    return {
      x: clampNorm((e.clientY - rect.top) / rect.height),
      y: clampNorm(1 - (e.clientX - rect.left) / rect.width),
    }
  }

  function startDrag(e, type, lineId, itemId = null) {
    if (placeChord.value) return
    const isLineOp = type !== 'chord-x'
    if (isLineOp && bottomTab.value !== 'adjust') return
    if (!isLineOp && bottomTab.value !== 'place') return
    if (type === 'chord-x' && itemId && !isChordSelected(lineId, itemId)) return
    e.stopPropagation()
    activeLineId.value = lineId
    const line0 = lines.value.find((L) => L.id === lineId)
    const pos0 = normFromEvent(e)
    let chordGrabOffset = 0
    let origChordT = 0.5
    if (type === 'chord-x' && line0 && itemId) {
      const item0 = (line0.items || []).find((it) => it.id === itemId)
      const span0 = (line0.xEnd ?? 0.99) - (line0.xStart ?? 0.01)
      origChordT = typeof item0?.t === 'number' ? item0.t : 0.5
      if (span0 > 0.001 && pos0) {
        const centerAbs = (line0.xStart ?? 0.01) + origChordT * span0
        chordGrabOffset = pos0.x - centerAbs
      }
    }
    drag.value = {
      type, lineId, itemId, moved: false,
      startX: pos0?.x ?? 0, startY: pos0?.y ?? 0,
      startClientX: e.clientX, startClientY: e.clientY,
      origY: line0?.y ?? 0,
      origHeight: line0?.height ?? 0.032,
      origXStart: line0?.xStart ?? 0.01,
      origXEnd: line0?.xEnd ?? 0.99,
      origAbs: null, chordGrabOffset, origChordT,
    }
    const DRAG_THRESHOLD_PX = 4
    const onMove = (ev) => {
      if (!drag.value) return
      if (!drag.value.moved) {
        const movedPx = Math.hypot(ev.clientX - drag.value.startClientX, ev.clientY - drag.value.startClientY)
        if (movedPx < DRAG_THRESHOLD_PX) return
        drag.value.moved = true
      }
      const pos = normFromEvent(ev); if (!pos) return
      const line = lines.value.find((L) => L.id === drag.value.lineId); if (!line) return
      if (!drag.value.origAbs) {
        const span0 = drag.value.origXEnd - drag.value.origXStart
        drag.value.origAbs = (line.items || []).map(it => ({
          id: it.id, abs: drag.value.origXStart + (typeof it.t === 'number' ? it.t : 0.5) * span0
        }))
      }
      if (drag.value.type === 'line-body') {
        const dy = pos.y - drag.value.startY
        line.y = Math.min(0.98, Math.max(0.02, drag.value.origY + dy))
      } else if (drag.value.type === 'chord-x') {
        const item = line.items.find((it) => it.id === drag.value.itemId); if (!item) return
        const span = line.xEnd - line.xStart; if (span <= 0.001) return
        const centerAbs = pos.x - (drag.value.chordGrabOffset || 0)
        const nt = (centerAbs - line.xStart) / span
        item.t = Math.min(0.98, Math.max(0.02, nt))
      }
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      if (drag.value?.moved) dirty.value = true
      drag.value = null
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  function onStageClick(e) {
    if (!placeChord.value) return
    const pos = normFromEvent(e); if (!pos) return
    const ch = placeChord.value
    if (lines.value.length) {
      let best = null, bestDist = Infinity
      for (const L of lines.value) {
        const d = Math.abs((L.y || 0) - pos.y)
        if (d < bestDist) { bestDist = d; best = L }
      }
      const active = lines.value.find((L) => L.id === activeLineId.value)
      const target = active || best; if (!target) return
      const span = (target.xEnd - target.xStart) || 0.8
      const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - target.xStart) / span))
      target.items.push({ id: 'n' + Date.now().toString(36), chord: ch, t: tNorm, manual: true })
      activeLineId.value = target.id
      message.value = `"${ch}" 위치에 삽입`
      dirty.value = true
      return
    }
    const line = {
      id: 'L' + Date.now().toString(36), y: pos.y, xStart: EDIT_X0, xEnd: EDIT_X1, height: 0.032,
      items: [{ id: 'n' + Date.now().toString(36), chord: ch, t: 0.5, manual: true }],
    }
    lines.value.push(line); activeLineId.value = line.id
    message.value = `"${ch}" 새 위치에 삽입`; dirty.value = true
  }

  function onLineClick(e, line) {
    e.stopPropagation()
    const L = lines.value.find((x) => x.id === line.id) || line
    if (bottomTab.value === 'adjust') { toggleLineSelection(L.id); return }
    activeLineId.value = L.id
    if (!placeChord.value) return
    const pos = normFromEvent(e); if (!pos) return
    if (!Array.isArray(L.items)) L.items = []
    const span = (L.xEnd - L.xStart) || 0.8
    const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - L.xStart) / span))
    L.items.push({ id: 'n' + Date.now().toString(36), chord: placeChord.value, t: tNorm, manual: true })
    message.value = `"${placeChord.value}" 위치에 삽입`; dirty.value = true
  }

  function onChipClick(e, line, item) {
    e.stopPropagation()
    if (bottomTab.value === 'adjust') { toggleLineSelection(line.id); return }
    if (placeChord.value) placeChord.value = ''
    toggleChordSelection(line.id, item.id)
  }

  return { normFromEvent, startDrag, onStageClick, onLineClick, onChipClick, clampNorm }
}