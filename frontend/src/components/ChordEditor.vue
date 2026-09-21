<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { API_BASE, apiFetch } from '@/api/api.js'
import { ROOTS, VARIANTS, EDIT_X0, EDIT_X1 } from '@/constants/chords.js'
import { useStageZoom } from '@/composables/chord-editor/useStageZoom.js'
import { useOcr } from '@/composables/chord-editor/useOcr.js'
import { useLinesData } from '@/composables/chord-editor/useLinesData.js'
import { useStageInteractions } from '@/composables/chord-editor/useStageInteractions.js'
import '@/assets/chord-editor.css'

const props = defineProps({ sheet: { type: Object, required: true } })
const emit = defineEmits(['updated', 'back', 'next'])

const lines = ref([])
const saving = ref(false)
const confirming = ref(false)
const message = ref('')
const dirty = ref(false)

const { ocrLoading, ocrError, ocrQueueInfo, ocrHasRun, runOcr: runOcrCore } = useOcr(props)
const { toLines, compactLinesForSave } = useLinesData()

function runOcr() {
  return runOcrCore(lines, toLines, askConfirm, (chords) => {
    lines.value = toLines(chords)
    dirty.value = true
    message.value = `OCR 완료: ${chords.length}개`
    emit('updated', { ...props.sheet, chords: lines.value })
  })
}

const appConfirm = ref(null)
function askConfirm(msg) {
  return new Promise((resolve) => { appConfirm.value = { message: msg, resolve } })
}
function answerConfirm(ok) {
  const cur = appConfirm.value; appConfirm.value = null
  if (cur) cur.resolve(!!ok)
}

function preferMobileLandscape() {
  if (typeof window === 'undefined') return false
  try {
    if (window.matchMedia('(pointer: coarse)').matches) return true
    if (window.matchMedia('(max-width: 900px)').matches) return true
  } catch (_) {}
  return false
}
const landscapeMode = ref(false)
const toolsCollapsed = ref(false)

const activeLineId = ref(null)
const placeChord = ref('')
const previewChord = ref('')
const customChord = ref('')
const stageRef = ref(null)
const stageFrameRef = ref(null)
const drag = ref(null)
const chordFontPx = ref(13)
const selectedRoot = ref(null)

function clearPlace() {
  placeChord.value = ''
  previewChord.value = ''
  customChord.value = ''
  selectedRoot.value = null
  message.value = ''
}
function releaseAddMode() { clearPlace() }

