<script setup>
import { ref, computed, watch } from 'vue'

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
const ocrLoading = ref(false)
const confirming = ref(false)
const message = ref('')
const editKey = ref(null)
const editValue = ref('')
const activeLineId = ref(null)
const placeChord = ref('')
const customChord = ref('')
const stageRef = ref(null)
const drag = ref(null)
const chordFontPx = ref(13)
const selectedRoot = ref(null)
const uiMode = ref('layout') // 'layout' | 'refine'

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
    if (typeof it.t === 'number' && !Number.isNaN(it.t)) {
      return { ...it, t: Math.min(0.98, Math.max(0.02, it.t)) }
    }
    return { ...it, t: (i + 0.5) / n }
  })
}

function toLines(raw) {
  if (!Array.isArray(raw) || !raw.length) return []
  if (raw[0] && typeof raw[0] === 'object' && Array.isArray(raw[0].items)) {
    return raw.map((L, i) => ({
      id: L.id || `L${i}`,
      y: L.y ?? 0.1 + i * 0.08,
      xStart: L.xStart ?? 0.08,
      xEnd: L.xEnd ?? 0.92,
      height: L.height ?? 0.032,
      items: ensureItemT(
        (L.items || []).map((it, j) =>
          typeof it === 'string'
            ? { id: `i${i}_${j}`, chord: it }
            : { id: it.id || `i${i}_${j}`, chord: it.chord || '', t: it.t }
        )
      ),
    }))
  }
  const items = raw.map((c, j) =>
    typeof c === 'string'
      ? { id: `f${j}`, chord: c }
      : { id: c.id || `f${j}`, chord: c.chord || '', t: c.t }
  )
  return [{
    id: 'L0', y: 0.12, xStart: 0.08, xEnd: 0.92, height: 0.032,
    items: ensureItemT(items),
  }]
}

