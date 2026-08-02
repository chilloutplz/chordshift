<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { API_BASE } from '@/api/api.js'

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
const editKey = ref(null)
const editValue = ref('')
const activeLineId = ref(null)
const placeChord = ref('')
const customChord = ref('')
const stageRef = ref(null)
const drag = ref(null)
const chordFontPx = ref(13)
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
  // 코드 선택(삽입) 중에는 드래그보다 클릭 삽입 우선
  if (placeChord.value) return
  e.preventDefault()
  e.stopPropagation()
  activeLineId.value = lineId
  const line0 = lines.value.find((L) => L.id === lineId)
  const pos0 = normFromEvent(e)
  drag.value = {
    type,
    lineId,
    itemId,
    moved: false,
    // 코드줄 전체 이동용 시작 스냅샷
    startX: pos0?.x ?? 0,
    startY: pos0?.y ?? 0,
    origY: line0?.y ?? 0,
    origXStart: line0?.xStart ?? 0.08,
    origXEnd: line0?.xEnd ?? 0.92,
  }
  const onMove = (ev) => {
    const pos = normFromEvent(ev)
    if (!pos || !drag.value) return
    drag.value.moved = true
    const line = lines.value.find((L) => L.id === drag.value.lineId)
    if (!line) return
    const t = drag.value.type
    if (t === 'line-y' || t === 'line-body') {
      // 코드줄 전체 이동 (안의 코드 t는 상대값이므로 함께 이동)
      const dx = pos.x - drag.value.startX
      const dy = pos.y - drag.value.startY
      const span = drag.value.origXEnd - drag.value.origXStart
      let ns = drag.value.origXStart + dx
      let ne = drag.value.origXEnd + dx
      if (ns < 0.01) {
        ne = 0.01 + span
        ns = 0.01
      }
      if (ne > 0.99) {
        ns = 0.99 - span
        ne = 0.99
      }
      line.xStart = ns
      line.xEnd = ne
      line.y = Math.min(0.98, Math.max(0.02, drag.value.origY + dy))
    } else if (t === 'line-h-top') {
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

  // 기존 코드줄이 있으면 가장 가까운 줄에만 삽입 (새 줄 자동 생성 안 함)
  if (lines.value.length) {
    let best = null
    let bestDist = Infinity
    for (const L of lines.value) {
      const d = Math.abs((L.y || 0) - pos.y)
      if (d < bestDist) { bestDist = d; best = L }
    }
    // active 줄이 있으면 우선
    const active = lines.value.find((L) => L.id === activeLineId.value)
    const target = active || best
    if (!target) return
    const span = (target.xEnd - target.xStart) || 0.8
    const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - target.xStart) / span))
    target.items.push({ id: 'n' + Date.now().toString(36), chord: ch, t: tNorm })
    activeLineId.value = target.id
    message.value = `"${ch}" 코드줄에 삽입`
    saveLines()
    return
  }

  // 코드줄이 하나도 없을 때만 새 줄 생성
  const line = {
    id: 'L' + Date.now().toString(36),
    y: pos.y, xStart: 0.08, xEnd: 0.92, height: 0.032,
    items: [{ id: 'n' + Date.now().toString(36), chord: ch, t: 0.5 }],
  }
  lines.value.push(line)
  activeLineId.value = line.id
  message.value = `"${ch}" 새 코드줄에 삽입`
  saveLines()
}