const selectedChordKeys = ref([])
const chordMultiMode = ref(false)
const selectedChordCount = computed(() => selectedChordKeys.value.length)
const hasChordSelection = computed(() => selectedChordKeys.value.length > 0)
const canReleaseAdd = computed(() => {
  if (selectedChordKeys.value.length) return false
  return !!(placeChord.value || (customChord.value || '').trim())
})
function chordKey(lineId, itemId) { return `${lineId}:${itemId}` }
function isChordSelected(lineId, itemId) { return selectedChordKeys.value.includes(chordKey(lineId, itemId)) }
function clearChordSelection() {
  selectedChordKeys.value = []
  customChord.value = ''
  previewChord.value = ''
}
function selectedChordItems() {
  const out = []
  for (const key of selectedChordKeys.value) {
    const [lineId, itemId] = key.split(':')
    const L = lines.value.find((x) => x.id === lineId)
    const it = L?.items?.find((x) => x.id === itemId)
    if (L && it) out.push({ line: L, item: it, key })
  }
  return out
}
function applyChordNameToSelection(name) {
  const ch = (name || '').trim()
  if (!ch || !selectedChordKeys.value.length) return false
  for (const { item } of selectedChordItems()) item.chord = ch
  dirty.value = true
  message.value = selectedChordKeys.value.length === 1 ? `"${ch}" 으로 수정` : `${selectedChordKeys.value.length}개 코드를 "${ch}" 으로 수정`
  return true
}
function toggleChordSelection(lineId, itemId) {
  const key = chordKey(lineId, itemId)
  if (chordMultiMode.value) {
    const idx = selectedChordKeys.value.indexOf(key)
    if (idx >= 0) selectedChordKeys.value = selectedChordKeys.value.filter((k) => k !== key)
    else selectedChordKeys.value = [...selectedChordKeys.value, key]
  } else {
    if (selectedChordKeys.value.length === 1 && selectedChordKeys.value[0] === key) {
      selectedChordKeys.value = []
    } else {
      selectedChordKeys.value = [key]
    }
  }
  placeChord.value = ''
  bottomTab.value = 'place'
  toolsCollapsed.value = false
  activeLineId.value = lineId
  if (selectedChordKeys.value.length === 1) {
    const k = selectedChordKeys.value[0]
    const [lid, iid] = k.split(':')
    const L = lines.value.find((x) => x.id === lid)
    const it = L?.items?.find((x) => x.id === iid)
    if (it?.chord) customChord.value = it.chord
  } else if (!selectedChordKeys.value.length) customChord.value = ''
}
function toggleChordMultiMode() {
  chordMultiMode.value = !chordMultiMode.value
  if (!chordMultiMode.value && selectedChordKeys.value.length > 1) {
    const keep = selectedChordKeys.value[0]
    selectedChordKeys.value = keep ? [keep] : []
  }
}
function deleteSelectedChords() {
  if (!selectedChordKeys.value.length) return
  const byLine = new Map()
  for (const key of selectedChordKeys.value) {
    const [lineId, itemId] = key.split(':')
    if (!byLine.has(lineId)) byLine.set(lineId, new Set())
    byLine.get(lineId).add(itemId)
  }
  for (const [lineId, ids] of byLine) {
    const L = lines.value.find((x) => x.id === lineId)
    if (!L) continue
    L.items = (L.items || []).filter((it) => !ids.has(it.id))
  }
  lines.value = lines.value.filter((L) => (L.items || []).length > 0)
  selectedChordKeys.value = []
  dirty.value = true
  message.value = '선택한 코드를 삭제했습니다'
}
function nudgeSelectedChords(dt) {
  if (!selectedChordKeys.value.length) return
  for (const { item } of selectedChordItems()) {
    const cur = typeof item.t === 'number' ? item.t : 0.5
    item.t = Math.min(0.98, Math.max(0.02, cur + dt))
  }
  dirty.value = true
}

const bottomTab = ref('adjust')
watch(bottomTab, (tab) => {
  if (tab !== 'place') {
    clearPlace()
    clearChordSelection()
    chordMultiMode.value = false
  }
})

const { zoom, ZOOM_MIN, ZOOM_MAX, PAN_STEP, zoomIn, zoomOut, panBy, stageStyle, onStagePointerDownCapture } = useStageZoom(stageFrameRef, drag)

const stageWidthPx = ref(640)
const DISPLAY_FONT_REF_W = 640
function measureStageWidth() {
  const el = stageRef.value
  if (!el) return
  const w = el.getBoundingClientRect().width
  if (w > 40) stageWidthPx.value = w
}
const displayFontPx = computed(() => {
  const base = chordFontPx.value * zoom.value
  const scale = Math.min(2.2, Math.max(0.5, stageWidthPx.value / DISPLAY_FONT_REF_W))
  const px = base * scale
  return Math.round(Math.min(48, Math.max(8, px)))
})
watch(landscapeMode, (on) => {
  if (!on) toolsCollapsed.value = false
  nextTick(() => measureStageWidth())
})
watch(zoom, () => nextTick(() => measureStageWidth()))

const selectedLineIds = ref([])
const lineMultiMode = ref(false)
const targetLineIds = computed(() => selectedLineIds.value)
function isLineSelected(id) { return selectedLineIds.value.includes(id) }
function toggleLineSelection(id) {
  activeLineId.value = id
  if (lineMultiMode.value) {
    const idx = selectedLineIds.value.indexOf(id)
    if (idx >= 0) selectedLineIds.value = selectedLineIds.value.filter((x) => x !== id)
    else selectedLineIds.value = [...selectedLineIds.value, id]
  } else {
    if (selectedLineIds.value.length === 1 && selectedLineIds.value[0] === id) selectedLineIds.value = []
    else selectedLineIds.value = [id]
  }
}
function toggleLineMultiMode() {
  lineMultiMode.value = !lineMultiMode.value
  if (!lineMultiMode.value && selectedLineIds.value.length > 1) {
    const keep = activeLineId.value && selectedLineIds.value.includes(activeLineId.value) ? activeLineId.value : selectedLineIds.value[0]
    selectedLineIds.value = keep ? [keep] : []
  }
}
function selectAllLines() {
  selectedLineIds.value = lines.value.map((L) => L.id)
  if (selectedLineIds.value.length) activeLineId.value = selectedLineIds.value[0]
}
function clearLineSelection() { selectedLineIds.value = [] }

