<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { API_BASE, apiFetch } from '@/api/api.js'

const props = defineProps({
  sheet: { type: Object, required: true },
  pageMode: { type: String, default: 'correct' }, // correct | full
})
const emit = defineEmits(['updated', 'back', 'next'])

const ROOTS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
const VARIANTS = {
  C: ['C', 'Cm', 'C7', 'Cmaj7', 'Cm7', 'C/E', 'C/G', 'C#', 'C#m', 'C#7', 'Db', 'Dbm'],
  D: ['D', 'Dm', 'D7', 'Dmaj7', 'Dm7', 'D/F#', 'D/A', 'D#', 'D#m', 'Eb', 'Ebm', 'Eb7'],
  E: ['E', 'Em', 'E7', 'Emaj7', 'Em7', 'E/G#', 'E/B', 'Eb', 'Ebm'],
  F: ['F', 'Fm', 'F7', 'Fmaj7', 'Fm7', 'F/A', 'F/C', 'F#', 'F#m', 'F#7', 'F#m7', 'Gb'],
  G: ['G', 'Gm', 'G7', 'Gmaj7', 'Gm7', 'G/B', 'G/D', 'G#', 'G#m', 'Ab', 'Abm'],
  A: ['A', 'Am', 'A7', 'Amaj7', 'Am7', 'A/C#', 'A/E', 'Am/G', 'A#', 'Bb', 'Bbm', 'Bb7'],
  B: ['B', 'Bm', 'B7', 'Bmaj7', 'Bm7', 'B/D#', 'B/F#', 'Bb', 'Bbm', 'Bb7'],
}

const lines = ref([])
const semitones = ref(0)
const saving = ref(false)
const confirming = ref(false)
const message = ref('')
const ocrLoading = ref(false)
const ocrError = ref('')
// OCR 큐 대기 정보 - { status: 'queued'|'processing', aheadCount, estimatedWaitSeconds }
const ocrQueueInfo = ref(null)
// 이 시트에 대해 OCR을 이미 한 번이라도 실행한 적 있는지
// - 열었을 때 이미 인식된 코드/원문이 있으면 재실행으로 간주 (예: 저장 후 다시 들어온 경우)
// - 처음 업로드해서 아직 OCR 안 돌린 상태면 false
const ocrHasRun = ref(!!(props.sheet.chords?.length || props.sheet.ocr_raw_text))
const editKey = ref(null)
const editValue = ref('')
const activeLineId = ref(null)
const placeChord = ref('')
const customChord = ref('')
const stageRef = ref(null)
const drag = ref(null)
const chordFontPx = ref(15)
const selectedRoot = ref(null)
const dupCandidates = ref([])

