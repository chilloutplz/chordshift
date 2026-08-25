<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { API_BASE, apiFetch } from '@/api/api.js'

const props = defineProps({
  sheet: { type: Object, required: true },
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
const saving = ref(false)
const confirming = ref(false)
const message = ref('')
const ocrLoading = ref(false)
const ocrError = ref('')
// OCR 큐 대기 정보 - { status: 'queued'|'processing', aheadCount, estimatedWaitSeconds }
const ocrQueueInfo = ref(null)
// 이 시트에 대해 OCR을 이미 한 번이라도 실행한 적 있는지
const ocrHasRun = ref(!!(props.sheet.chords?.length || props.sheet.ocr_raw_text))
// 저장 안 된 변경사항 추적용 dirty 플래그 - 뒤로가기/앱 종료 시 경고용
const dirty = ref(false)
// 앱 안에서 화면을 가로로 돌려보는 모드 (기기 자체 회전과 무관하게 CSS로 구현)
const landscapeMode = ref(false)
const editKey = ref(null)
const editValue = ref('')
const activeLineId = ref(null)
const placeChord = ref('')
const customChord = ref('')
const stageRef = ref(null)
const stageFrameRef = ref(null)
const drag = ref(null)
const chordFontPx = ref(13)
const selectedRoot = ref(null)

// --- 하단 도구 탭: 배치(코드 고르기) / 조정(이동·크기) ---
const bottomTab = ref('place')
watch(bottomTab, (tab) => {
  if (tab !== 'place') clearPlace()
})

// --- 캔버스 확대/축소 (모바일에서 정밀 배치용) ---
const zoom = ref(1)
const ZOOM_MIN = 1
const ZOOM_MAX = 2.5
const ZOOM_STEP = 0.25
function zoomIn() {
  zoom.value = Math.min(ZOOM_MAX, +(zoom.value + ZOOM_STEP).toFixed(2))
}
function zoomOut() {
  zoom.value = Math.max(ZOOM_MIN, +(zoom.value - ZOOM_STEP).toFixed(2))
}
// 확대된 상태에서 버튼으로 화면 이동 - 캔버스를 직접 드래그하면
// 라인이 잡혀 오동작하기 쉬우므로, 드래그 없이 이동할 수 있는 수단 제공
const PAN_STEP = 90
function panBy(dx, dy) {
  stageFrameRef.value?.scrollBy({ left: dx, top: dy, behavior: 'smooth' })
}
// 좌표 계산(normFromEvent)은 실제 렌더된 stage 크기를 기준으로 하므로
// 확대해도 드래그/클릭 위치 계산은 그대로 정확하게 맞는다.
const stageStyle = computed(() => {
  if (zoom.value <= 1) return {}
  return { width: `${zoom.value * 100}%`, maxWidth: 'none' }
})

// --- 두 손가락 핀치로 확대/축소 ---
// stage-frame에 pointerdown을 캡처 단계로 걸어서, 자식(코드줄/칩 등)이
// stopPropagation을 해도 두 번째 손가락 터치를 항상 감지할 수 있게 한다.
// pointerup/cancel은 핀치 중이 아니어도 항상(마운트 시부터) 리스닝해야 한다 -
// 안 그러면 마우스 클릭 한 번만 해도 그 포인터가 지워지지 않고 남아있다가
// 다음 클릭과 합쳐져 "2개"로 잘못 인식되어 핀치가 오작동한다.
const activePointers = new Map()
let pinchStartDist = 0
let pinchStartZoom = 1

function pointerDist(pts) {
  return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
}

function onStagePointerDownCapture(e) {
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (activePointers.size === 2) {
    // 핀치 시작 - 진행 중이던 단일 드래그(코드/줄 이동)는 취소
    drag.value = null
    pinchStartDist = pointerDist([...activePointers.values()])
    pinchStartZoom = zoom.value
  }
}
function onGlobalPointerMove(e) {
  if (!activePointers.has(e.pointerId)) return
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (activePointers.size < 2 || pinchStartDist <= 0) return
  const dist = pointerDist([...activePointers.values()])
  zoom.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, +(pinchStartZoom * (dist / pinchStartDist)).toFixed(2)))
}
function onGlobalPointerUp(e) {
  activePointers.delete(e.pointerId)
  if (activePointers.size < 2) {
    pinchStartDist = 0
  }
}
// 화면에 보여줄 코드 글자 크기 = 저장용 기준 크기 × 확대 배율.
// (서버에 저장되는 chordFontPx 자체는 건드리지 않고, 화면 표시만 확대에 맞춰 커짐)
const displayFontPx = computed(() => Math.round(chordFontPx.value * zoom.value))

// --- 코드줄 다중 선택 (Shift+클릭, 모바일은 "Multi" 토글) ---
const multiSelectMode = ref(false)
const selectedLineIds = ref([])
const showLineHelp = ref(false) // Shift+클릭 안내를 기본적으로 숨기고 ? 버튼으로만 노출

// 이동/좌우 툴이 실제로 작동할 대상 줄 id 목록.
// 다중 선택된 게 있으면 그것들, 없으면 현재 활성(activeLineId) 하나.
const targetLineIds = computed(() =>
  selectedLineIds.value.length ? selectedLineIds.value : (activeLineId.value ? [activeLineId.value] : []),
)

function isLineSelected(id) {
  if (selectedLineIds.value.length) return selectedLineIds.value.includes(id)
  return activeLineId.value === id
}

function toggleLineSelection(id) {
  const idx = selectedLineIds.value.indexOf(id)
  if (idx >= 0) {
    selectedLineIds.value = selectedLineIds.value.filter((x) => x !== id)
  } else {
    selectedLineIds.value = [...selectedLineIds.value, id]
  }
  activeLineId.value = id
}