const LINE_NUDGE_STEP = 0.006
const CHORD_NUDGE_STEP = 0.01
const LINE_EDGE_STEP = 0.004
const LINE_HEIGHT_MIN = 0.014
const LINE_HEIGHT_MAX = 0.08
const LINE_WIDTH_MIN = 0.06
function targetLines() {
  const ids = targetLineIds.value
  return lines.value.filter((L) => ids.includes(L.id))
}
function bumpLineTop(delta) {
  const targets = targetLines(); if (!targets.length) return
  for (const L of targets) {
    const h = L.height ?? 0.032, y = L.y ?? 0.1
    let top = y - h / 2, bottom = y + h / 2
    top = Math.min(bottom - LINE_HEIGHT_MIN, Math.max(0.005, top + delta))
    let newH = bottom - top
    if (newH > LINE_HEIGHT_MAX) { top = bottom - LINE_HEIGHT_MAX; newH = LINE_HEIGHT_MAX }
    L.height = newH; L.y = (top + bottom) / 2
  }
  dirty.value = true
}
function bumpLineBottom(delta) {
  const targets = targetLines(); if (!targets.length) return
  for (const L of targets) {
    const h = L.height ?? 0.032, y = L.y ?? 0.1
    const top = y - h / 2
    let bottom = y + h / 2
    bottom = Math.max(top + LINE_HEIGHT_MIN, Math.min(0.995, bottom + delta))
    let newH = bottom - top
    if (newH > LINE_HEIGHT_MAX) { bottom = top + LINE_HEIGHT_MAX; newH = LINE_HEIGHT_MAX }
    L.height = newH; L.y = (top + bottom) / 2
  }
  dirty.value = true
}
function bumpLineLeft(delta) {
  const targets = targetLines(); if (!targets.length) return
  for (const L of targets) {
    const x0 = L.xStart ?? EDIT_X0
    const x1 = L.xEnd ?? EDIT_X1
    const span = Math.max(0.001, x1 - x0)
    const absList = (L.items || []).map((it) => {
      const t = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
      return { it, abs: x0 + t * span }
    })
    let newStart = Math.max(0.005, Math.min(x1 - LINE_WIDTH_MIN, x0 + delta))
    const newSpan = Math.max(0.001, x1 - newStart)
    for (const { it, abs } of absList) {
      it.t = Math.min(0.98, Math.max(0.02, (abs - newStart) / newSpan))
    }
    L.xStart = newStart
  }
  dirty.value = true
}
function bumpLineRight(delta) {
  const targets = targetLines(); if (!targets.length) return
  for (const L of targets) {
    const x0 = L.xStart ?? EDIT_X0
    const x1 = L.xEnd ?? EDIT_X1
    const span = Math.max(0.001, x1 - x0)
    const absList = (L.items || []).map((it) => {
      const t = typeof it.t === 'number' && !Number.isNaN(it.t) ? it.t : 0.5
      return { it, abs: x0 + t * span }
    })
    let newEnd = Math.min(0.995, Math.max(x0 + LINE_WIDTH_MIN, x1 + delta))
    const newSpan = Math.max(0.001, newEnd - x0)
    for (const { it, abs } of absList) {
      it.t = Math.min(0.98, Math.max(0.02, (abs - x0) / newSpan))
    }
    L.xEnd = newEnd
  }
  dirty.value = true
}
function nudgeLine(dx, dy) {
  const targets = targetLines(); if (!targets.length) return
  if (dy) { for (const L of targets) L.y = Math.min(0.98, Math.max(0.02, (L.y ?? 0.1) + dy)); dirty.value = true }
}