function keyLabelFromLines(linesArr, semitones = 0) {
  const NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
  const map = Object.fromEntries(NOTES.map((n,i)=>[n,i]))
  map['Db']=1; map['Eb']=3; map['Gb']=6; map['Ab']=8; map['Bb']=10
  let name = 'C'
  if (Array.isArray(linesArr) && linesArr[0]?.items?.[0]?.chord) name = linesArr[0].items[0].chord
  const m = String(name).match(/^([A-Ga-g])([#b]?)/)
  if (!m) return 'C코드'
  const root = m[1].toUpperCase() + (m[2] || '')
  const idx = map[root]
  if (idx === undefined) return `${root}코드`
  const out = NOTES[(idx + (semitones % 12) + 12) % 12]
  return `${out}코드`
}

function isTemp() {
  return !!(props.sheet.is_temp || props.sheet.temp_id)
}
function sheetId() {
  return props.sheet.temp_id || props.sheet.id
}

async function runOcr() {
  const temp_id = props.sheet.temp_id
  if (!temp_id) {
    ocrError.value = '임시 ID가 없습니다. 다시 업로드하세요.'
    return
  }
  const isRerun = ocrHasRun.value  // 이번 호출이 재실행인지 시작 시점에 미리 기억
  ocrLoading.value = true
  ocrError.value = ''
  ocrQueueInfo.value = null
  try {
    // 1차: /ocr/ 호출 (job 방식 또는 sync 방식 둘 다 대응)
    let res = await apiFetch(`/api/temp/${temp_id}/ocr/`, { method: 'POST' })
    // 만약 404면 sync 엔드포인트 시도
    if (res.status === 404) {
      res = await apiFetch(`/api/temp/${temp_id}/ocr-sync/`, { method: 'POST' })
    }
    if (!res.ok) {
      const err = await res.json().catch(()=>({}))
      throw new Error(err.error || `OCR 실패 (${res.status})`)
    }
    let data = await res.json()

    // job_id 방식이면 폴링
    if (data.job_id) {
      const jobId = data.job_id
      for (let i=0; i<60; i++) {
        await new Promise(r=>setTimeout(r, 1000))
        const jr = await apiFetch(`/api/temp/job/${jobId}/`)
        if (!jr.ok) continue
        const jd = await jr.json()

        if (jd.status === 'queued') {
          ocrQueueInfo.value = {
            status: 'queued',
            aheadCount: jd.ahead_count ?? 0,
            estimatedWaitSeconds: jd.estimated_wait_seconds ?? null,
          }
          continue
        }
        if (jd.status === 'processing') {
          ocrQueueInfo.value = { status: 'processing' }
        }
        if (jd.status === 'done' && jd.result) {
          data = jd.result
          break
        }
        if (jd.status === 'failed') throw new Error(jd.error || 'OCR 실패')
      }
    }

    const chords = data.chords || data.result?.chords || []
    if (chords && chords.length) {
      lines.value = toLines(chords)
      message.value = isRerun
        ? `OCR 재실행 완료: ${chords.length}개 라인 인식 (기존 수정 내용은 대체되었습니다)`
        : `OCR 완료: ${chords.length}개 라인 인식`
      ocrHasRun.value = true
      emit('updated', { ...props.sheet, chords })
    } else if (data.ocr_raw_text) {
      message.value = isRerun ? 'OCR 재실행 완료 (원문만 있음)' : 'OCR 완료 (원문만 있음)'
      ocrHasRun.value = true
    } else {
      ocrError.value = 'OCR 결과가 비어있습니다.'
    }
  } catch (e) {
    ocrError.value = e.message || 'OCR 중 오류'
  } finally {
    ocrLoading.value = false
    ocrQueueInfo.value = null
  }
}


const NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const NOTE_IDX = Object.fromEntries(NOTES.map((n,i)=>[n,i]))
NOTE_IDX['Db']=1; NOTE_IDX['Eb']=3; NOTE_IDX['Fb']=4; NOTE_IDX['Gb']=6
NOTE_IDX['Ab']=8; NOTE_IDX['Bb']=10; NOTE_IDX['Cb']=11; NOTE_IDX['E#']=5; NOTE_IDX['B#']=0

function transposeChordName(name, semitones) {
  if (!name || !semitones) return name
  const s = String(name).trim()
  if (s.includes('/')) {
    return s.split('/').map(p => transposeChordName(p, semitones)).join('/')
  }
  const m = s.match(/^([A-Ga-g])([#b]?)(.*)$/)
  if (!m) return s
  const root = m[1].toUpperCase() + (m[2] || '')
  const idx = NOTE_IDX[root]
  if (idx === undefined) return s
  const newRoot = NOTES[(idx + semitones % 12 + 12) % 12]
  return newRoot + (m[3] || '')
}


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


function toLines(raw) {
  if (!Array.isArray(raw) || !raw.length) return []
  // 이미 lines 형식이면 그대로 (chord/text 호환)
  if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].items)) {
    return raw.map((L, i) => ({
      id: L.id || `L${i}`,
      y: L.y ?? 0.1 + i * 0.08,
      xStart: L.xStart ?? 0.01,
      xEnd: L.xEnd ?? 0.99,
      height: L.height ?? 0.032,
      items: ensureItemT(
        (L.items || []).map((it, j) => ({
          id: it.id || `i${i}_${j}`,
          chord: it.chord || it.text || '',
          t: it.t ?? 0.5,
          manual: !!it.manual
        }))
      ),
    }))
  }

  // === 절대좌표 모드 ===
  // raw = [{chord/text, x, y}] 형태
  // x,y가 픽셀 좌표면 그대로 %로 변환해서 한 줄씩 쪼개지 않고 y로만 그룹핑
  // 저장된 y가 있으면 절대 덮어쓰지 않음 - 사용자 드래그 위치 유지
  const W = 750 // 악보 이미지 예상 폭
  const H = 1100 // 예상 높이

  // 엣지 노이즈 제거: 왼쪽 5% 오른쪽 5% 밖은 버림
  const filtered = raw.filter(c => {
    if (typeof c === 'string') return true
    const x = c.x ?? 0
    if (x < 35 || x > 700) return false
    const name = c.chord || c.text || ''
    if (!name) return false
    return true
  })

  const sorted = [...filtered].sort((a,b) => (a.y ?? 0) - (b.y ?? 0))

  const groups = []
  let cur = []
  let lastY = null
  const Y_GAP = 45

  for (const c of sorted) {
    const y = c.y ?? 0
    const x = c.x ?? 0
    const name = typeof c === 'string' ? c : (c.chord || c.text || '')
    if (lastY === null || Math.abs(y - lastY) <= Y_GAP) {
      cur.push({ id: c.id || `c_${groups.length}_${cur.length}`, chord: name, x, y, t: x / W })
      lastY = lastY === null ? y : (lastY*0.7 + y*0.3)
    } else {
      if (cur.length) groups.push(cur)
      cur = [{ id: c.id || `c_${groups.length}_0`, chord: name, x, y, t: x / W }]
      lastY = y
    }
  }
  if (cur.length) groups.push(cur)

  return groups.map((g, gi) => {
    g.sort((a,b) => a.x - b.x)
    const avgY = g.reduce((s,it)=>s+it.y,0)/g.length
    return {
      id: `L${gi}`,
      y: Math.min(0.92, Math.max(0.04, avgY / H )),
      xStart: 0.01,
      xEnd: 0.99,
      height: 0.032,
      items: ensureItemT(g.map(it => ({
        id: it.id,
        chord: it.chord,
        t: Math.min(0.98, Math.max(0.02, it.t))
      })))
    }
  })
}


watch(() => props.sheet, (s) => {
  lines.value = toLines(s.chords)
  semitones.value = s.transpose_semitones || 0
  ocrHasRun.value = !!(s.chords?.length || s.ocr_raw_text)
  if (s.chord_font_size) {
    chordFontPx.value = s.chord_font_size
  } else if (s.chordFontSize) {
    chordFontPx.value = s.chordFontSize
  }
}, { immediate: true })

const displayLines = computed(() => {
  const delta = semitones.value || 0
  return lines.value.map(L => ({
    ...L,
    items: (L.items || []).map(it => ({
      ...it,
      chord: delta ? transposeChordName(it.chord, delta) : it.chord,
    })),
  }))
})


const paletteChords = computed(() => {
  if (!selectedRoot.value) return []
  return VARIANTS[selectedRoot.value] || [selectedRoot.value]
})

function lineStyle(line) {
  // y = 코드줄 세로 중앙, height = 띠 높이 (정규화 0~1)
  const h = Math.max(line.height || 0.028, 0.015)
  const y = line.y ?? 0.1
  return {
    top: `${(y - h / 2) * 100}%`,
    left: `${(line.xStart || 0) * 100}%`,
    width: `${((line.xEnd || 0.9) - (line.xStart || 0)) * 100}%`,
    height: `${h * 100}%`,
  }
}

function chordLeftPct(line, item) {
  // t = 줄 안 상대 위치 (0~1). 보정 배율 없이 그대로 표시
  if (typeof item.t !== 'number' || Number.isNaN(item.t)) return '50%'
  return `${Math.min(98, Math.max(2, item.t * 100))}%`
}

function stageRect() {
  return stageRef.value?.getBoundingClientRect()
}

function normFromEvent(e) {
  const rect = stageRect()
  if (!rect) return null
  return {
    x: Math.min(0.99, Math.max(0.01, (e.clientX - rect.left) / rect.width)),
    y: Math.min(0.99, Math.max(0.01, (e.clientY - rect.top) / rect.height)),
  }
}

function startDrag(e, type, lineId, itemId = null) {
  // 코드 선택(삽입) 중에는 드래그보다 클릭 삽입 우선
  if (placeChord.value) return
  e.preventDefault()
  e.stopPropagation()
  activeLineId.value = lineId
  const line0 = lines.value.find((L) => L.id === lineId)
  const pos0 = normFromEvent(e)
  // 코드 드래그 시: 클릭 지점과 코드 중앙의 차이를 보존 (선택 순간 점프 방지)
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
    type,
    lineId,
    itemId,
    moved: false,
    startX: pos0?.x ?? 0,
    startY: pos0?.y ?? 0,
    origY: line0?.y ?? 0,
    origHeight: line0?.height ?? 0.032,
    origXStart: line0?.xStart ?? 0.01,
    origXEnd: line0?.xEnd ?? 0.99,
    origAbs: null,
    chordGrabOffset,
    origChordT,
  }
  const onMove = (ev) => {
    const pos = normFromEvent(ev)
    if (!pos || !drag.value) return
    drag.value.moved = true
    const line = lines.value.find((L) => L.id === drag.value.lineId)
    if (!line) return
    const t = drag.value.type
    // 절대 위치 보존을 위한 원본 절대 x 저장 (최초 드래그 시작 시)
    if (!drag.value.origAbs) {
      const span0 = drag.value.origXEnd - drag.value.origXStart
      drag.value.origAbs = (line.items || []).map(it => {
        const tt = typeof it.t === 'number' ? it.t : 0.5
        return { id: it.id, abs: drag.value.origXStart + tt * span0 }
      })
    }
    const restoreT = (newStart, newEnd) => {
      const newSpan = newEnd - newStart
      if (newSpan <= 0.001) return
      for (const it of line.items) {
        const saved = drag.value.origAbs.find(a => a.id === it.id)
        if (!saved) continue
        let nt = (saved.abs - newStart) / newSpan
        it.t = Math.min(0.98, Math.max(0.02, nt))
      }
    }

    if (t === 'line-y' || t === 'line-body') {
      // y 이동만, x 이동은 코드 절대위치 유지 (요청사항: 사이즈 움직여도 코드 위치 고정)
      const dy = pos.y - drag.value.startY
      line.y = Math.min(0.98, Math.max(0.02, drag.value.origY + dy))
      // x는 고정 - 코드 절대위치 보존 (이동시키고 싶으면 아래 2줄 주석 해제)
      // const dx = pos.x - drag.value.startX ...
    } else if (t === 'line-h-top') {
      // 위 가장자리를 포인터 위치로 직접 맞춤 (더 직관적)
      const origBottom = drag.value.origY + drag.value.origHeight / 2
      const newTop = Math.min(origBottom - 0.012, Math.max(0.005, pos.y))
      line.height = Math.max(0.012, origBottom - newTop)
      line.y = (newTop + origBottom) / 2
    } else if (t === 'line-h-bottom') {
      // 아래 가장자리를 포인터 위치로 직접 맞춤
      const origTop = drag.value.origY - drag.value.origHeight / 2
      const newBottom = Math.max(origTop + 0.012, Math.min(0.995, pos.y))
      line.height = Math.max(0.012, newBottom - origTop)
      line.y = (newBottom + origTop) / 2
    } else if (t === 'line-left') {
      const newStart = Math.min(line.xEnd - 0.08, pos.x)
      restoreT(newStart, line.xEnd)
      line.xStart = newStart
    } else if (t === 'line-right') {
      const newEnd = Math.max(line.xStart + 0.08, pos.x)
      restoreT(line.xStart, newEnd)
      line.xEnd = newEnd
    }
    else if (t === 'chord-x') {
      const item = line.items.find((it) => it.id === drag.value.itemId)
      if (!item) return
      const span = line.xEnd - line.xStart
      if (span <= 0.001) return
      // 포인터 - 클릭오프셋 = 코드 중앙이 되어야 할 절대 x
      const centerAbs = pos.x - (drag.value.chordGrabOffset || 0)
      const nt = (centerAbs - line.xStart) / span
      item.t = Math.min(0.98, Math.max(0.02, nt))
    }
  }
  const onUp = () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    const didMove = drag.value?.moved
    drag.value = null
    if (didMove) saveLines()
  }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}

function onLineBodyDown(e, line) {
  if (placeChord.value) return
  if (e.target !== e.currentTarget && !e.target.classList?.contains('items-layer')) return
  startDrag(e, 'line-body', line.id)
}

function onStageClick(e) {
  if (!placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  const ch = placeChord.value

  if (lines.value.length) {
    let best = null
    let bestDist = Infinity
    for (const L of lines.value) {
      const d = Math.abs((L.y || 0) - pos.y)
      if (d < bestDist) { bestDist = d; best = L }
    }
    const active = lines.value.find((L) => L.id === activeLineId.value)
    const target = active || best
    if (!target) return
    const span = (target.xEnd - target.xStart) || 0.8
    const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - target.xStart) / span))
    target.items.push({ 
      id: 'n' + Date.now().toString(36), 
      chord: ch, 
      t: tNorm,
      manual: true // 클릭 무보정 표시
    })
    activeLineId.value = target.id
    message.value = `"${ch}" 코드줄에 삽입`
    saveLines()
    return
  }

  const line = {
    id: 'L' + Date.now().toString(36),
    y: pos.y, xStart: 0.08, xEnd: 0.92, height: 0.032,
    items: [{ id: 'n' + Date.now().toString(36), chord: ch, t: 0.5, manual: true }],
  }
  lines.value.push(line)
  activeLineId.value = line.id
  message.value = `"${ch}" 새 코드줄에 삽입`
  saveLines()
}