function onLineClick(e, line) {
  e.stopPropagation()
  // displayLines는 복사본이므로 반드시 lines 원본을 수정
  const L = lines.value.find((x) => x.id === line.id) || line
  activeLineId.value = L.id
  if (!placeChord.value) return
  const pos = normFromEvent(e)
  if (!pos) return
  if (!Array.isArray(L.items)) L.items = []
  const span = (L.xEnd - L.xStart) || 0.8
  const tNorm = Math.min(0.98, Math.max(0.02, (pos.x - L.xStart) / span))
  L.items.push({ id: 'n' + Date.now().toString(36), chord: placeChord.value, t: tNorm })
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
    if (isTemp()) {
      res = await fetch(`${API_BASE}/api/temp/${sheetId()}/chords/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chords: lines.value }),
      })
    } else {
      res = await fetch(`${API_BASE}/api/songs/${props.sheet.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chords: lines.value }),
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
        force_new: forceNew,
      }
      if (mergeSongId) body.merge_song_id = mergeSongId
      const res = await fetch(`${API_BASE}/api/songs/from-temp/`, {
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
      const res = await fetch(`${API_BASE}/api/songs/${props.sheet.id}/`, {
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
  message.value = '확정 처리 중…'
  try {
    await saveLines()

    let song = { ...props.sheet }

    // 임시 업로드면 확정과 함께 DB 등록 (보정본 저장)
    if (isTemp()) {
      const body = {
        temp_id: sheetId(),
        title: props.sheet.title || '',
        chords: lines.value,
        force_new: true,
      }
      let res = await fetch(`${API_BASE}/api/songs/from-temp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      let data = await res.json().catch(() => ({}))
      if (res.status === 409 && data.error === 'duplicate_title') {
        // 확정 흐름에서는 새 곡으로 강제 저장
        body.force_new = true
        res = await fetch(`${API_BASE}/api/songs/from-temp/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        data = await res.json().catch(() => ({}))
      }
      if (!res.ok) {
        // Song API 미적용 환경 → 구 API 시도하지 않고 안내
        throw new Error(data.error || data.message || '보정본 저장 실패. migrate / 서버 재시작을 확인하세요.')
      }
      song = { ...data, is_temp: false }
      emit('updated', song)
    }

    const songId = song.id
    if (!songId) throw new Error('곡 ID가 없습니다')

    // 수정본 이미지 렌더 (Song API)
    let res = await fetch(`${API_BASE}/api/songs/${songId}/render_variant/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semitones: 0,
        chords: lines.value,
        label: keyLabelFromLines(lines.value, 0),
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || '확정 실패')
    }
    const data = await res.json()
    song = data.song || data
    emit('updated', song)
    message.value = '확정됨 · 조옮김 단계로 이동'
    emit('next', song)
  } catch (e) {
    message.value = e.message || '확정 실패'
  } finally {
    confirming.value = false
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
    </div>
    <h2>{{ sheet.title || '제목 없음' }}</h2>
    <div v-if="dupCandidates.length" class="dup-box">
      <p>같은 제목의 곡이 있습니다. 선택하세요:</p>
      <button v-for="c in dupCandidates" :key="c.id" type="button" @click="saveBase(c.id)">
        「{{ c.title }}」에 합치기 (코드 {{ (c.variants || []).length }})
      </button>
      <button type="button" class="force" @click="saveBase(null, true)">새 곡으로 저장</button>
    </div>
    <div class="size-bar">
      <span>코드 크기</span>
      <button type="button" @click="bumpFont(-1)">A-</button>
      <span class="size-val">{{ chordFontPx }}px</span>
      <button type="button" @click="bumpFont(1)">A+</button>
    </div>
    <div class="stage-frame" v-if="sheet.optimized_image">
    <div ref="stageRef" class="stage" :class="{ placing: !!placeChord }" @click="onStageClick">
      <img :src="imageUrl" class="score-img" draggable="false" alt="악보" />
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
              <input v-model="editValue" @keyup.enter="confirmEdit(line.id, item)" @blur="confirmEdit(line.id, item)" @click.stop @pointerdown.stop @keydown.esc.stop="editKey = null" />
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
.meta { font-size: 0.85rem; color: #666; }
.hint { font-size: 0.85rem; color: #444; background: #f5f7fa; padding: 0.6rem 0.8rem; border-radius: 6px; line-height: 1.5; }
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
.stage.placing { cursor: crosshair; outline: 2px solid #0d6efd; outline-offset: -2px; }
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
.handle.left { left: -2px; top: 0; bottom: 0; width: 3px; cursor: ew-resize; }
.handle.right { right: -2px; top: 0; bottom: 0; width: 3px; cursor: ew-resize; }
.handle.top { top: -2px; left: 0; right: 0; height: 3px; cursor: ns-resize; }
.handle.bottom { bottom: -2px; left: 0; right: 0; height: 3px; cursor: ns-resize; }
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