function toggleMultiSelectMode() {
  multiSelectMode.value = !multiSelectMode.value
  if (multiSelectMode.value) {
    // 이미 선택되어 있던 줄이 있으면 다중 선택으로 그대로 이어받는다
    if (activeLineId.value && !selectedLineIds.value.length) {
      selectedLineIds.value = [activeLineId.value]
    }
  } else {
    selectedLineIds.value = []
  }
}

function clearLineSelection() {
  selectedLineIds.value = []
}

// --- 코드줄 이동 / 코드만 좌우 이동 툴 ---
const LINE_NUDGE_STEP = 0.006
const CHORD_NUDGE_STEP = 0.01

function targetLines() {
  const ids = targetLineIds.value
  return lines.value.filter((L) => ids.includes(L.id))
}

// 줄 전체를 상하좌우로 이동 (프레임 xStart/xEnd/y를 함께 옮김 - 코드 간 간격 유지)
function nudgeLine(dx, dy) {
  const targets = targetLines()
  if (!targets.length) return
  for (const L of targets) {
    const width = (L.xEnd ?? 0.99) - (L.xStart ?? 0.01)
    let newXStart = (L.xStart ?? 0.01) + dx
    newXStart = Math.max(0.005, Math.min(0.995 - width, newXStart))
    L.xStart = newXStart
    L.xEnd = newXStart + width
    L.y = Math.min(0.98, Math.max(0.02, (L.y ?? 0.1) + dy))
  }
  dirty.value = true
}

// 줄의 프레임은 그대로 두고, 그 안의 코드들만 좌우로 같이 이동
function nudgeChords(dt) {
  const targets = targetLines()
  if (!targets.length) return
  for (const L of targets) {
    for (const it of L.items || []) {
      const cur = typeof it.t === 'number' ? it.t : 0.5
      it.t = Math.min(0.98, Math.max(0.02, cur + dt))
    }
  }
  dirty.value = true
}

// --- 저장 시 제목 입력 모달 ---
const showSaveModal = ref(false)
const saveTitle = ref('')
const saveTitleError = ref('')
const forceNewOnDuplicate = ref(false)
const dupCandidates = ref([]) // 중복 제목 발견 시 서버가 내려주는 기존 곡 후보 목록
const titleInputRef = ref(null)

// 모달이 열릴 때 제목 입력창에 자동 포커스 + 전체 선택 (바로 타이핑해서 덮어쓸 수 있게)
watch(showSaveModal, async (open) => {
  if (!open) return
  await nextTick()
  titleInputRef.value?.focus()
  titleInputRef.value?.select()
})

function openSaveModal() {
  saveTitle.value = (props.sheet.title || '').trim()
  saveTitleError.value = ''
  forceNewOnDuplicate.value = false
  dupCandidates.value = []
  showSaveModal.value = true
}
// 저장 버튼 클릭: 신규(temp) 업로드는 제목을 물어봐야 하지만,
// 이미 저장된 곡을 "수정"하는 경우엔 제목을 다시 물을 필요가 없으므로 바로 저장한다.
function handleSaveClick() {
  if (isTemp()) {
    openSaveModal()
  } else {
    saveTitle.value = (props.sheet.title || '').trim()
    confirmSheet()
  }
}
function closeSaveModal() {
  if (confirming.value) return
  showSaveModal.value = false
}
// 제목 입력 후 (다시) 저장 시도 - 중복 후보 목록은 초기화하고 새로 확인
function submitSaveModal() {
  const t = saveTitle.value.trim()
  if (!t) {
    saveTitleError.value = '제목을 입력해주세요'
    return
  }
  saveTitle.value = t
  saveTitleError.value = ''
  dupCandidates.value = []
  forceNewOnDuplicate.value = false
  confirmSheet()
}
// 중복 후보 중 하나를 골라 그 곡에 덮어쓰기 (merge)
function mergeIntoCandidate(candidate) {
  saveTitleError.value = ''
  confirmSheet(candidate.id)
}
// 중복이어도 별개의 새 곡으로 저장
function saveAsNewAnyway() {
  saveTitleError.value = ''
  forceNewOnDuplicate.value = true
  confirmSheet()
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
  // 재실행이면 기존 수정 내용이 사라진다는 걸 명확히 확인받고 진행
  if (ocrHasRun.value) {
    const ok = window.confirm('OCR을 다시 실행하면 지금까지 수정한 코드 내용이 모두 사라집니다.\n계속할까요?')
    if (!ok) return
  }
  const isRerun = ocrHasRun.value
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
        ? `OCR 재실행 완료: ${chords.length}개 라인 인식`
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
  const W = 750
  const H = 1100

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
  ocrHasRun.value = !!(s.chords?.length || s.ocr_raw_text)
  if (s.chord_font_size) {
    chordFontPx.value = s.chord_font_size
  } else if (s.chordFontSize) {
    chordFontPx.value = s.chordFontSize
  }
  // 서버(부모)로부터 받은 최신 상태로 갱신된 시점이므로 "저장 안 된 변경"은 없다
  dirty.value = false
}, { immediate: true })

const paletteChords = computed(() => {
  if (!selectedRoot.value) return []
  return VARIANTS[selectedRoot.value] || [selectedRoot.value]
})