function onLineClick(e, line) {
  e.stopPropagation()
  const L = lines.value.find((x) => x.id === line.id) || line
  activeLineId.value = L.id
  if (!placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  if (!Array.isArray(L.items)) L.items = []
  const span = (L.xEnd - L.xStart) || 0.8
  const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - L.xStart) / span))
  L.items.push({ id: 'n' + Date.now().toString(36), chord: placeChord.value, t: tNorm, manual: true })
  message.value = `"${placeChord.value}" 코드줄에 삽입`
  saveLines()
}

function onChipClick(e, line, item) {
  e.stopPropagation()
  if (placeChord.value) {
    onLineClick(e, line)
  }
}

function startEdit(lineId, item) {
  editKey.value = `${lineId}:${item.id}`
  const L = lines.value.find(x => x.id === lineId)
  const it = L?.items?.find(x => x.id === item.id)
  editValue.value = it?.chord || item.chord || ''
  requestAnimationFrame(() => {
    setTimeout(() => {
      const key = `${lineId}:${item.id}`
      const input = document.querySelector(`.chip input[data-edit-key="${key}"]`)
      if (input) {
        input.focus()
        const len = input.value.length
        try { input.setSelectionRange(len, len) } catch(e) {}
      }
    }, 0)
  })
}

function confirmEdit(lineId, item) {
  if (editKey.value !== `${lineId}:${item.id}`) return
  const L = lines.value.find(x => x.id === lineId)
  const it = L?.items?.find(x => x.id === item.id)
  if (it) {
    // 표시가 조옮김된 값이면 역산하지 않고 사용자가 입력한 값을 원본으로 저장
    it.chord = editValue.value.trim() || it.chord
  }
  editKey.value = null
  saveLines()
}
function removeItem(line, itemId) {
  const L = lines.value.find(x => x.id === line.id)
  if (!L) return
  L.items = L.items.filter((it) => it.id !== itemId)
  if (!L.items.length) lines.value = lines.value.filter((x) => x.id !== L.id)
  saveLines()
}
function pickRoot(root) { 
  selectedRoot.value = root
  const list = VARIANTS[root] || [root]
  placeChord.value = list[0] || root
  message.value = `"${placeChord.value}" 선택 · 코드줄 클릭 삽입 (Esc 취소)`
}
function pickVariant(ch) {
  placeChord.value = ch
  message.value = `"${ch}" 선택 · 코드줄 클릭 삽입 (Esc 취소)`
}
function pickCustom() {
  const ch = customChord.value.trim()
  if (!ch) return
  placeChord.value = ch
  message.value = `"${ch}" 선택 · 코드줄 클릭 삽입 (Esc 취소)`
}
function clearPlace() { placeChord.value = ''; message.value = '' }