watch(() => props.sheet, (s) => {
  lines.value = toLines(s.chords)
  semitones.value = s.transpose_semitones || 0
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
  const h = Math.max(line.height || 0.02, 0.015)
  return {
    top: `${((line.y || 0) - h / 2) * 100}%`,
    left: `${(line.xStart || 0) * 100}%`,
    width: `${((line.xEnd || 0.9) - (line.xStart || 0)) * 100}%`,
    height: `${h * 100}%`,
  }
}

function chordLeftPct(line, item) {
  return `${(typeof item.t === 'number' ? item.t : 0.5) * 100}%`
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
  // 삽입 모드에서는 코드 이동 금지 (배치만)
  if (uiMode.value === 'refine' && (type === 'chord-x' || type.startsWith('line-'))) return
  e.preventDefault()
  e.stopPropagation()
  activeLineId.value = lineId
  drag.value = { type, lineId, itemId, moved: false }
  const onMove = (ev) => {
    const pos = normFromEvent(ev)
    if (!pos || !drag.value) return
    drag.value.moved = true
    const line = lines.value.find((L) => L.id === drag.value.lineId)
    if (!line) return
    const t = drag.value.type
    if (t === 'line-y') line.y = pos.y
    else if (t === 'line-h-top') {
      const bottom = line.y + (line.height || 0.032) / 2
      const top = Math.min(bottom - 0.012, pos.y)
      line.height = Math.max(0.012, bottom - top)
      line.y = (top + bottom) / 2
    } else if (t === 'line-h-bottom') {
      const top = line.y - (line.height || 0.032) / 2
      const bottom = Math.max(top + 0.012, pos.y)
      line.height = Math.max(0.012, bottom - top)
      line.y = (top + bottom) / 2
    } else if (t === 'line-left') line.xStart = Math.min(line.xEnd - 0.08, pos.x)
    else if (t === 'line-right') line.xEnd = Math.max(line.xStart + 0.08, pos.x)
    else if (t === 'chord-x') {
      const item = line.items.find((it) => it.id === drag.value.itemId)
      if (!item) return
      const span = line.xEnd - line.xStart
      if (span <= 0) return
      item.t = Math.min(0.98, Math.max(0.02, (pos.x - line.xStart) / span))
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

function onStageClick(e) {
  if (uiMode.value !== 'layout' || !placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  let best = null
  let bestDist = Infinity
  for (const L of lines.value) {
    const d = Math.abs((L.y || 0) - pos.y)
    if (d < bestDist) { bestDist = d; best = L }
  }
  const ch = placeChord.value
  if (best && bestDist < 0.045) {
    const span = best.xEnd - best.xStart
    const t = span > 0 ? Math.min(0.98, Math.max(0.02, (pos.x - best.xStart) / span)) : 0.5
    best.items.push({ id: 'n' + Date.now().toString(36), chord: ch, t })
    activeLineId.value = best.id
  } else {
    const line = {
      id: 'L' + Date.now().toString(36),
      y: pos.y, xStart: 0.08, xEnd: 0.92, height: 0.032,
      items: [{ id: 'n' + Date.now().toString(36), chord: ch, t: 0.5 }],
    }
    lines.value.push(line)
    activeLineId.value = line.id
  }
  message.value = `"${ch}" 삽입됨`
  saveLines()
}

function onLineClick(e, line) {
  e.stopPropagation()
  activeLineId.value = line.id
  if (uiMode.value !== 'layout' || !placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  const span = line.xEnd - line.xStart
  const t = span > 0 ? Math.min(0.98, Math.max(0.02, (pos.x - line.xStart) / span)) : 0.5
  line.items.push({ id: 'n' + Date.now().toString(36), chord: placeChord.value, t })
  message.value = `"${placeChord.value}" 줄에 삽입`
  saveLines()
}

function startEdit(lineId, item) {
  editKey.value = `${lineId}:${item.id}`
  // 조옮김 표시값이 아닌 원본(base) 코드 편집
  const L = lines.value.find(x => x.id === lineId)
  const it = L?.items?.find(x => x.id === item.id)
  editValue.value = it?.chord || item.chord || ''
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
function pickRoot(root) { selectedRoot.value = root; placeChord.value = '' }
function pickVariant(ch) {
  placeChord.value = ch
  uiMode.value = 'layout'
  message.value = `"${ch}" 선택 · 악보/줄 클릭으로 배치`
}
function pickCustom() {
  const ch = customChord.value.trim()
  if (!ch) return
  placeChord.value = ch
  uiMode.value = 'layout'
  message.value = `"${ch}" 선택 · 악보/줄 클릭으로 배치`
}
function clearPlace() { placeChord.value = ''; message.value = '' }
function setLayoutMode() {
  uiMode.value = 'layout'
  message.value = '배치: 코드 선택 후 클릭 삽입 · 드래그로 위치 조정'
}
function setRefineMode() {
  placeChord.value = ''
  uiMode.value = 'refine'
  message.value = '수정: 코드 이름 클릭 편집 · × 삭제 (삽입 없음)'
}
function addEmptyLine() {
  const line = {
    id: 'L' + Date.now().toString(36),
    y: 0.2 + lines.value.length * 0.05,
    xStart: 0.08, xEnd: 0.92, height: 0.032, items: [],
  }
  lines.value.push(line)
  activeLineId.value = line.id
}
function redistribute(line) {
  const L = lines.value.find(x => x.id === line.id)
  if (!L) return
  const n = Math.max(L.items.length, 1)
  L.items = L.items.map((it, i) => ({ ...it, t: (i + 0.5) / n }))
  saveLines()
}
function bumpFont(delta) {
  chordFontPx.value = Math.min(22, Math.max(9, chordFontPx.value + delta))
}

async function saveLines() {
  saving.value = true
  try {
    const res = await fetch(`/api/scores/${props.sheet.id}/update_chords/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chords: lines.value }),
    })
    if (!res.ok) throw new Error('저장 실패')
    emit('updated', await res.json())
  } catch (e) { message.value = e.message }
  finally { saving.value = false }
}

async function doTranspose(delta) {
  // 원본 lines(보정본)는 유지, semitones만 변경
  const target = semitones.value + delta
  saving.value = true
  try {
    const res = await fetch(`/api/scores/${props.sheet.id}/transpose/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ semitones: target }),
    })
    if (!res.ok) throw new Error('조옮김 실패')
    const data = await res.json()
    semitones.value = data.transpose_semitones ?? target
    emit('updated', data)
    message.value = `조옮김 ${target > 0 ? '+' : ''}${target} (원본 보정본 유지)`
  } catch (e) { message.value = e.message }
  finally { saving.value = false }
}

async function saveBase() {
  // 보정된 원본(위치·코드) 명시 저장, 조옮김 0으로
  saving.value = true
  try {
    const res = await fetch(`/api/scores/${props.sheet.id}/update_chords/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chords: lines.value }),
    })
    if (!res.ok) throw new Error('저장 실패')
    await fetch(`/api/scores/${props.sheet.id}/transpose/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ semitones: 0 }),
    })
    semitones.value = 0
    emit('updated', await res.json())
    message.value = '보정본 저장됨 · 다음에 이어서 작업 가능'
  } catch (e) { message.value = e.message }
  finally { saving.value = false }
}

async function runOcr() {
  ocrLoading.value = true
  message.value = ''
  try {
    const res = await fetch(`/api/scores/${props.sheet.id}/ocr/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apply_chords: true }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || 'OCR 실패')
    }
    emit('updated', await res.json())
    message.value = 'OCR 완료'
  } catch (e) { message.value = e.message }
  finally { ocrLoading.value = false }
}

async function confirmSheet() {
  confirming.value = true
  message.value = ''
  try {
    await saveLines()
    // 확정 시에는 화면에 보이는(조옮김 반영) 코드로 렌더
    const res = await fetch(`/api/scores/${props.sheet.id}/confirm/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chords: displayLines.value }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || '확정 실패')
    }
    const data = await res.json()
    emit('updated', data)
    message.value = '확정됨 · 조옮김 단계로 이동합니다'
    emit('next', data)
  } catch (e) { message.value = e.message }
  finally { confirming.value = false }
}