const showSaveModal = ref(false)
const saveTitle = ref('')
const saveTitleError = ref('')
const forceNewOnDuplicate = ref(false)
const dupCandidates = ref([])
const titleInputRef = ref(null)
watch(showSaveModal, async (open) => {
  if (!open) return
  await nextTick(); titleInputRef.value?.focus(); titleInputRef.value?.select()
})
function openSaveModal() {
  saveTitle.value = (props.sheet.title || '').trim()
  saveTitleError.value = ''; forceNewOnDuplicate.value = false; dupCandidates.value = []; showSaveModal.value = true
}
function handleSaveClick() {
  if (isTemp()) openSaveModal()
  else { saveTitle.value = (props.sheet.title || '').trim(); confirmSheet() }
}
function closeSaveModal() { if (confirming.value) return; showSaveModal.value = false }
function submitSaveModal() {
  const t = saveTitle.value.trim()
  if (!t) { saveTitleError.value = '제목을 입력해주세요'; return }
  saveTitle.value = t; saveTitleError.value = ''; dupCandidates.value = []; forceNewOnDuplicate.value = false; confirmSheet()
}
function mergeIntoCandidate(c) { saveTitleError.value = ''; confirmSheet(c.id) }
function saveAsNewAnyway() { saveTitleError.value = ''; forceNewOnDuplicate.value = true; confirmSheet() }
function isTemp() { return !!(props.sheet.is_temp || props.sheet.temp_id) }
function sheetId() { return props.sheet.temp_id || props.sheet.id }

watch(() => props.sheet, (s, prev) => {
  const sid = s?.temp_id || s?.id, pid = prev?.temp_id || prev?.id
  if (dirty.value && prev && sid === pid) {
    if (s.chord_font_size) chordFontPx.value = s.chord_font_size
    else if (s.chordFontSize) chordFontPx.value = s.chordFontSize
    return
  }
  lines.value = toLines(s.chords)
  ocrHasRun.value = !!(s.chords?.length || s.ocr_raw_text)
  if (s.chord_font_size) chordFontPx.value = s.chord_font_size
  else if (s.chordFontSize) chordFontPx.value = s.chordFontSize
  dirty.value = false
}, { immediate: true })

const paletteChords = computed(() => {
  if (!selectedRoot.value) return []
  return VARIANTS[selectedRoot.value] || [selectedRoot.value]
})
function lineStyle(line) {
  const h = Math.max(line.height || 0.028, 0.015)
  const y = line.y ?? 0.1
  const x0 = typeof line.xStart === 'number' ? line.xStart : EDIT_X0
  const x1 = typeof line.xEnd === 'number' ? line.xEnd : EDIT_X1
  return {
    top: `${(y - h / 2) * 100}%`,
    left: `${x0 * 100}%`,
    width: `${Math.max(0.02, x1 - x0) * 100}%`,
    height: `${h * 100}%`,
  }
}

const { normFromEvent, startDrag, onStageClick, onLineClick, onChipClick } = useStageInteractions({
  lines, drag, activeLineId, placeChord, bottomTab, landscapeMode,
  stageRef, message, dirty,
  isChordSelected, toggleLineSelection, toggleChordSelection
})