function onKeydownEsc(e) {
  if (e.key === 'Escape' || e.key === 'Esc') {
    if (placeChord.value) {
      clearPlace()
      e.preventDefault()
    } else if (editKey.value) {
      editKey.value = null
      e.preventDefault()
    }
  }
}

onMounted(() => window.addEventListener('keydown', onKeydownEsc))
onUnmounted(() => window.removeEventListener('keydown', onKeydownEsc))
function addEmptyLine() {
  const line = {
    id: 'L' + Date.now().toString(36),
    y: 0.2 + lines.value.length * 0.05,
    xStart: 0.08, xEnd: 0.92, height: 0.032, items: [],
  }
  lines.value.push(line)
  activeLineId.value = line.id
}
function bumpFont(delta) {
  chordFontPx.value = Math.min(22, Math.max(9, chordFontPx.value + delta))
}

async function saveLines() {
  saving.value = true
  try {
    let res
    const payload = { 
      chords: lines.value,
      chord_font_size: chordFontPx.value // 이거 추가
    }
    if (isTemp()) {
      res = await apiFetch(`/api/temp/${sheetId()}/chords/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } else {
      res = await apiFetch(`/api/songs/${props.sheet.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    }
    if (!res.ok) throw new Error('저장 실패')
    const data = await res.json()
    emit('updated', { ...props.sheet, ...data, chords: data.chords ?? lines.value })
  } catch (e) { message.value = e.message }
  finally { saving.value = false }
}

async function doTranspose(delta) {
  // 보정 화면 미리보기용 (원본 lines 유지)
  semitones.value = (semitones.value || 0) + delta
  message.value = `조옮김 미리보기 ${semitones.value > 0 ? '+' : ''}${semitones.value}`
}

async function saveBase(mergeSongId = null, forceNew = false) {
  saving.value = true
  message.value = ''
  dupCandidates.value = []
  try {
    if (isTemp()) {
      const body = {
        temp_id: sheetId(),
        title: props.sheet.title || '',
        chords: lines.value,
        chord_font_size: chordFontPx.value,
        force_new: forceNew,
      }
      if (mergeSongId) body.merge_song_id = mergeSongId
      const res = await apiFetch('/api/songs/from-temp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 409 && data.error === 'duplicate_title') {
        dupCandidates.value = data.candidates || []
        message.value = data.message || '같은 제목의 곡이 있습니다'
        return
      }
      if (!res.ok) throw new Error(data.error || '보정본 저장 실패')
      emit('updated', { ...data, is_temp: false })
      message.value = '보정본 저장됨 (DB 등록)'
    } else {
      const res = await apiFetch(`/api/songs/${props.sheet.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chords: lines.value }),
      })
      if (!res.ok) throw new Error('저장 실패')
      emit('updated', await res.json())
      message.value = '보정본 저장됨'
    }
  } catch (e) { message.value = e.message }
  finally { saving.value = false }
}


async function confirmSheet() {
  confirming.value = true
  message.value = ''
  try {
    await saveLines()
    let song = { ...props.sheet, chords: lines.value, chord_font_size: chordFontPx.value }

    if (isTemp()) {
      const body = {
        temp_id: sheetId(),
        title: props.sheet.title || '',
        chords: lines.value,
        chord_font_size: chordFontPx.value,
        force_new: false,
      }
      let res = await apiFetch('/api/songs/from-temp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      let data = await res.json().catch(() => ({}))
      if (res.status === 409 && data.error === 'duplicate_title') {
        body.force_new = true
        res = await apiFetch('/api/songs/from-temp/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        data = await res.json().catch(() => ({}))
      }
      if (!res.ok) {
        throw new Error(data.error || data.message || '보정본 저장 실패. migrate / 서버 재시작을 확인하세요.')
      }
      // 서버 응답의 이미지 URL 유지 (temp URL 덮어쓰지 않음)
      song = {
        ...song,
        ...data,
        is_temp: false,
        optimized_image: data.optimized_image || data.image_url || song.optimized_image,
        chords: data.chords ?? lines.value,
      }
      emit('updated', song)
    } else {
      const res = await apiFetch(`/api/songs/${props.sheet.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chords: lines.value,
          chord_font_size: chordFontPx.value,
          title: props.sheet.title || '',
        }),
      })
      if (!res.ok) throw new Error('저장 실패')
      const data = await res.json()
      song = {
        ...song,
        ...data,
        optimized_image: data.optimized_image || song.optimized_image,
        chords: data.chords ?? lines.value,
      }
      emit('updated', song)
    }

    if (!song.id) throw new Error('곡 ID가 없습니다')

    // 온디맨드 렌더: 확정 시 variant 이미지 저장하지 않음. 조옮김 화면에서 실시간 생성.
    message.value = '확정됨 · 조옮김 단계로 이동'
    emit('next', song)
  } catch (e) {
    message.value = e.message || '확정 실패'
  } finally {
    confirming.value = false
  }
}