function lineStyle(line) {
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
  if (placeChord.value) return
  // --- Line 작업 / Chord 작업 모드 분리 ---
  // 모바일에서 줄 핸들과 코드 칩 드래그가 같은 영역에 겹쳐 있어서
  // 오동작이 잦았다. 하단 탭("코드 배치" / "위치 조정")을 곧 "지금 무엇을
  // 다루는 중인가"의 모드로 삼아서, 그 모드에 해당하지 않는 제스처는
  // 아예 시작조차 하지 않도록 한다.
  const isLineOp = type !== 'chord-x'
  if (isLineOp && bottomTab.value !== 'adjust') return
  if (!isLineOp && bottomTab.value !== 'place') return
  // 주의: 여기서 e.preventDefault()를 호출하면 안 된다 -
  // 터치 환경에서 pointerdown에 preventDefault를 걸면 브라우저가 그 터치에서
  // 파생되는 click/dblclick 합성 이벤트 자체를 만들지 않아서, 더블탭으로
  // 편집모드 진입하는 게 완전히 막혀버린다. 스크롤/제스처 억제는
  // .chord-line/.handle/.chip에 걸어둔 CSS touch-action:none이 대신 처리한다.
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
    type,
    lineId,
    itemId,
    moved: false,
    startX: pos0?.x ?? 0,
    startY: pos0?.y ?? 0,
    startClientX: e.clientX,
    startClientY: e.clientY,
    origY: line0?.y ?? 0,
    origHeight: line0?.height ?? 0.032,
    origXStart: line0?.xStart ?? 0.01,
    origXEnd: line0?.xEnd ?? 0.99,
    origAbs: null,
    chordGrabOffset,
    origChordT,
  }
  // 클릭/탭인지 실제 드래그인지 구분하는 최소 이동 거리(px).
  // 이게 없으면 손가락/마우스의 미세한 떨림도 "이동"으로 잡혀서
  // 클릭하려던 코드/줄이 의도치 않게 살짝 밀리는 문제가 있었다.
  const DRAG_THRESHOLD_PX = 4
  const onMove = (ev) => {
    if (!drag.value) return
    if (!drag.value.moved) {
      const movedPx = Math.hypot(ev.clientX - drag.value.startClientX, ev.clientY - drag.value.startClientY)
      if (movedPx < DRAG_THRESHOLD_PX) return
      drag.value.moved = true
    }
    const pos = normFromEvent(ev)
    if (!pos) return
    const line = lines.value.find((L) => L.id === drag.value.lineId)
    if (!line) return
    const t = drag.value.type
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

    if (t === 'line-body') {
      // 손가락 드래그는 세로 이동만 반영한다 - 가로는 터치로 정밀하게
      // 맞추기 어려워서 오히려 오동작을 유발하므로, 가로 이동이 필요하면
      // "위치 조정" 탭의 ← → 버튼(정밀 이동)을 쓰도록 분리했다.
      const dy = pos.y - drag.value.startY
      line.y = Math.min(0.98, Math.max(0.02, drag.value.origY + dy))
    } else if (t === 'line-h-top') {
      const origBottom = drag.value.origY + drag.value.origHeight / 2
      const newTop = Math.min(origBottom - 0.012, Math.max(0.005, pos.y))
      line.height = Math.max(0.012, origBottom - newTop)
      line.y = (newTop + origBottom) / 2
    } else if (t === 'line-h-bottom') {
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
      manual: true
    })
    activeLineId.value = target.id
    message.value = `"${ch}" 코드줄에 삽입`
    dirty.value = true
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
  dirty.value = true
}

function onLineClick(e, line) {
  e.stopPropagation()
  const L = lines.value.find((x) => x.id === line.id) || line

  if (!placeChord.value && (e.shiftKey || multiSelectMode.value)) {
    toggleLineSelection(L.id)
    return
  }

  activeLineId.value = L.id
  selectedLineIds.value = []
  if (!placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  if (!Array.isArray(L.items)) L.items = []
  const span = (L.xEnd - L.xStart) || 0.8
  const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - L.xStart) / span))
  L.items.push({ id: 'n' + Date.now().toString(36), chord: placeChord.value, t: tNorm, manual: true })
  message.value = `"${placeChord.value}" 코드줄에 삽입`
  dirty.value = true
}

// 네이티브 dblclick은 모바일에서 touch-action:none 때문에 발생하지 않으므로
// (드래그를 위해 필요한 설정이라 되돌릴 수 없음), click 두 번을 직접 시간차로
// 감지해서 더블탭/더블클릭을 흉내낸다.
let lastChipClickKey = null
let lastChipClickTime = 0
const MANUAL_DBLCLICK_MS = 400