async function deleteThis() {
  const name = props.sheet.title || props.sheet.share_token || '이 악보'
  if (!confirm(`"${name}" 을(를) 삭제할까요?\n이미지 파일과 데이터가 모두 삭제됩니다.`)) return
  try {
    const res = await fetch(`/api/scores/${props.sheet.id}/`, { method: 'DELETE' })
    if (!res.ok && res.status !== 204) throw new Error('삭제 실패')
    emit('back')
  } catch (e) {
    message.value = e.message || '삭제 실패'
  }
}

const imageUrl = computed(() => {
  const u = props.sheet.optimized_image
  if (!u) return ''
  return u + (u.includes('?') ? '&' : '?') + 't=' + (props.sheet.updated_at || Date.now())
})
const resultUrl = computed(() => {
  const u = props.sheet.result_image
  if (!u) return ''
  return u + (u.includes('?') ? '&' : '?') + 't=' + (props.sheet.updated_at || Date.now())
})
</script>

<template>
  <div class="editor">
    <div class="top-actions">
      <button class="back" @click="emit('back')">← 목록</button>
      <button type="button" class="delete-sheet" @click="deleteThis">악보 삭제</button>
    </div>
    <h2>{{ sheet.title || '제목 없음' }}</h2>
    <p class="meta">공유: <code>{{ sheet.share_token }}</code> · 조옮김: {{ semitones > 0 ? '+' : '' }}{{ semitones }}</p>
    <p class="hint">
      <b>1. 배치</b>: 코드 선택→클릭 삽입 · 드래그로 위치/줄 크기 조정<br />
      <b>2. 수정</b>: 이름 편집·삭제만 (실수 삽입 방지) · 보정본 저장 후 조옮김
    </p>
    <div class="mode-bar">
      <button type="button" :class="{ on: uiMode === 'layout' }" @click="setLayoutMode">1. 배치</button>
      <button type="button" :class="{ on: uiMode === 'refine' }" @click="setRefineMode">2. 수정</button>
      <button type="button" class="save-base" @click="saveBase" :disabled="saving">보정본 저장</button>
    </div>
    <div class="size-bar">
      <span>코드 크기</span>
      <button type="button" @click="bumpFont(-1)">A-</button>
      <span class="size-val">{{ chordFontPx }}px</span>
      <button type="button" @click="bumpFont(1)">A+</button>
    </div>
    <div ref="stageRef" class="stage" :class="{ placing: uiMode === 'layout' && !!placeChord }" v-if="sheet.optimized_image" @click="onStageClick">
      <img :src="imageUrl" class="score-img" draggable="false" alt="악보" />
      <div v-for="line in displayLines" :key="line.id" class="chord-line" :class="{ active: activeLineId === line.id }" :style="lineStyle(line)" @click="onLineClick($event, line)">
        <div class="handle left" @pointerdown="startDrag($event, 'line-left', line.id)" />
        <div class="handle right" @pointerdown="startDrag($event, 'line-right', line.id)" />
        <div class="handle top" @pointerdown="startDrag($event, 'line-h-top', line.id)" />
        <div class="handle bottom" @pointerdown="startDrag($event, 'line-h-bottom', line.id)" />
        <button class="line-move" title="세로 이동" @pointerdown="startDrag($event, 'line-y', line.id)" @click.stop>⋮⋮</button>
        <div class="items-layer">
          <div v-for="item in line.items" :key="item.id" class="chip" :style="{ left: chordLeftPct(line, item), fontSize: chordFontPx + 'px' }" @pointerdown="startDrag($event, 'chord-x', line.id, item.id)">
            <template v-if="editKey === line.id + ':' + item.id">
              <input v-model="editValue" @keyup.enter="confirmEdit(line.id, item)" @blur="confirmEdit(line.id, item)" @click.stop @pointerdown.stop />
            </template>
            <template v-else>
              <span @click.stop="startEdit(line.id, item)">{{ item.chord }}</span>
              <button class="x" @click.stop="removeItem(line, item.id)" @pointerdown.stop>×</button>
            </template>
          </div>
        </div>
        <button type="button" class="redistribute" title="균등 재배치" @click.stop="redistribute(line)">⇄</button>
      </div>
      <div v-if="placeChord" class="place-banner" @click.stop>
        「{{ placeChord }}」 배치 모드 — 악보·줄을 클릭 ·
        <button type="button" @click="clearPlace">취소</button>
      </div>
    </div>
    <section class="palette" v-if="uiMode === 'layout'">
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
    <div class="toolbar">
      <button class="ocr" :disabled="ocrLoading" @click="runOcr">{{ ocrLoading ? 'OCR 중…' : 'PaddleOCR 실행' }}</button>
    </div>
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
    <p v-if="message" class="msg">{{ message }}</p>
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
.delete-sheet {
  border: 1px solid #f0c0c0; background: #fff5f5; color: #c00;
  border-radius: 6px; padding: 0.35rem 0.7rem; cursor: pointer; font-size: 0.85rem;
}
.delete-sheet:hover { background: #c00; color: #fff; }
.meta { font-size: 0.85rem; color: #666; }
.hint { font-size: 0.85rem; color: #444; background: #f5f7fa; padding: 0.6rem 0.8rem; border-radius: 6px; line-height: 1.5; }
.mode-bar { display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center; }
.mode-bar button { padding: 0.4rem 0.75rem; border: 1px solid #ccc; border-radius: 6px; background: #fff; cursor: pointer; font-weight: 600; }
.mode-bar button.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
.mode-bar .save-base { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.size-bar { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }
.size-bar button { padding: 0.25rem 0.55rem; border: 1px solid #ccc; border-radius: 5px; background: #fff; cursor: pointer; font-weight: 700; }
.size-val { min-width: 2.5rem; text-align: center; font-weight: 600; }
.stage { position: relative; width: 100%; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; background: #fff; user-select: none; touch-action: none; }
.stage.placing { cursor: crosshair; outline: 2px solid #0d6efd; }
.score-img { display: block; width: 100%; height: auto; pointer-events: none; }
.chord-line { position: absolute; box-sizing: border-box; background: rgba(255, 250, 180, 0.32); border: 1px dashed rgba(180, 150, 0, 0.5); border-radius: 4px; z-index: 2; min-height: 18px; }
.chord-line.active { background: rgba(255, 235, 100, 0.4); border-color: #0d6efd; border-style: solid; }
.handle { position: absolute; z-index: 4; background: rgba(13, 110, 253, 0.35); }
.handle.left { left: -3px; top: 0; bottom: 0; width: 6px; cursor: ew-resize; }
.handle.right { right: -3px; top: 0; bottom: 0; width: 6px; cursor: ew-resize; }
.handle.top { top: -3px; left: 0; right: 0; height: 6px; cursor: ns-resize; }
.handle.bottom { bottom: -3px; left: 0; right: 0; height: 6px; cursor: ns-resize; }
.line-move { position: absolute; left: 4px; top: 50%; transform: translateY(-50%); border: none; background: rgba(0,0,0,0.1); border-radius: 3px; padding: 2px 3px; font-size: 9px; cursor: grab; z-index: 3; color: #444; }
.items-layer { position: absolute; inset: 0; pointer-events: none; }
.chip { position: absolute; top: 50%; transform: translate(-50%, -50%); display: flex; align-items: center; font-weight: 700; color: #1a1a2e; background: rgba(255, 255, 255, 0.55); border-radius: 3px; padding: 0 2px 0 4px; pointer-events: auto; cursor: grab; white-space: nowrap; max-width: 5rem; }
.chip input { width: 2.6rem; font-size: inherit; font-weight: 700; border: 1px solid #333; border-radius: 2px; padding: 0 2px; }
.chip .x { border: none; background: transparent; color: #a00; cursor: pointer; font-size: 0.9em; padding: 0 1px; opacity: 0.55; }
.redistribute { position: absolute; right: 4px; top: 50%; transform: translateY(-50%); border: none; background: rgba(0,0,0,0.08); border-radius: 3px; font-size: 11px; padding: 1px 4px; cursor: pointer; z-index: 3; }
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
.toolbar .ocr { padding: 0.55rem 1rem; background: #0d6efd; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
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