const imageUrl = computed(() => {
  let u =
    props.sheet.optimized_image ||
    props.sheet.image_url ||
    props.sheet.original_image ||
    ''
  if (!u) return ''
  if (typeof u === 'object' && u.url) u = u.url
  u = String(u)
  // data URL 은 그대로
  if (u.startsWith('data:')) return u
  if (u.startsWith('/')) u = `${API_BASE}${u}`
  if (u.includes('127.0.0.1') || u.includes('localhost')) {
    u = u.replace('https://', 'http://')
  } else if (u.startsWith('http://') && API_BASE.startsWith('https://')) {
    u = u.replace('http://', 'https://')
  }
  const bust = props.sheet.updated_at || Date.now()
  return u + (u.includes('?') ? '&' : '?') + 't=' + encodeURIComponent(bust)
})
const resultUrl = computed(() => {
  let u = props.sheet.result_image || ''
  if (!u) return ''
  if (u.startsWith('/')) u = `${API_BASE}${u}`
  if (u.includes('127.0.0.1') || u.includes('localhost')) {
    u = u.replace('https://', 'http://')
  } else if (u.startsWith('http://') && API_BASE.startsWith('https://')) {
    u = u.replace('http://', 'https://')
  }
  return u + (u.includes('?') ? '&' : '?') + 't=' + (props.sheet.updated_at || Date.now())
})