function chordLeftPct(line, item) {
  if (typeof item.t !== 'number' || Number.isNaN(item.t)) return '50%'
  return `${Math.min(98, Math.max(2, item.t * 100))}%`
}
function pickRoot(root) {
  selectedRoot.value = root
  const list = VARIANTS[root] || [root]; const first = list[0] || root
  previewChord.value = first; customChord.value = first
  if (selectedChordKeys.value.length) { message.value = ''; return }
  placeChord.value = first; message.value = `"${first}" · 위치를 탭하세요`
}
function pickVariant(ch) {
  bottomTab.value = 'place'
  if (selectedChordKeys.value.length) { previewChord.value = ch; customChord.value = ch; applyChordNameToSelection(ch); return }
  if (placeChord.value === ch) { clearPlace(); return }
  clearChordSelection(); previewChord.value = ch; customChord.value = ch; placeChord.value = ch; message.value = `"${ch}" · 위치를 탭하세요`
}
function onCustomChordInput() {
  if (selectedChordKeys.value.length) return
  const ch = customChord.value.trim()
  if (ch) { placeChord.value = ch; previewChord.value = ch } else { placeChord.value = ''; previewChord.value = '' }
}
function applyFromInput() {
  const ch = customChord.value.trim()
  if (!ch || !selectedChordKeys.value.length) return
  previewChord.value = ch; applyChordNameToSelection(ch)
}
function onKeydownEsc(e) {
  if (e.key === 'Escape' || e.key === 'Esc') {
    if (placeChord.value) { clearPlace(); e.preventDefault() }
    else if (selectedChordKeys.value.length) { clearChordSelection(); e.preventDefault() }
  }
}
function handleBeforeUnload(e) { if (!dirty.value) return; e.preventDefault(); e.returnValue = '' }
onMounted(() => {
  window.addEventListener('keydown', onKeydownEsc)
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('resize', measureStageWidth)
  nextTick(() => measureStageWidth())
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydownEsc)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('resize', measureStageWidth)
})
async function handleBackClick() {
  if (dirty.value) { const ok = await askConfirm('저장하지 않은 변경사항이 있습니다. 그래도 나가시겠어요?'); if (!ok) return }
  emit('back')
}
function addEmptyLine() {
  const line = { id: 'L' + Date.now().toString(36), y: 0.2 + lines.value.length * 0.05, xStart: EDIT_X0, xEnd: EDIT_X1, height: 0.032, items: [] }
  lines.value.push(line); activeLineId.value = line.id; dirty.value = true
}
function bumpFont(delta) { chordFontPx.value = Math.min(28, Math.max(8, chordFontPx.value + delta)); dirty.value = true }
async function saveLines() {
  saving.value = true
  try {
    const chordsToSave = compactLinesForSave(lines.value)
    const payload = { chords: chordsToSave, chord_font_size: chordFontPx.value }
    let res
    if (isTemp()) res = await apiFetch(`/api/temp/${sheetId()}/chords/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    else res = await apiFetch(`/api/songs/${props.sheet.id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!res.ok) throw new Error('저장 실패')
    const data = await res.json().catch(() => ({}))
    lines.value = toLines(chordsToSave); dirty.value = false
    emit('updated', { ...props.sheet, ...data, chords: chordsToSave, chord_font_size: chordFontPx.value })
  } catch (e) { message.value = e.message } finally { saving.value = false }
}
async function confirmSheet(mergeId = null) {
  confirming.value = true; message.value = ''; const titleToSave = saveTitle.value.trim()
  try {
    const chordsToSave = compactLinesForSave(lines.value)
    await saveLines()
    let song = { ...props.sheet, title: titleToSave, chords: chordsToSave, chord_font_size: chordFontPx.value }
    if (isTemp()) {
      const body = { temp_id: sheetId(), title: titleToSave, chords: chordsToSave, chord_font_size: chordFontPx.value, force_new: forceNewOnDuplicate.value }
      if (mergeId) body.merge_song_id = mergeId
      const res = await apiFetch('/api/songs/from-temp/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      const data = await res.json().catch(() => ({}))
      if (res.status === 409 && data.error === 'duplicate_title') { dupCandidates.value = data.candidates || []; saveTitleError.value = data.message || `"${titleToSave}" 제목의 곡이 이미 있습니다.`; showSaveModal.value = true; return }
      if (!res.ok) throw new Error(data.error || data.message || '보정본 저장 실패.')
      song = { ...song, ...data, is_temp: false, temp_id: undefined, optimized_image: data.optimized_image || data.image_url || song.optimized_image, chords: chordsToSave, chord_font_size: chordFontPx.value }
      dirty.value = false; emit('updated', song)
    } else {
      const res = await apiFetch(`/api/songs/${props.sheet.id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chords: chordsToSave, chord_font_size: chordFontPx.value, title: titleToSave }) })
      if (!res.ok) throw new Error('저장 실패')
      const data = await res.json()
      song = { ...song, ...data, optimized_image: data.optimized_image || song.optimized_image, chords: chordsToSave, chord_font_size: chordFontPx.value }
      dirty.value = false; emit('updated', song)
    }
    if (!song.id) throw new Error('곡 ID가 없습니다')
    dupCandidates.value = []; forceNewOnDuplicate.value = false; showSaveModal.value = false; message.value = '저장됨 · 조옮김 단계로 이동'; emit('next', song)
  } catch (e) { message.value = e.message || '저장 실패' } finally { confirming.value = false }
}
const imageUrl = computed(() => {
  let u = props.sheet.optimized_image || props.sheet.image_url || props.sheet.original_image || ''
  if (!u) return ''
  if (typeof u === 'object' && u.url) u = u.url
  u = String(u)
  if (u.startsWith('data:')) return u
  if (u.startsWith('/')) u = `${API_BASE}${u}`
  if (u.includes('127.0.0.1') || u.includes('localhost')) u = u.replace('https://', 'http://')
  else if (u.startsWith('http://') && API_BASE.startsWith('https://')) u = u.replace('http://', 'https://')
  const bust = props.sheet.updated_at || Date.now()
  return u + (u.includes('?') ? '&' : '?') + 't=' + encodeURIComponent(bust)
})
const ocrStatusText = computed(() => {
  const q = ocrQueueInfo.value; const verb = ocrHasRun.value ? '재분석' : '분석'
  if (!q) return `OCR ${verb} 중...`
  if (q.status === 'queued') {
    const ahead = q.aheadCount ?? 0
    if (ahead <= 0) return '곧 시작합니다...'
    const wait = q.estimatedWaitSeconds
    return wait ? `앞에 ${ahead}명 대기 중 · 약 ${Math.round(wait)}초 예상` : `앞에 ${ahead}명 대기 중...`
  }
  return `악보를 ${verb}하는 중...`
})
const statusBanner = computed(() => {
  if (ocrLoading.value) return { text: ocrStatusText.value, kind: 'loading' }
  if (ocrError.value) return { text: ocrError.value, kind: 'error' }
  if (message.value) return { text: message.value, kind: 'info' }
  return null
})
</script>

<template>
  <div class="editor" :class="{ landscape: landscapeMode, 'tools-collapsed': toolsCollapsed }">
    <div class="top-bar">
      <button class="icon-btn" title="목록" aria-label="목록" @click="handleBackClick">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
      <button class="ocr-pill" @click="runOcr" :disabled="ocrLoading">{{ ocrLoading ? (ocrHasRun ? '재실행 중…' : 'OCR 중…') : (ocrHasRun ? 'OCR 재실행' : 'OCR 실행') }}</button>
      <button class="save-pill" :disabled="confirming || !lines.length" @click="handleSaveClick">{{ confirming ? '저장 중…' : '저장' }}</button>
      <button class="icon-btn" :class="{ on: landscapeMode }" title="가로 화면으로 보기" @click="landscapeMode = !landscapeMode">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="2" y="6" width="20" height="12" rx="2.5" stroke="currentColor" stroke-width="2" /><path d="M22 10v4" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></svg>
      </button>
    </div>
    <p v-if="statusBanner" class="status-banner" :class="statusBanner.kind">
      <span v-if="statusBanner.kind === 'loading'" class="ocr-status-dot" :class="{ queued: ocrQueueInfo?.status === 'queued' }" />{{ statusBanner.text }}
    </p>
    <div class="canvas-wrap" v-if="imageUrl">
      <div class="zoom-bar" :class="{ dim: zoom <= ZOOM_MIN }">
        <button type="button" :disabled="zoom <= ZOOM_MIN" @click="zoomOut">−</button>
        <span class="zoom-val">{{ Math.round(zoom * 100) }}%</span>
        <button type="button" :disabled="zoom >= ZOOM_MAX" @click="zoomIn">+</button>
      </div>
      <div class="pan-bar" v-if="zoom > ZOOM_MIN">
        <button type="button" class="pan-btn" @click="panBy(0, -PAN_STEP)">↑</button>
        <button type="button" class="pan-btn" @click="panBy(0, PAN_STEP)">↓</button>
        <button type="button" class="pan-btn" @click="panBy(-PAN_STEP, 0)">←</button>
        <button type="button" class="pan-btn" @click="panBy(PAN_STEP, 0)">→</button>
      </div>
      <div ref="stageFrameRef" class="stage-frame" @pointerdown.capture="onStagePointerDownCapture">
        <div ref="stageRef" class="stage" :class="{ placing: !!placeChord, 'mode-line': bottomTab === 'adjust', 'mode-chord': bottomTab === 'place' }" :style="stageStyle" @click="onStageClick">
          <img :src="imageUrl" class="score-img" draggable="false" @dragstart.prevent alt="악보" @load="measureStageWidth" />
          <div v-if="ocrLoading" class="ocr-scan-overlay"><div class="ocr-scan-info"><span class="ocr-scan-spinner" v-if="ocrQueueInfo?.status === 'queued'" /><span>{{ ocrStatusText }}</span></div><div class="ocr-scan-track"><div class="ocr-scan-line" /><div class="ocr-scan-glass"><svg viewBox="0 0 24 24" width="34" height="34" fill="none"><circle cx="10.5" cy="10.5" r="6.5" stroke="#0d6efd" stroke-width="2.4"/><line x1="15.3" y1="15.3" x2="21" y2="21" stroke="#0d6efd" stroke-width="2.4" stroke-linecap="round"/></svg></div></div></div>
          <div v-for="line in lines" :key="line.id" class="chord-line" :class="{ active: isLineSelected(line.id) }" :style="lineStyle(line)" @click="onLineClick($event, line)">
            <div class="items-layer">
              <div v-for="item in line.items" :key="item.id" class="chip" :class="{ selected: isChordSelected(line.id, item.id) }" :style="{ left: chordLeftPct(line, item), fontSize: displayFontPx + 'px' }" @pointerdown="startDrag($event, 'chord-x', line.id, item.id)" @click="onChipClick($event, line, item)"><span>{{ item.chord }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="canvas-empty">악보 이미지를 불러오는 중입니다…</div>
    <div class="bottom-tools">
      <div class="bt-tabs">
        <button type="button" :class="{ on: bottomTab === 'adjust' }" @click="bottomTab = 'adjust'; toolsCollapsed = false">Line</button>
        <button type="button" :class="{ on: bottomTab === 'place' }" @click="bottomTab = 'place'; toolsCollapsed = false">Chord</button>
        <button v-if="landscapeMode" type="button" class="bt-collapse" @click="toolsCollapsed = !toolsCollapsed">{{ toolsCollapsed ? '▲ 도구' : '▼ 접기' }}</button>
      </div>
      <div class="bt-panel" v-show="bottomTab === 'place'">
        <div class="chord-sel-bar">
          <div class="lt-pair">
            <button type="button" class="lt-btn" @click="bumpFont(-1)">A−</button>
            <button type="button" class="lt-btn" @click="bumpFont(1)">A+</button>
          </div>
          <button type="button" class="lt-btn" :class="{ on: chordMultiMode }" title="다중 선택" @click="toggleChordMultiMode">Mul.</button>
          <template v-if="hasChordSelection">
            <button type="button" class="act danger" @click="deleteSelectedChords">삭제</button>
            <div class="tool-btns">
              <button type="button" @click="nudgeSelectedChords(-CHORD_NUDGE_STEP)">←</button>
              <button type="button" @click="nudgeSelectedChords(CHORD_NUDGE_STEP)">→</button>
            </div>
          </template>
        </div>
        <div class="roots"><button v-for="r in ROOTS" :key="r" type="button" class="root" :class="{ on: selectedRoot === r }" @click="pickRoot(r)">{{ r }}</button></div>
        <div v-if="selectedRoot" class="variants"><button v-for="ch in paletteChords" :key="ch" type="button" class="pchip" :class="{ on: placeChord === ch || previewChord === ch }" @click="pickVariant(ch)">{{ ch }}</button></div>
        <div class="custom-row">
          <input v-model="customChord" :placeholder="hasChordSelection ? '이름 바꿔 적용' : (placeChord ? '위치를 탭하세요' : '코드 입력')" @input="onCustomChordInput" @keyup.enter="hasChordSelection ? applyFromInput() : null" />
          <button v-if="hasChordSelection" type="button" class="act" :disabled="!customChord.trim()" @click="applyFromInput">적용</button>
          <button v-else type="button" class="act ghost" :disabled="!canReleaseAdd" @click="releaseAddMode">해제</button>
        </div>
        <p v-if="hasChordSelection" class="ms-count">{{ selectedChordCount }}개 선택됨 <button type="button" class="ms-clear" @click="clearChordSelection">해제</button></p>
      </div>
      <div class="bt-panel bt-panel-adjust" v-show="bottomTab === 'adjust'">
        <div class="layout-tools">
          <div class="lt-grid">
            <div class="lt-row is-first">
                <button type="button" class="lt-btn" @click="addEmptyLine">Add</button>
                <span class="lt-sep" />
                <button type="button" class="lt-btn" :class="{ on: lineMultiMode }" @click="toggleLineMultiMode">Mul.</button>
                <button type="button" class="lt-btn" @click="selectAllLines">All</button>
                <span class="lt-sep" />
                <div class="lt-pair">
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="nudgeLine(0, -LINE_NUDGE_STEP)">↑</button>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="nudgeLine(0, LINE_NUDGE_STEP)">↓</button>
                </div>
            </div>
            <div class="lt-row">
                <div class="lt-edge">
                  <span class="lt-edge-lab">Top</span>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineTop(-LINE_EDGE_STEP)">↑</button>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineTop(LINE_EDGE_STEP)">↓</button>
                </div>
                <div class="lt-edge">
                  <span class="lt-edge-lab">Bottom</span>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineBottom(-LINE_EDGE_STEP)">↑</button>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineBottom(LINE_EDGE_STEP)">↓</button>
                </div>
            </div>
            <div class="lt-row">
                <div class="lt-edge">
                  <span class="lt-edge-lab">Left</span>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineLeft(-LINE_EDGE_STEP)">←</button>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineLeft(LINE_EDGE_STEP)">→</button>
                </div>
                <div class="lt-edge">
                  <span class="lt-edge-lab">Right</span>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineRight(-LINE_EDGE_STEP)">←</button>
                  <button type="button" class="lt-icon" :disabled="!targetLineIds.length" @click="bumpLineRight(LINE_EDGE_STEP)">→</button>
                </div>
            </div>
          </div>
        </div>
        <p v-if="selectedLineIds.length >= 1" class="ms-count">{{ selectedLineIds.length }}개 선택됨 <button type="button" class="ms-clear" @click="clearLineSelection">해제</button></p>
      </div>
    </div>
    <div v-if="appConfirm" class="modal-backdrop" @click.self="answerConfirm(false)"><div class="modal-box app-confirm-box"><h3>ChordShift</h3><p class="modal-hint app-confirm-msg">{{ appConfirm.message }}</p><div class="modal-actions"><button type="button" class="modal-cancel" @click="answerConfirm(false)">취소</button><button type="button" class="modal-save" @click="answerConfirm(true)">확인</button></div></div></div>
    <div v-if="showSaveModal" class="modal-backdrop" @click.self="closeSaveModal"><div class="modal-box"><h3>제목 입력</h3><p class="modal-hint">중복 저장을 막기 위해 정확한 곡 제목을 입력해주세요.</p><input ref="titleInputRef" v-model="saveTitle" type="text" class="modal-input" placeholder="곡 제목" :disabled="confirming" @keyup.enter="submitSaveModal" /><p v-if="saveTitleError" class="modal-error">{{ saveTitleError }}</p><div v-if="dupCandidates.length" class="dup-block"><p class="dup-label">기존 곡에 덮어쓸까요?</p><button v-for="c in dupCandidates" :key="c.id" type="button" class="dup-item" :disabled="confirming" @click="mergeIntoCandidate(c)">{{ c.title || '(제목 없음)' }} 덮어쓰기</button><button type="button" class="dup-newone" :disabled="confirming" @click="saveAsNewAnyway">아니요, 별개의 새 곡으로 저장</button></div><div class="modal-actions"><button type="button" class="modal-cancel" :disabled="confirming" @click="closeSaveModal">취소</button><button v-if="!dupCandidates.length" type="button" class="modal-save" :disabled="confirming" @click="submitSaveModal">{{ confirming ? '저장 중…' : '저장' }}</button><button v-else type="button" class="modal-save" :disabled="confirming" @click="submitSaveModal">{{ confirming ? '확인 중…' : '제목 다시 확인' }}</button></div></div></div>
  </div>
</template>

<style>
@import '@/assets/chord-editor.css';
</style>
