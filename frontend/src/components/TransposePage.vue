<script setup>
import { ref, computed, watch } from 'vue'
import { apiFetch } from '@/api/api.js'

const props = defineProps({ sheet: { type: Object, required: true } })
const emit = defineEmits(['updated', 'back', 'edit'])

const NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const NOTE_IDX = Object.fromEntries(NOTES.map((n, i) => [n, i]))
NOTE_IDX['Db'] = 1
NOTE_IDX['Eb'] = 3
NOTE_IDX['Gb'] = 6
NOTE_IDX['Ab'] = 8
NOTE_IDX['Bb'] = 10

const lastSheetId = ref(null)

function normalizeSemitones(n) {
  n = (((Number(n) || 0) % 12) + 12) % 12
  if (n > 6) n -= 12
  return n
}

function transposeChordName(name, semitones) {
  if (!name || !semitones) return name
  const s = String(name).trim()
  if (s.includes('/')) {
    return s.split('/').map((p) => transposeChordName(p, semitones)).join('/')
  }
  const m = s.match(/^([A-Ga-g])([#b]?)(.*)$/)
  if (!m) return s
  const root = m[1].toUpperCase() + (m[2] || '')
  const idx = NOTE_IDX[root]
  if (idx === undefined) return s
  return NOTES[(idx + (semitones % 12) + 12) % 12] + (m[3] || '')
}

function firstChordName(chords) {
  if (!Array.isArray(chords) || !chords.length) return 'C'
  const first = chords[0]
  if (first?.items?.length) return first.items[0].chord || 'C'
  if (typeof first === 'string') return first
  return first?.chord || 'C'
}

function rootOnly(name) {
  const s = String(name || 'C').trim()
  const m = s.match(/^([A-Ga-g][#b]?)/)
  return m ? m[1].toUpperCase().replace('B#', 'C').replace('E#', 'F') : 'C'
}

function keyLabel(chords, semitones) {
  const base = firstChordName(chords)
  const transposed = transposeChordName(base, semitones || 0)
  return `${rootOnly(transposed)}코드`
}

const semitones = ref(0)
const rendering = ref(false)
const imageLoading = ref(false)
const message = ref('')
const deleting = ref(false)
const renderFailed = ref(false)
/** data: URL 또는 빈 문자열 — 서버에 저장하지 않음 */
const previewUrl = ref('')
const currentLabel = ref('')

// 가운데 "원곡(코드)" 버튼 라벨 - 항상 원본(0반음) 기준, 현재 위치와 무관하게 고정
const originLabel = computed(() => `원곡(${keyLabel(props.sheet.chords || [], 0)})`)

// "(C→E)" 부분만 - 0일 땐 빈 문자열 (원곡 버튼이 이미 원곡임을 보여주므로)
const transposeLabel = computed(() => {
  if (!semitones.value) return ''
  const base = firstChordName(props.sheet.chords || [])
  const fromRoot = rootOnly(base)
  const toRoot = rootOnly(transposeChordName(base, semitones.value))
  return `(${fromRoot}→${toRoot})`
})

watch(
  () => props.sheet,
  (s) => {
    if (!s) return
    const isNew = lastSheetId.value !== s.id
    lastSheetId.value = s.id
    if (isNew) {
      semitones.value = 0
      previewUrl.value = ''
      message.value = ''
      currentLabel.value = keyLabel(s.chords || [], 0)
      // 진입 시 원본(0) 자동 렌더
      renderPreview()
    }
  },
  { immediate: true },
)

const previewChords = computed(() => {
  const delta = semitones.value || 0
  const lines = Array.isArray(props.sheet.chords) ? props.sheet.chords : []
  if (!lines.length) return []
  if (lines[0]?.items) {
    return lines.flatMap((L) =>
      (L.items || []).map((it) => transposeChordName(it.chord, delta)),
    )
  }
  return lines.map((c) => transposeChordName(typeof c === 'string' ? c : c.chord, delta))
})

// ±1/±2 버튼: 기존처럼 현재 위치에서 누적 이동
function doTranspose(delta) {
  semitones.value = normalizeSemitones(semitones.value + delta)
  currentLabel.value = keyLabel(props.sheet.chords || [], semitones.value)
  message.value = ''
  renderPreview()
}

// 가운데 "원곡(코드)" 버튼: 현재 위치와 무관하게 항상 0(원본 키)으로 바로 이동
function goToOrigin() {
  if (semitones.value === 0 && previewUrl.value) return // 이미 원곡이면 재렌더 생략
  semitones.value = 0
  currentLabel.value = keyLabel(props.sheet.chords || [], 0)
  message.value = ''
  renderPreview()
}

async function renderPreview() {
  const id = props.sheet.id
  if (!id) {
    message.value = '곡 ID 없음'
    return
  }
  rendering.value = true
  imageLoading.value = true
  renderFailed.value = false
  try {
    const res = await apiFetch(`/api/songs/${id}/render_variant/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semitones: semitones.value,
        chords: props.sheet.chords || [],
        label: keyLabel(props.sheet.chords || [], semitones.value),
        chord_font_size: props.sheet.chord_font_size,
      }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || err.detail || '생성 실패')
    }
    const data = await res.json()
    const url =
      data.variant?.image ||
      (data.image_base64 ? `data:image/jpeg;base64,${data.image_base64}` : '')
    if (!url) throw new Error('이미지 데이터 없음')
    previewUrl.value = url
    currentLabel.value = data.label || keyLabel(props.sheet.chords || [], semitones.value)
    message.value = ''
  } catch (e) {
    message.value = e.message || '생성 실패'
    previewUrl.value = ''
    renderFailed.value = true
  } finally {
    rendering.value = false
  }
}

function onImageLoad() {
  imageLoading.value = false
}
function onImageError() {
  imageLoading.value = false
  message.value = '이미지를 표시하지 못했습니다'
}

async function downloadResult() {
  if (!previewUrl.value) {
    message.value = '먼저 악보를 생성하세요'
    return
  }
  try {
    let blob
    if (previewUrl.value.startsWith('data:')) {
      const res = await fetch(previewUrl.value)
      blob = await res.blob()
    } else {
      const res = await apiFetch(previewUrl.value)
      if (!res.ok) throw new Error('이미지 요청 실패')
      blob = await res.blob()
    }
    const title = (props.sheet.title || 'chordshift').replace(/[\\/:*?"<>|]/g, '_')
    const key = currentLabel.value || keyLabel(props.sheet.chords || [], semitones.value)
    const filename = `${title}_${key}.jpg`
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(objectUrl)
    message.value = `다운로드: ${filename}`
  } catch (e) {
    message.value = e.message || '다운로드 실패'
  }
}

// 곡 삭제: DB 레코드 + 원본/변형 이미지(스토리지)까지 백엔드에서 함께 정리됨
// (backend SongViewSet.destroy 참고)
async function deleteSong() {
  const id = props.sheet.id
  if (!id) return
  const title = props.sheet.title || '제목 없음'
  const ok = window.confirm(
    `"${title}" 곡을 삭제할까요?\n원본 이미지와 저장된 코드 데이터가 모두 삭제되며 되돌릴 수 없습니다.`,
  )
  if (!ok) return
  deleting.value = true
  message.value = ''
  try {
    const res = await apiFetch(`/api/songs/${id}/`, { method: 'DELETE' })
    if (!res.ok && res.status !== 204) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || err.detail || '삭제 실패')
    }
    emit('back')
  } catch (e) {
    message.value = e.message || '삭제 실패'
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="top">
      <button type="button" class="back-btn" @click="emit('back')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        목록
      </button>
    </div>

    <h2>{{ sheet.title || '제목 없음' }}</h2>

    <section class="transpose card">
      <h3>조옮김 <span class="transpose-label" v-if="transposeLabel">{{ transposeLabel }}</span></h3>
      <div class="btns">
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(-2)">−2</button>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(-1)">−1</button>
        <button
          type="button"
          class="step origin"
          :class="{ active: semitones === 0 }"
          :disabled="rendering"
          @click="goToOrigin"
        >{{ originLabel }}</button>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(1)">+1</button>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(2)">+2</button>
      </div>
      <div class="preview-chords" v-if="previewChords.length">
        <span v-for="(c, i) in previewChords.slice(0, 12)" :key="i" class="preview-chip">{{ c }}</span>
        <span v-if="previewChords.length > 12" class="preview-more">…</span>
      </div>
    </section>

    <div class="actions">
      <button type="button" class="btn-edit" @click="emit('edit')">수정</button>
      <button type="button" class="btn-delete" :disabled="deleting" @click="deleteSong">
        {{ deleting ? '삭제 중…' : '삭제' }}
      </button>
      <button type="button" class="btn-dl" :disabled="!previewUrl || rendering" @click="downloadResult">
        다운로드
      </button>
    </div>

    <p v-if="message" class="msg" :class="{ error: renderFailed }">
      {{ message }}
      <button v-if="renderFailed" type="button" class="retry-link" @click="renderPreview">다시 시도</button>
    </p>

    <div class="result card" v-if="previewUrl || rendering">
      <div class="img-wrap">
        <div v-if="imageLoading || rendering" class="img-loading">
          <div class="spinner" />
          <span>악보 준비 중…</span>
        </div>
        <img
          v-if="previewUrl"
          :src="previewUrl"
          alt="조옮김 결과"
          :class="{ dim: imageLoading }"
          @load="onImageLoad"
          @error="onImageError"
        />
      </div>
    </div>
    <p v-else class="muted empty">± 버튼으로 조옮김하면 결과가 여기에 표시됩니다.</p>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.top {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.4rem 0.75rem 0.4rem 0.6rem;
  border: 1px solid var(--border, #e2e6ef);
  border-radius: 999px;
  background: var(--surface, #fff);
  color: var(--text, #1a1d26);
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}
.back-btn svg {
  color: var(--text-muted, #5c6578);
  transition: transform 0.15s;
}
.back-btn:hover {
  border-color: #93c5fd;
  background: var(--primary-soft, #eff4ff);
}
.back-btn:hover svg {
  transform: translateX(-2px);
}
.back-btn:active {
  transform: scale(0.97);
}
h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
}
.card {
  background: #fff;
  border: 1px solid #e2e6ef;
  border-radius: 12px;
  padding: 1rem 1.1rem;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
}
.transpose h3 {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
}
.btns {
  display: flex;
  gap: 0.45rem;
  align-items: center;
  flex-wrap: wrap;
}
.step {
  padding: 0.5rem 0.85rem;
  background: #1e293b;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}
.step:disabled {
  opacity: 0.5;
}
.step.origin {
  background: #0f766e;
  font-weight: 700;
  white-space: nowrap;
}
.step.origin.active {
  background: #0a5c55;
  box-shadow: inset 0 0 0 2px #6ee7d5;
}
.transpose-label {
  font-size: 0.85rem;
  font-weight: 700;
  color: #0f766e;
}
.preview-chords {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.55rem 0 0;
}
.preview-chip {
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  background: #eef2ff;
  color: #818cf8;
  font-size: 0.82rem;
  font-weight: 600;
}
.preview-more {
  align-self: center;
  color: #cbd5e1;
  font-size: 0.82rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.btn-edit,
.btn-delete {
  padding: 0.7rem 1.1rem;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
  background: #fff;
}
.btn-edit {
  border: 1px solid #cbd5e1;
  color: #1e293b;
}
.btn-edit:hover {
  background: #f1f5f9;
}
.btn-delete {
  border: 1px solid #fca5a5;
  color: #dc2626;
}
.btn-delete:hover {
  background: #fef2f2;
}
.btn-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-dl {
  padding: 0.7rem 1.1rem;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
}
.btn-dl:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.msg {
  margin: 0;
  color: #0f766e;
  font-weight: 600;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.msg.error {
  color: #c00;
}
.retry-link {
  background: none;
  border: none;
  padding: 0;
  color: #2563eb;
  font-weight: 700;
  font-size: 0.85rem;
  cursor: pointer;
  text-decoration: underline;
}
.result img {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  display: block;
}
.result img.dim {
  opacity: 0.35;
}
.img-wrap {
  position: relative;
  min-height: 100px;
}
.img-loading {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 8px;
  color: #0f766e;
  font-weight: 600;
  font-size: 0.9rem;
}
.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #ccfbf1;
  border-top-color: #0f766e;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.muted {
  color: #94a3b8;
}
.empty {
  margin: 0;
  font-size: 0.9rem;
}
</style>