const ocrStatusText = computed(() => {
  const q = ocrQueueInfo.value
  const verb = ocrHasRun.value ? '재분석' : '분석'
  if (!q) return `OCR ${verb} 중...`
  if (q.status === 'queued') {
    const ahead = q.aheadCount ?? 0
    if (ahead <= 0) return '곧 시작합니다...'
    const wait = q.estimatedWaitSeconds
    return wait
      ? `앞에 ${ahead}명 대기 중 · 약 ${Math.round(wait)}초 예상`
      : `앞에 ${ahead}명 대기 중...`
  }
  return `악보를 ${verb}하는 중...`
})
</script>

<template>
  <div class="editor">
    <div class="top-actions">
      <button class="back" @click="emit('back')">← 목록</button>
    </div>
    <div class="ocr-bar">
      <button class="ocr-btn" @click="runOcr" :disabled="ocrLoading">
        {{ ocrLoading ? (ocrHasRun ? '재실행 중...' : 'OCR 중...') : (ocrHasRun ? 'OCR 다시 실행' : 'OCR 실행') }}
      </button>
      <span v-if="ocrLoading" class="ocr-status">
        <span class="ocr-status-dot" :class="{ queued: ocrQueueInfo?.status === 'queued' }" />
        {{ ocrStatusText }}
      </span>
      <span v-else-if="ocrError" class="ocr-error">{{ ocrError }}</span>
      <span v-else-if="ocrHasRun" class="ocr-hint" style="color:#d00; font-weight:700;">⚠️ 다시 실행하면 수정한 내용이 사라집니다</span>
      <span v-else class="ocr-hint">업로드한 이미지에서 기타 코드를 자동으로 인식합니다</span>
      <span v-if="message" class="msg" style="margin-left:8px">{{ message }}</span>
    </div>
    <div class="size-bar">
      <span>코드 크기</span>
      <button type="button" @click="bumpFont(-1)">A-</button>
      <span class="size-val">{{ chordFontPx }}px</span>
      <button type="button" @click="bumpFont(1)">A+</button>
    </div>
    <div class="stage-frame" v-if="imageUrl">
    <div ref="stageRef" class="stage" :class="{ placing: !!placeChord }" @click="onStageClick">
      <img :src="imageUrl" class="score-img" draggable="false" alt="악보" />
      <div v-if="ocrLoading" class="ocr-scan-overlay">
        <div class="ocr-scan-info">
          <span class="ocr-scan-spinner" v-if="ocrQueueInfo?.status === 'queued'" />
          <span>{{ ocrStatusText }}</span>
        </div>
        <div class="ocr-scan-track">
          <div class="ocr-scan-line" />
          <div class="ocr-scan-glass">
            <svg viewBox="0 0 24 24" width="34" height="34" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="10.5" cy="10.5" r="6.5" stroke="#0d6efd" stroke-width="2.4"/>
              <line x1="15.3" y1="15.3" x2="21" y2="21" stroke="#0d6efd" stroke-width="2.4" stroke-linecap="round"/>
            </svg>
          </div>
        </div>
      </div>
      <div
        v-for="line in displayLines"
        :key="line.id"
        class="chord-line"
        :class="{ active: activeLineId === line.id }"
        :style="lineStyle(line)"
        @click="onLineClick($event, line)"
        @pointerdown="onLineBodyDown($event, line)"
      >
        <div class="handle left" @pointerdown="startDrag($event, 'line-left', line.id)" />
        <div class="handle right" @pointerdown="startDrag($event, 'line-right', line.id)" />
        <div class="handle top" @pointerdown="startDrag($event, 'line-h-top', line.id)" />
        <div class="handle bottom" @pointerdown="startDrag($event, 'line-h-bottom', line.id)" />
        <div class="items-layer">
          <div
            v-for="item in line.items"
            :key="item.id"
            class="chip"
            :style="{ left: chordLeftPct(line, item), fontSize: chordFontPx + 'px' }"
            @pointerdown="startDrag($event, 'chord-x', line.id, item.id)"
            @click="onChipClick($event, line, item)"
            @dblclick.stop="startEdit(line.id, item)"
          >
            <template v-if="editKey === line.id + ':' + item.id">
              <input :data-edit-key="line.id + ':' + item.id" v-model="editValue" @keyup.enter="confirmEdit(line.id, item)" @blur="confirmEdit(line.id, item)" @click.stop @pointerdown.stop @keydown.esc.stop="editKey = null" />
            </template>
            <template v-else>
              <span>{{ item.chord }}</span>
              <button class="x" @click.stop="removeItem(line, item.id)" @pointerdown.stop>×</button>
            </template>
          </div>
        </div>
      </div>
      <div v-if="placeChord" class="place-banner" @click.stop>
        「{{ placeChord }}」 선택됨 — 코드줄 클릭으로 삽입 · Esc 취소
        <button type="button" @click="clearPlace">취소</button>
      </div>
    </div>
    </div>
    <section class="palette">
      <h3>코드 선택</h3>
      <div class="roots">
        <button v-for="r in ROOTS" :key="r" type="button" class="root" :class="{ on: selectedRoot === r }" @click="pickRoot(r)">{{ r }}</button>
      </div>
      <div v-if="selectedRoot" class="variants">
        <button v-for="ch in paletteChords" :key="ch" type="button" class="pchip" :class="{ on: placeChord === ch }" @click="pickVariant(ch)">{{ ch }}</button>
      </div>
      <div class="custom-row">
        <input v-model="customChord" placeholder="직접 입력" @keyup.enter="pickCustom" />
        <button type="button" class="act" @click="pickCustom">선택</button>
        <button type="button" class="act ghost" @click="addEmptyLine">+ 새 줄</button>
      </div>
    </section>
    <section class="transpose" v-if="pageMode !== 'correct'">
      <h3>조옮김</h3>
      <div class="btns">
        <button @click="doTranspose(-1)" :disabled="saving">−1</button>
        <button @click="doTranspose(-2)" :disabled="saving">−2</button>
        <span class="current">{{ semitones > 0 ? '+' : '' }}{{ semitones }}</span>
        <button @click="doTranspose(1)" :disabled="saving">+1</button>
        <button @click="doTranspose(2)" :disabled="saving">+2</button>
      </div>
    </section>
    <button class="confirm" :disabled="confirming || !lines.length" @click="confirmSheet">
      {{ confirming ? '확정 중…' : '확정 · 조옮김 단계로' }}
    </button>
    <section v-if="pageMode !== 'correct' && resultUrl" class="result-section">
      <h3>생성된 기타 코드 악보</h3>
      <img :src="resultUrl" alt="결과 악보" class="result-img" />
      <a class="dl" :href="resultUrl" target="_blank" rel="noopener" download>이미지 열기 / 저장</a>
    </section>
  </div>
