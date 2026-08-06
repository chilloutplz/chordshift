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
/** data: URL 또는 빈 문자열 — 서버에 저장하지 않음 */
const previewUrl = ref('')
const currentLabel = ref('')

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

function doTranspose(delta) {
  semitones.value = normalizeSemitones(semitones.value + delta)
  currentLabel.value = keyLabel(props.sheet.chords || [], semitones.value)
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
  message.value = '악보 생성 중…'
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
    message.value = currentLabel.value
  } catch (e) {
    message.value = e.message || '생성 실패'
    previewUrl.value = ''
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
</script>

<template>
  <div class="page">
    <div class="top">
      <button type="button" class="link" @click="emit('back')">← 목록</button>
      <button type="button" class="link" @click="emit('edit')">보정으로</button>
    </div>

    <h2>{{ sheet.title || '제목 없음' }}</h2>

    <section class="transpose card">
      <h3>조옮김</h3>
      <div class="btns">
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(-1)">−1</button>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(-2)">−2</button>
        <span class="cur">{{ semitones > 0 ? '+' : '' }}{{ semitones }}</span>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(1)">+1</button>
        <button type="button" class="step" :disabled="rendering" @click="doTranspose(2)">+2</button>
      </div>
      <p class="label-line" v-if="currentLabel">{{ currentLabel }}</p>
      <p class="preview" v-if="previewChords.length">
        미리보기: {{ previewChords.slice(0, 12).join(' · ') }}{{ previewChords.length > 12 ? ' …' : '' }}
      </p>
      <p class="hint muted">조옮김할 때마다 원본에서 바로 그립니다. 서버에 결과 이미지를 저장하지 않습니다.</p>
    </section>

    <div class="actions">
      <button type="button" class="btn-render" :disabled="rendering" @click="renderPreview">
        {{ rendering ? '생성 중…' : '다시 생성' }}
      </button>
      <button type="button" class="btn-dl" :disabled="!previewUrl || rendering" @click="downloadResult">
        다운로드
      </button>
    </div>

    <p v-if="message" class="msg">{{ message }}</p>

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
.link {
  background: none;
  border: none;
  cursor: pointer;
  color: #2563eb;
  font-weight: 600;
  padding: 0;
}
.link:hover {
  text-decoration: underline;
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
.cur {
  min-width: 2.75rem;
  text-align: center;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.label-line {
  margin: 0.6rem 0 0;
  font-weight: 700;
  color: #0f766e;
}
.preview {
  margin: 0.4rem 0 0;
  font-size: 0.88rem;
  color: #4b5563;
}
.hint {
  margin: 0.55rem 0 0;
  font-size: 0.8rem;
}
.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.btn-render {
  padding: 0.7rem 1.1rem;
  background: #0f766e;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
}
.btn-render:disabled {
  opacity: 0.5;
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