function onChipClick(e, line, item) {
  e.stopPropagation()
  if (placeChord.value) {
    onLineClick(e, line)
    return
  }
  const key = `${line.id}:${item.id}`
  const now = Date.now()
  if (lastChipClickKey === key && now - lastChipClickTime < MANUAL_DBLCLICK_MS) {
    lastChipClickKey = null
    if (editKey.value !== key) startEdit(line.id, item)
    return
  }
  lastChipClickKey = key
  lastChipClickTime = now
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
    it.chord = editValue.value.trim() || it.chord
    dirty.value = true
  }
  editKey.value = null
}
function removeItem(line, itemId) {
  const L = lines.value.find(x => x.id === line.id)
  if (!L) return
  L.items = L.items.filter((it) => it.id !== itemId)
  if (!L.items.length) {
    lines.value = lines.value.filter((x) => x.id !== L.id)
    selectedLineIds.value = selectedLineIds.value.filter((id) => id !== L.id)
    if (activeLineId.value === L.id) activeLineId.value = null
  }
  dirty.value = true
}
function pickRoot(root) {
  selectedRoot.value = root
  const list = VARIANTS[root] || [root]
  placeChord.value = list[0] || root
  message.value = `"${placeChord.value}" 선택 · 코드줄 탭해서 삽입`
}
function pickVariant(ch) {
  placeChord.value = ch
  message.value = `"${ch}" 선택 · 코드줄 탭해서 삽입`
}
function pickCustom() {
  const ch = customChord.value.trim()
  if (!ch) return
  placeChord.value = ch
  message.value = `"${ch}" 선택 · 코드줄 탭해서 삽입`
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

// 저장 안 된 변경사항이 있는 채로 앱을 벗어나려 할 때(모바일 뒤로가기,
// 탭 닫기, 새로고침 등) 브라우저 표준 경고창을 띄운다.
function handleBeforeUnload(e) {
  if (!dirty.value) return
  e.preventDefault()
  e.returnValue = ''
}

onMounted(() => {
  window.addEventListener('keydown', onKeydownEsc)
  window.addEventListener('pointermove', onGlobalPointerMove)
  window.addEventListener('pointerup', onGlobalPointerUp)
  window.addEventListener('pointercancel', onGlobalPointerUp)
  window.addEventListener('beforeunload', handleBeforeUnload)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydownEsc)
  window.removeEventListener('pointermove', onGlobalPointerMove)
  window.removeEventListener('pointerup', onGlobalPointerUp)
  window.removeEventListener('pointercancel', onGlobalPointerUp)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
// 앱 안의 "목록" 버튼도 마찬가지로 - 저장 안 된 변경사항이 있으면 한 번 확인
function handleBackClick() {
  if (dirty.value) {
    const ok = window.confirm('저장하지 않은 변경사항이 있습니다. 그래도 나가시겠어요?')
    if (!ok) return
  }
  emit('back')
}
function addEmptyLine() {
  const line = {
    id: 'L' + Date.now().toString(36),
    y: 0.2 + lines.value.length * 0.05,
    xStart: 0.08, xEnd: 0.92, height: 0.032, items: [],
  }
  lines.value.push(line)
  activeLineId.value = line.id
  dirty.value = true
}
function bumpFont(delta) {
  chordFontPx.value = Math.min(22, Math.max(9, chordFontPx.value + delta))
  dirty.value = true
}

async function saveLines() {
  saving.value = true
  try {
    let res
    const payload = {
      chords: lines.value,
      chord_font_size: chordFontPx.value
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

async function confirmSheet(mergeId = null) {
  confirming.value = true
  message.value = ''
  const titleToSave = saveTitle.value.trim()
  try {
    await saveLines()
    let song = { ...props.sheet, title: titleToSave, chords: lines.value, chord_font_size: chordFontPx.value }

    if (isTemp()) {
      const body = {
        temp_id: sheetId(),
        title: titleToSave,
        chords: lines.value,
        chord_font_size: chordFontPx.value,
        force_new: forceNewOnDuplicate.value,
      }
      if (mergeId) body.merge_song_id = mergeId
      const res = await apiFetch('/api/songs/from-temp/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (res.status === 409 && data.error === 'duplicate_title') {
        dupCandidates.value = data.candidates || []
        saveTitleError.value = data.message || `"${titleToSave}" 제목의 곡이 이미 있습니다.`
        showSaveModal.value = true
        return
      }
      if (!res.ok) {
        throw new Error(data.error || data.message || '보정본 저장 실패. migrate / 서버 재시작을 확인하세요.')
      }
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
          title: titleToSave,
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

    dupCandidates.value = []
    forceNewOnDuplicate.value = false
    showSaveModal.value = false
    message.value = '저장됨 · 조옮김 단계로 이동'
    emit('next', song)
  } catch (e) {
    message.value = e.message || '저장 실패'
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

// 상단 상태 배너에 표시할 내용 - 우선순위: 로딩 > 에러 > 일반 메시지
const statusBanner = computed(() => {
  if (ocrLoading.value) return { text: ocrStatusText.value, kind: 'loading' }
  if (ocrError.value) return { text: ocrError.value, kind: 'error' }
  if (message.value) return { text: message.value, kind: 'info' }
  return null
})
</script>

<template>
  <div class="editor" :class="{ landscape: landscapeMode }">
    <!-- 상단 미니 툴바: 뒤로가기 / OCR / 저장 한 줄로 -->
    <div class="top-bar">
      <button class="icon-btn" title="목록" aria-label="목록" @click="handleBackClick">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <button class="ocr-pill" @click="runOcr" :disabled="ocrLoading">
        {{ ocrLoading ? (ocrHasRun ? '재실행 중…' : 'OCR 중…') : (ocrHasRun ? 'OCR 재실행' : 'OCR 실행') }}
      </button>
      <button class="save-pill" :disabled="confirming || !lines.length" @click="handleSaveClick">
        {{ confirming ? '저장 중…' : '저장' }}
      </button>
      <button
        class="icon-btn"
        :class="{ on: landscapeMode }"
        title="가로 화면으로 보기"
        aria-label="가로 화면 전환"
        @click="landscapeMode = !landscapeMode"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="2" y="6" width="20" height="12" rx="2.5" stroke="currentColor" stroke-width="2" />
          <path d="M22 10v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </button>
    </div>

    <p v-if="statusBanner" class="status-banner" :class="statusBanner.kind">
      <span v-if="statusBanner.kind === 'loading'" class="ocr-status-dot" :class="{ queued: ocrQueueInfo?.status === 'queued' }" />
      {{ statusBanner.text }}
    </p>

    <!-- 캔버스: 화면 대부분 차지, 곧바로 보임 -->
    <div class="canvas-wrap" v-if="imageUrl">
      <div class="zoom-bar" :class="{ dim: zoom <= ZOOM_MIN }">
        <button type="button" :disabled="zoom <= ZOOM_MIN" @click="zoomOut" title="축소">−</button>
        <span class="zoom-val">{{ Math.round(zoom * 100) }}%</span>
        <button type="button" :disabled="zoom >= ZOOM_MAX" @click="zoomIn" title="확대">+</button>
      </div>
      <div class="pan-bar" v-if="zoom > ZOOM_MIN">
        <button type="button" class="pan-btn" title="위로" @click="panBy(0, -PAN_STEP)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 19V5M12 5l-5 5M12 5l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
        <button type="button" class="pan-btn" title="아래로" @click="panBy(0, PAN_STEP)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M12 19l-5-5M12 19l5-5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
        <button type="button" class="pan-btn" title="왼쪽으로" @click="panBy(-PAN_STEP, 0)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M5 12l5-5M5 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
        <button type="button" class="pan-btn" title="오른쪽으로" @click="panBy(PAN_STEP, 0)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M19 12l-5-5M19 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
      </div>
      <div ref="stageFrameRef" class="stage-frame" @pointerdown.capture="onStagePointerDownCapture">
        <div
          ref="stageRef"
          class="stage"
          :class="{ placing: !!placeChord, 'mode-line': bottomTab === 'adjust', 'mode-chord': bottomTab === 'place' }"
          :style="stageStyle"
          @click="onStageClick"
        >
          <img :src="imageUrl" class="score-img" draggable="false" @dragstart.prevent alt="악보" />
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
            v-for="line in lines"
            :key="line.id"
            class="chord-line"
            :class="{ active: isLineSelected(line.id) }"
            :style="lineStyle(line)"
            @click="onLineClick($event, line)"
            @pointerdown="onLineBodyDown($event, line)"
          >
            <div class="handle left" @pointerdown="startDrag($event, 'line-left', line.id)" />
            <div class="handle right" @pointerdown="startDrag($event, 'line-right', line.id)" />
            <div class="handle top" @pointerdown="startDrag($event, 'line-h-top', line.id)" />
            <div class="handle bottom" @pointerdown="startDrag($event, 'line-h-bottom', line.id)" />
            <div class="move-hint" title="드래그해서 코드줄 위아래로 이동">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 5 12 2 15 5" />
                <polyline points="15 19 12 22 9 19" />
                <line x1="12" y1="2" x2="12" y2="22" />
              </svg>
            </div>
            <div class="items-layer">
              <div
                v-for="item in line.items"
                :key="item.id"
                class="chip"
                :style="{ left: chordLeftPct(line, item), fontSize: displayFontPx + 'px' }"
                @pointerdown="startDrag($event, 'chord-x', line.id, item.id)"
                @click="onChipClick($event, line, item)"
                @dblclick.stop="startEdit(line.id, item)"
              >
                <template v-if="editKey === line.id + ':' + item.id">
                  <input :data-edit-key="line.id + ':' + item.id" v-model="editValue" @keyup.enter="confirmEdit(line.id, item)" @blur="confirmEdit(line.id, item)" @click.stop @pointerdown.stop @keydown.esc.stop="editKey = null" />
                  <button
                    class="x edit-x"
                    title="삭제"
                    @mousedown.prevent
                    @pointerdown.stop.prevent
                    @click.stop="removeItem(line, item.id)"
                  >×</button>
                </template>
                <template v-else>
                  <span>{{ item.chord }}</span>
                </template>
              </div>
            </div>
          </div>
          <div v-if="placeChord" class="place-banner" @click.stop>
            「{{ placeChord }}」 선택됨 — 코드줄 탭해서 삽입 · Esc 취소
            <button type="button" @click="clearPlace">취소</button>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="canvas-empty">악보 이미지를 불러오는 중입니다…</div>

    <!-- 하단 고정 도구: 배치 / 조정 탭 -->
    <div class="bottom-tools">
      <div class="bt-tabs">
        <button type="button" :class="{ on: bottomTab === 'place' }" @click="bottomTab = 'place'">코드 배치</button>
        <button type="button" :class="{ on: bottomTab === 'adjust' }" @click="bottomTab = 'adjust'">위치 조정</button>
      </div>

      <div class="bt-panel" v-show="bottomTab === 'place'">
        <div class="roots">
          <button v-for="r in ROOTS" :key="r" type="button" class="root" :class="{ on: selectedRoot === r }" @click="pickRoot(r)">{{ r }}</button>
        </div>
        <div v-if="selectedRoot" class="variants">
          <button v-for="ch in paletteChords" :key="ch" type="button" class="pchip" :class="{ on: placeChord === ch }" @click="pickVariant(ch)">{{ ch }}</button>
        </div>
        <div class="custom-row">
          <input v-model="customChord" placeholder="직접 입력" @keyup.enter="pickCustom" />
          <button type="button" class="act" @click="pickCustom">선택</button>
        </div>
      </div>

      <div class="bt-panel" v-show="bottomTab === 'adjust'">
        <div class="tool-line-block">
          <div class="tlb-col">
            <span class="tool-row-label">Line</span>
            <div class="tlb-controls">
              <button type="button" class="mini-btn" title="새 줄 추가" @click="addEmptyLine">+</button>
              <div class="tool-btns">
                <button type="button" :disabled="!targetLineIds.length" @click="nudgeLine(0, -LINE_NUDGE_STEP)" title="위로">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 19V5M12 5l-5 5M12 5l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
                </button>
                <button type="button" :disabled="!targetLineIds.length" @click="nudgeLine(0, LINE_NUDGE_STEP)" title="아래로">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 5v14M12 19l-5-5M12 19l5-5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
                </button>
                <button type="button" :disabled="!targetLineIds.length" @click="nudgeLine(-LINE_NUDGE_STEP, 0)" title="왼쪽으로">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M5 12l5-5M5 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
                </button>
                <button type="button" :disabled="!targetLineIds.length" @click="nudgeLine(LINE_NUDGE_STEP, 0)" title="오른쪽으로">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M19 12l-5-5M19 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
                </button>
              </div>
            </div>
          </div>
          <div class="tlb-col align-right">
            <span class="ml-label">Multi</span>
            <div class="tlb-controls">
              <button
                type="button"
                class="ml-switch"
                :class="{ on: multiSelectMode }"
                role="switch"
                :aria-checked="multiSelectMode"
                @click="toggleMultiSelectMode"
              >
                <span class="ml-knob" />
              </button>
              <button type="button" class="help-btn" title="도움말" @click="showLineHelp = !showLineHelp">?</button>
            </div>
          </div>
        </div>
        <p v-if="showLineHelp" class="help-text">PC는 Shift+클릭으로도 여러 줄을 선택할 수 있어요</p>
        <p v-if="selectedLineIds.length > 1" class="ms-count">
          {{ selectedLineIds.length }}개 선택됨
          <button type="button" class="ms-clear" @click="clearLineSelection">해제</button>
        </p>

        <div class="tool-divider"></div>

        <div class="tlb-col">
          <span class="tool-row-label">Chord</span>
          <div class="tlb-controls">
            <div class="tool-btns">
              <button type="button" @click="bumpFont(-1)">A-</button>
              <button type="button" @click="bumpFont(1)">A+</button>
            </div>
            <div class="tool-btns">
              <button type="button" :disabled="!targetLineIds.length" @click="nudgeChords(-CHORD_NUDGE_STEP)" title="코드들만 왼쪽으로">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M5 12l5-5M5 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
              </button>
              <button type="button" :disabled="!targetLineIds.length" @click="nudgeChords(CHORD_NUDGE_STEP)" title="코드들만 오른쪽으로">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M19 12l-5-5M19 12l5 5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showSaveModal" class="modal-backdrop" @click.self="closeSaveModal">
      <div class="modal-box">
        <h3>제목 입력</h3>
        <p class="modal-hint">
          중복 저장을 막기 위해 정확한 곡 제목을 입력해주세요.
        </p>
        <input
          ref="titleInputRef"
          v-model="saveTitle"
          type="text"
          class="modal-input"
          placeholder="곡 제목"
          :disabled="confirming"
          @keyup.enter="submitSaveModal"
        />
        <p v-if="saveTitleError" class="modal-error">{{ saveTitleError }}</p>

        <div v-if="dupCandidates.length" class="dup-block">
          <p class="dup-label">기존 곡에 덮어쓸까요?</p>
          <button
            v-for="c in dupCandidates"
            :key="c.id"
            type="button"
            class="dup-item"
            :disabled="confirming"
            @click="mergeIntoCandidate(c)"
          >
            {{ c.title || '(제목 없음)' }} 덮어쓰기
          </button>
          <button type="button" class="dup-newone" :disabled="confirming" @click="saveAsNewAnyway">
            아니요, 별개의 새 곡으로 저장
          </button>
        </div>

        <div class="modal-actions">
          <button type="button" class="modal-cancel" :disabled="confirming" @click="closeSaveModal">취소</button>
          <button v-if="!dupCandidates.length" type="button" class="modal-save" :disabled="confirming" @click="submitSaveModal">
            {{ confirming ? '저장 중…' : '저장' }}
          </button>
          <button v-else type="button" class="modal-save" :disabled="confirming" @click="submitSaveModal">
            {{ confirming ? '확인 중…' : '제목 다시 확인' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  max-width: 920px;
  margin: 0 auto;
}
/* 앱 안 가로 보기 모드 - 기기 자체 회전과 무관하게 화면 전체를 90도 돌려서
   가로로 넓게 쓸 수 있게 한다. (네이티브 화면 회전에 의존하지 않는 방식) */
.editor.landscape {
  position: fixed;
  inset: 0;
  z-index: 200;
  width: 100vh;
  height: 100vw;
  max-width: none;
  margin: 0;
  transform-origin: top left;
  transform: rotate(90deg) translateY(-100%);
  /* 90도 회전된 상태에서는 실제 세로 스와이프가 가로축 스크롤로 먹히는
     경우가 있어(브라우저마다 다름), 한쪽만 허용하면 스크롤이 아예 안 먹는
     문제가 있었다. 양쪽 다 열어서 어느 방향으로 스와이프해도 스크롤되게 한다. */
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  touch-action: pan-x pan-y;
  background: var(--bg, #f4f6fa);
  padding: 0.65rem 0.65rem calc(0.65rem + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

/* --- 상단 미니 툴바 --- */
.top-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.icon-btn {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: 1px solid #d8dee8;
  background: #fff;
  color: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.icon-btn:hover { background: #f1f5f9; }
.icon-btn.on {
  background: #0d6efd;
  border-color: #0d6efd;
  color: #fff;
}
.icon-btn.on:hover { background: #0b5ed7; }
.ocr-pill {
  flex: 1;
  min-width: 0;
  padding: 0.65rem 0.5rem;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #0d6efd;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ocr-pill:disabled { opacity: 0.6; cursor: not-allowed; }
.save-pill {
  flex: 1;
  min-width: 0;
  padding: 0.65rem 0.5rem;
  border-radius: 999px;
  border: none;
  background: #0a7a3e;
  color: #fff;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  white-space: nowrap;
}
.save-pill:disabled { opacity: 0.5; cursor: not-allowed; }

/* --- 상태 배너 --- */
.status-banner {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.status-banner.loading { background: #eff6ff; color: #0d6efd; }
.status-banner.error { background: #fef2f2; color: #c00; }
.status-banner.info { background: #ecfdf5; color: #0a7a3e; }
.ocr-status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
  animation: ocr-dot-pulse 1s ease-in-out infinite;
}
.ocr-status-dot.queued { background: #f5a623; }
@keyframes ocr-dot-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.1); }
}

/* --- 캔버스 --- */
.canvas-wrap {
  position: relative;
}
.canvas-empty {
  padding: 2.5rem 1rem;
  text-align: center;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px dashed #d8dee8;
}
.zoom-bar {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.25rem 0.4rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #d8dee8;
  box-shadow: 0 1px 4px rgba(0,0,0,0.12);
  transform-origin: top right;
  transition: opacity 0.2s, transform 0.2s;
}
.zoom-bar.dim {
  opacity: 0.55;
  transform: scale(0.85);
}
.zoom-bar.dim:hover,
.zoom-bar.dim:focus-within,
.zoom-bar.dim:active {
  opacity: 1;
  transform: scale(1);
}
.zoom-bar button {
  width: 1.6rem;
  height: 1.6rem;
  flex-shrink: 0;
  border-radius: 50%;
  border: none;
  background: #1e293b;
  color: #fff;
  font-weight: 800;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.zoom-bar button:disabled { opacity: 0.35; cursor: not-allowed; }
.zoom-val {
  min-width: 2.3rem;
  text-align: center;
  font-size: 0.7rem;
  font-weight: 700;
  color: #475569;
  flex-shrink: 0;
}
.pan-bar {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.25rem 0.4rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #d8dee8;
  box-shadow: 0 1px 4px rgba(0,0,0,0.12);
}
.pan-btn {
  width: 1.6rem;
  height: 1.6rem;
  flex-shrink: 0;
  border-radius: 50%;
  border: none;
  background: #0d6efd;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pan-btn:hover { background: #0b5ed7; }

.stage-frame {
  width: 100%;
  min-height: 360px;
  max-height: 70vh;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-x pan-y;
  background: #e8e8e8;
  border: 1px solid #ddd;
  border-radius: 10px;
}
.stage {
  position: relative;
  width: 100%;
  max-width: 640px;
  margin: 0 auto;
  border: none;
  background: #fff;
  user-select: none;
  touch-action: pan-x pan-y;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.stage.placing { cursor: crosshair; outline: 3px solid #ff2d55; outline-offset: -2px; box-shadow: 0 0 0 4px rgba(255,45,85,0.25); }
/* 코드 모드: 줄 핸들/몸통 드래그 비활성 - 아예 안 보이게 해서 오터치 여지 자체를 없앤다 */
.stage.mode-chord .handle { display: none; }
.stage.mode-chord .chord-line { cursor: default; }
/* 줄 모드: 칩 드래그 비활성 - 잡을 수 없다는 걸 커서로 표시 (더블탭 수정/삭제는 계속 가능) */
.stage.mode-line .chip { cursor: default; }
.score-img {
  display: block;
  width: 100%;
  height: auto;
  vertical-align: top;
  pointer-events: none;
  -webkit-user-drag: none;
  user-drag: none;
  -webkit-touch-callout: none;
}
.chord-line {
  position: absolute;
  box-sizing: border-box;
  background: rgba(13, 110, 253, 0.035);
  border: 1px solid rgba(13, 110, 253, 0.18);
  border-radius: 2px;
  z-index: 2;
  min-height: 18px;
  cursor: grab;
  touch-action: none;
}
.chord-line:hover {
  border-color: rgba(13, 110, 253, 0.5);
  background: rgba(13, 110, 253, 0.06);
}
.chord-line.active {
  border: 1.5px solid #0d6efd;
  background: rgba(13, 110, 253, 0.06);
}
.chord-line:active { cursor: grabbing; }
.handle {
  position: absolute;
  z-index: 4;
  background: transparent;
  opacity: 0;
  touch-action: none;
}
.chord-line:hover .handle,
.chord-line.active .handle {
  opacity: 1;
}
.handle.left { left: -9px; top: 0; bottom: 0; width: 18px; cursor: ew-resize; }
.handle.right { right: -9px; top: 0; bottom: 0; width: 18px; cursor: ew-resize; }
.handle.top { top: 0; left: 0; right: 0; height: 8px; cursor: ns-resize; }
.handle.bottom { bottom: 0; left: 0; right: 0; height: 8px; cursor: ns-resize; }
.handle.top::after,
.handle.bottom::after {
  content: '';
  position: absolute;
  left: 20%;
  right: 20%;
  height: 1.5px;
  background: #0d6efd;
  border-radius: 2px;
  opacity: 0.85;
}
.handle.top::after { top: 0; }
.handle.bottom::after { bottom: 0; }
.handle.left::after,
.handle.right::after {
  content: '';
  position: absolute;
  top: 20%;
  bottom: 20%;
  width: 2px;
  left: 50%;
  transform: translateX(-50%);
  background: #0d6efd;
  border-radius: 2px;
  opacity: 0.9;
}
.items-layer { position: absolute; inset: 0; pointer-events: none; }
.move-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 3;
  color: #3b82f6;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s;
}
.chord-line:hover .move-hint {
  opacity: 0.35;
}
.chip {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  font-weight: 800;
  color: #ff2d55;
  touch-action: none;
  text-shadow:
    0 0 2px #fff,
    0 0 3px #fff,
    1px 0 0 #fff,
    -1px 0 0 #fff,
    0 1px 0 #fff,
    0 -1px 0 #fff;
  background: transparent;
  border-radius: 4px;
  padding: 0.25rem 0.2rem 0.25rem 0.4rem;
  pointer-events: auto;
  cursor: grab;
  white-space: nowrap;
  max-width: 5rem;
}
.chip input { width: 2.6rem; font-size: inherit; font-weight: 700; border: 1px solid #333; border-radius: 2px; padding: 0 2px; }
.chip .x {
  border: none;
  background: transparent;
  color: #a00;
  cursor: pointer;
  font-size: 1.05em;
  padding: 0.2rem 0.35rem;
  opacity: 0.65;
}
.chip .edit-x {
  margin-left: 0.3rem;
  background: #fee2e2;
  border-radius: 5px;
  opacity: 1;
  font-weight: 800;
  padding: 0.2rem 0.5rem;
}
.chip .edit-x:hover {
  background: #fecaca;
}
.place-banner {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  background: rgba(13, 110, 253, 0.92);
  color: #fff;
  text-align: center;
  padding: 0.6rem;
  font-size: 0.92rem;
  font-weight: 600;
  z-index: 10;
}
.place-banner button {
  background: #fff;
  border: none;
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  margin-left: 8px;
  cursor: pointer;
  font-weight: 700;
}

/* --- 하단 고정 도구 --- */
.bottom-tools {
  position: sticky;
  bottom: 0;
  z-index: 20;
  background: #fff;
  border: 1px solid #e2e6ef;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 14px rgba(16, 24, 40, 0.08);
  overflow: hidden;
}
/* 가로모드에서는 .editor.landscape 자체에 transform(rotate)이 걸려있는데,
   position:sticky는 transform이 걸린 조상 안에서는 containing block 계산이
   깨져서 아예 렌더링되지 않는(사라지는) 문제가 있다. 가로모드에서는 sticky를
   포기하고 그냥 일반 흐름 요소로 두어 스크롤해서 도달하도록 한다. */
.editor.landscape .bottom-tools {
  position: static;
  border-radius: 12px;
  margin-top: 0.4rem;
}
.bt-tabs {
  display: flex;
}
.bt-tabs button {
  flex: 1;
  padding: 0.7rem 0.5rem;
  border: none;
  background: #f8fafc;
  color: #64748b;
  font-weight: 700;
  font-size: 0.92rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.bt-tabs button.on {
  background: #fff;
  color: #0d6efd;
  border-bottom-color: #0d6efd;
}
.bt-panel {
  padding: 0.85rem 0.9rem calc(0.85rem + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  max-height: 42vh;
  overflow-y: auto;
}

.roots { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.root { width: 2.5rem; height: 2.5rem; border-radius: 50%; border: 2px solid #ccc; background: #fff; font-weight: 800; font-size: 1rem; cursor: pointer; flex-shrink: 0; }
.root.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.variants { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.pchip { padding: 0.45rem 0.65rem; border: 1px solid #ccc; border-radius: 6px; background: #fff; font-weight: 600; font-size: 0.88rem; cursor: pointer; }
.pchip.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.custom-row { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.custom-row input { flex: 1; min-width: 100px; padding: 0.55rem 0.65rem; border: 1px solid #ccc; border-radius: 8px; font-size: 0.95rem; }
.act { padding: 0.55rem 0.85rem; border: none; border-radius: 8px; background: #1a1a2e; color: #fff; cursor: pointer; font-size: 0.88rem; font-weight: 600; }
.act.ghost { background: #fff; color: #1a1a2e; border: 1px solid #ccc; }

.tool-line-block {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: start;
  gap: 0.4rem 0.75rem;
}
.tlb-col {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}
.tlb-col.align-right {
  align-items: flex-end;
}
.tlb-controls {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}
.ml-label {
  font-size: 0.9rem;
  font-weight: 700;
  color: #334155;
}
.ml-switch {
  position: relative;
  width: 38px;
  height: 22px;
  border-radius: 999px;
  border: none;
  background: #cbd5e1;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}
.ml-switch.on {
  background: #0d6efd;
}
.ml-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
  transition: transform 0.15s;
}
.ml-switch.on .ml-knob {
  transform: translateX(16px);
}
.help-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}
.help-btn:hover {
  border-color: #93c5fd;
  color: #0d6efd;
}
.help-text {
  margin: 0;
  font-size: 0.78rem;
  color: #64748b;
  background: #f8fafc;
  border-radius: 6px;
  padding: 0.4rem 0.55rem;
}
.ms-count {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 700;
  color: #0d6efd;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.ms-clear {
  padding: 0.2rem 0.55rem;
  border: 1px solid #93c5fd;
  border-radius: 999px;
  background: #eff6ff;
  cursor: pointer;
  color: #0d6efd;
  font-size: 0.75rem;
  font-weight: 700;
}

.tool-divider {
  height: 1px;
  background: #e2e6ef;
  margin: 0.2rem 0;
}

.tool-row-label {
  font-weight: 700;
  font-size: 0.85rem;
  color: #475569;
}
.mini-btn {
  width: 2.5rem;
  height: 2.5rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-weight: 700;
  font-size: 1.2rem;
  color: #0f172a;
  line-height: 1;
}
.mini-btn:hover {
  background: #eff4ff;
  border-color: #93c5fd;
}
.tool-btns {
  display: flex;
  gap: 0.4rem;
}
.tool-btns button {
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-weight: 700;
  color: #0f172a;
}
.tool-btns button svg { display: block; }
.tool-btns button:hover:not(:disabled) {
  background: #eff4ff;
  border-color: #93c5fd;
}
.tool-btns button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

/* --- OCR 스캔 오버레이 --- */
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

/* --- 저장 모달 --- */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(15, 17, 26, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.modal-box {
  width: 100%;
  max-width: 380px;
  background: #fff;
  border-radius: 12px;
  padding: 1.25rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}
.modal-box h3 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.modal-hint { margin: 0 0 0.85rem; font-size: 0.85rem; color: #555; line-height: 1.5; }
.modal-input {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 1rem;
  box-sizing: border-box;
}
.modal-error { margin: 0.5rem 0 0; color: #c00; font-size: 0.85rem; }
.dup-block {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #fff8e6;
  border: 1px solid #e6c200;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.dup-label { margin: 0 0 0.1rem; font-size: 0.85rem; font-weight: 700; color: #7a5d00; }
.dup-item {
  text-align: left;
  padding: 0.5rem 0.7rem;
  border: 1px solid #d9b800;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 0.9rem;
}
.dup-item:hover { background: #fff3cd; }
.dup-newone {
  text-align: left;
  padding: 0.5rem 0.7rem;
  border: 1px dashed #999;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 0.85rem;
  color: #555;
}
.dup-item:disabled,
.dup-newone:disabled { opacity: 0.5; cursor: not-allowed; }
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
.modal-cancel {
  padding: 0.55rem 1rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}
.modal-save {
  padding: 0.55rem 1.1rem;
  border: none;
  border-radius: 6px;
  background: #0a7a3e;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.modal-cancel:disabled,
.modal-save:disabled { opacity: 0.5; cursor: not-allowed; }

</style>