</template>

<style scoped>
.editor { display: flex; flex-direction: column; gap: 1rem; max-width: 920px; margin: 0 auto; }
.top-actions { display: flex; justify-content: space-between; align-items: center; }
.back { background: none; border: none; cursor: pointer; color: #1a1a2e; }
.meta { font-size: 0.85rem; color: #666; }
.hint { font-size: 0.85rem; color: #444; background: #f5f7fa; padding: 0.6rem 0.8rem; border-radius: 6px; line-height: 1.5; }
.ocr-bar { display: flex; gap: 0.6rem; align-items: center; padding: 0.6rem 0.8rem; background: #f0f6ff; border: 1px solid #c5d9ff; border-radius: 8px; flex-wrap: wrap; }
.ocr-btn { padding: 0.5rem 0.9rem; background: #0d6efd; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-weight: 700; }
.ocr-btn:disabled { opacity: 0.6; }
.ocr-error { color: #c00; font-size: 0.85rem; }
.ocr-hint { color: #555; font-size: 0.85rem; }
.ocr-status { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #0d6efd; font-weight: 600; }
.ocr-status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #0d6efd;
  animation: ocr-dot-pulse 1s ease-in-out infinite;
}
.ocr-status-dot.queued { background: #f5a623; }
@keyframes ocr-dot-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.1); }
}

/* --- OCR 진행 중 돋보기 스캔 오버레이 --- */
.ocr-scan-overlay {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.9rem;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(1.5px);
}
.ocr-scan-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.9rem;
  background: rgba(26, 26, 46, 0.88);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 999px;
  white-space: nowrap;
}
.ocr-scan-spinner {
  width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: ocr-spin 0.8s linear infinite;
}
@keyframes ocr-spin { to { transform: rotate(360deg); } }
.ocr-scan-track {
  position: relative;
  width: 78%;
  max-width: 420px;
  height: 64px;
}
.ocr-scan-line {
  position: absolute;
  left: 0; right: 0; top: 50%;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(13,110,253,0.65), transparent);
  animation: ocr-line-pulse 1.4s ease-in-out infinite;
}
@keyframes ocr-line-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
.ocr-scan-glass {
  position: absolute;
  top: 50%;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,0.25));
  animation: ocr-glass-sweep 1.8s cubic-bezier(0.45, 0, 0.55, 1) infinite;
}
@keyframes ocr-glass-sweep {
  0%   { left: 0%;   transform: translate(0, -50%) rotate(-8deg); }
  25%  { left: 50%;  transform: translate(-50%, -65%) rotate(8deg); }
  50%  { left: 100%; transform: translate(-100%, -50%) rotate(-8deg); }
  75%  { left: 50%;  transform: translate(-50%, -35%) rotate(8deg); }
  100% { left: 0%;   transform: translate(0, -50%) rotate(-8deg); }
}
.mode-bar { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
.mode-bar button { padding: 0.4rem 0.75rem; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; font-weight: 600; }
.mode-bar button.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.mode-bar .save-base { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.dup-box { background: #fff8e6; border: 1px solid #e6c200; border-radius: 8px; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.4rem; }
.dup-box button { text-align: left; padding: 0.5rem 0.75rem; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; }
.dup-box .force { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.size-bar { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }
.size-bar button { padding: 0.25rem 0.55rem; border: 1px solid #ccc; border-radius: 5px; background: #fff; cursor: pointer; font-weight: 700; }
.size-val { min-width: 2.5rem; text-align: center; font-weight: 600; }
.stage-frame {
  width: 100%;
  min-height: 360px;
  max-height: 75vh;
  overflow: auto;
  background: #e8e8e8;
  border: 1px solid #ddd;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
.stage {
  position: relative;
  width: 100%;
  max-width: 640px;
  border: none;
  background: #fff;
  user-select: none;
  touch-action: none;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.stage.placing { cursor: crosshair; outline: 3px solid #ff2d55; outline-offset: -2px; box-shadow: 0 0 0 4px rgba(255,45,85,0.25); }
.score-img {
  display: block;
  width: 100%;
  height: auto;
  vertical-align: top;
  pointer-events: none;
}
.chord-line {
  position: absolute;
  box-sizing: border-box;
  background: transparent;
  border: none;
  /* 기본은 거의 안 보이게, 호버/선택 시에만 얇은 선 */
  box-shadow: inset 0 0 0 1px rgba(0, 160, 255, 0.12);
  border-radius: 2px;
  z-index: 2;
  min-height: 18px;
  cursor: grab;
}
.chord-line:hover {
  box-shadow: inset 0 0 0 1px rgba(0, 160, 255, 0.28);
}
.chord-line.active {
  background: rgba(0, 180, 255, 0.04);
  box-shadow: inset 0 0 0 1px rgba(0, 160, 255, 0.4);
}
.chord-line:active { cursor: grabbing; }
/* 핸들이 두꺼운 파란 테두리처럼 보이던 원인 → 기본 투명, 호버 시에만 */
.handle {
  position: absolute;
  z-index: 4;
  background: transparent;
  opacity: 0;
}
.chord-line:hover .handle,
.chord-line.active .handle {
  opacity: 1;
  background: rgba(13, 110, 253, 0.2);
}
.handle.left { left: -6px; top: 0; bottom: 0; width: 12px; cursor: ew-resize; }
.handle.right { right: -6px; top: 0; bottom: 0; width: 12px; cursor: ew-resize; }
.handle.top { top: -6px; left: 0; right: 0; height: 12px; cursor: ns-resize; }
.handle.bottom { bottom: -6px; left: 0; right: 0; height: 12px; cursor: ns-resize; }
.handle.top::after,
.handle.bottom::after {
  content: '';
  position: absolute;
  left: 20%;
  right: 20%;
  height: 3px;
  top: 50%;
  transform: translateY(-50%);
  background: #3b82f6;
  border-radius: 2px;
  opacity: 0.85;
}
.handle.left::after,
.handle.right::after {
  content: '';
  position: absolute;
  top: 20%;
  bottom: 20%;
  width: 3px;
  left: 50%;
  transform: translateX(-50%);
  background: #3b82f6;
  border-radius: 2px;
  opacity: 0.85;
}
.items-layer { position: absolute; inset: 0; pointer-events: none; }
.chip {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  font-weight: 800;
  color: #ff2d55;
  text-shadow:
    0 0 2px #fff,
    0 0 3px #fff,
    1px 0 0 #fff,
    -1px 0 0 #fff,
    0 1px 0 #fff,
    0 -1px 0 #fff;
  background: transparent;
  border-radius: 3px;
  padding: 0 2px 0 4px;
  pointer-events: auto;
  cursor: grab;
  white-space: nowrap;
  max-width: 5rem;
}
.chip input { width: 2.6rem; font-size: inherit; font-weight: 700; border: 1px solid #333; border-radius: 2px; padding: 0 2px; }
.chip .x { border: none; background: transparent; color: #a00; cursor: pointer; font-size: 0.9em; padding: 0 1px; opacity: 0.55; }
.place-banner { position: absolute; left: 0; right: 0; bottom: 0; background: rgba(13, 110, 253, 0.92); color: #fff; text-align: center; padding: 0.4rem; font-size: 0.9rem; z-index: 10; }
.place-banner button { background: #fff; border: none; border-radius: 4px; padding: 2px 8px; margin-left: 6px; cursor: pointer; }
.palette h3 { margin: 0 0 0.4rem; font-size: 0.95rem; }
.roots { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.5rem; }
.root { width: 2.4rem; height: 2.4rem; border-radius: 50%; border: 2px solid #ccc; background: #fff; font-weight: 800; font-size: 1rem; cursor: pointer; }
.root.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.variants { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.5rem; }
.pchip { padding: 0.35rem 0.55rem; border: 1px solid #ccc; border-radius: 5px; background: #fff; font-weight: 600; font-size: 0.85rem; cursor: pointer; }
.pchip.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.custom-row { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.custom-row input { flex: 1; min-width: 100px; padding: 0.4rem 0.55rem; border: 1px solid #ccc; border-radius: 6px; }
.act { padding: 0.4rem 0.75rem; border: none; border-radius: 6px; background: #1a1a2e; color: #fff; cursor: pointer; font-size: 0.85rem; }
.act.ghost { background: #fff; color: #1a1a2e; border: 1px solid #ccc; }
.transpose .btns { display: flex; align-items: center; gap: 0.5rem; }
.transpose button { padding: 0.5rem 0.9rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.current { min-width: 2.5rem; text-align: center; font-weight: 700; }
.confirm { padding: 0.85rem 1.25rem; background: #0a7a3e; color: #fff; border: none; border-radius: 8px; font-size: 1.05rem; font-weight: 600; cursor: pointer; }
.confirm:disabled { opacity: 0.5; cursor: not-allowed; }
.msg { color: #0a7; }
.result-section { margin-top: 0.5rem; padding: 1rem; border: 2px solid #0a7a3e; border-radius: 10px; background: #f6fbf8; }
.result-section h3 { margin: 0 0 0.75rem; color: #0a7a3e; }
.result-img { display: block; width: 100%; border-radius: 6px; border: 1px solid #ddd; }
.dl { display: inline-block; margin-top: 0.6rem; color: #0d6efd; font-size: 0.9rem; }
</style>
