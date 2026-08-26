<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
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

/** OCR/입력 슬래시 유사 문자 → '/' 정규화 (전각／, ∕, ⁄ 등) */
function normalizeSlash(s) {
  return String(s || '')
    .replace(/[／∕⁄｜|\\]/g, '/')
    .replace(/\s*\/\s*/g, '/')
    .trim()
}

function transposeChordName(name, semitones) {
  if (!name) return name
  // semitones === 0 이어도 슬래시 정규화는 해 둔다
  let s = normalizeSlash(name)
  if (!semitones) return s
  // 슬래시 코드: 앞(코드) / 뒤(베이스) 모두 같은 반음만큼 이동
  if (s.includes('/')) {
    return s
      .split('/')
      .map((p) => transposeChordName(p.trim(), semitones))
      .filter((p, i, arr) => p || i === 0) // 앞부분은 유지
      .join('/')
  }
  const m = s.match(/^([A-Ga-g])([#b]?)(.*)$/)
  if (!m) return s
  const root = m[1].toUpperCase() + (m[2] || '')
  const idx = NOTE_IDX[root]
  if (idx === undefined) return s
  const quality = m[3] || ''
  // quality 안에 슬래시가 남은 경우 안전망 (D + "/E")
  if (quality.includes('/')) {
    const qi = quality.indexOf('/')
    const qMain = quality.slice(0, qi)
    const qBass = quality.slice(qi + 1)
    const newRoot = NOTES[(idx + (semitones % 12) + 12) % 12]
    const bass = qBass ? transposeChordName(qBass, semitones) : ''
    return bass ? `${newRoot}${qMain}/${bass}` : `${newRoot}${qMain}`
  }
  return NOTES[(idx + (semitones % 12) + 12) % 12] + quality
}

/** 가장 위(y) · 왼쪽(t/x) 코드를 원곡 기준으로 사용. 배열 순서가 아님. */
function firstChordName(chords) {
  if (!Array.isArray(chords) || !chords.length) return 'C'
  // line 형식
  if (chords[0] && typeof chords[0] === 'object' && Array.isArray(chords[0].items)) {
    const lines = [...chords].sort((a, b) => (Number(a?.y) || 0) - (Number(b?.y) || 0))
    for (const L of lines) {
      const items = (L.items || []).filter((it) => (it?.chord || '').trim())
      if (!items.length) continue
      items.sort((a, b) => {
        const pa = a.t != null ? Number(a.t) : a.x != null ? Number(a.x) : 0.5
        const pb = b.t != null ? Number(b.t) : b.x != null ? Number(b.x) : 0.5
        return pa - pb
      })
      return items[0].chord || 'C'
    }
    return 'C'
  }
  const first = chords[0]
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
/** 악보만 전체 화면으로 보기 (+ 핀치 줌 / 드래그 팬) */
const fullscreen = ref(false)
const FS_ZOOM_MIN = 1
const FS_ZOOM_MAX = 4
const fsZoom = ref(1)
const fsPanX = ref(0)
const fsPanY = ref(0)
const fsImgStyle = computed(() => ({
  transform: `translate(${fsPanX.value}px, ${fsPanY.value}px) scale(${fsZoom.value})`,
  transformOrigin: 'center center',
  touchAction: 'none',
  cursor: fsZoom.value > 1 ? 'grab' : 'zoom-out',
}))

// 핀치/팬 상태 (오버레이 전용)
const fsPointers = new Map()
let fsPinchStartDist = 0
let fsPinchStartZoom = 1
let fsPanLast = null // { x, y } 단일 포인터 드래그
let fsDidGesture = false // 제스처 후 click으로 닫히지 않게

function fsPointerDist(pts) {
  return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
}

function clampFsZoom(z) {
  return Math.min(FS_ZOOM_MAX, Math.max(FS_ZOOM_MIN, +z.toFixed(3)))
}

function resetFsView() {
  fsZoom.value = 1
  fsPanX.value = 0
  fsPanY.value = 0
  fsPointers.clear()
  fsPinchStartDist = 0
  fsPanLast = null
  fsDidGesture = false
}

function openFullscreen() {
  if (!previewUrl.value) return
  resetFsView()
  fullscreen.value = true
  document.body.style.overflow = 'hidden'
}
function closeFullscreen() {
  fullscreen.value = false
  resetFsView()
  document.body.style.overflow = ''
}

function onFsPointerDown(e) {
  // 닫기 버튼은 무시
  if (e.target?.closest?.('.fs-close')) return
  e.currentTarget.setPointerCapture?.(e.pointerId)
  fsPointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (fsPointers.size === 2) {
    fsPinchStartDist = fsPointerDist([...fsPointers.values()])
    fsPinchStartZoom = fsZoom.value
    fsPanLast = null
  } else if (fsPointers.size === 1) {
    fsPanLast = { x: e.clientX, y: e.clientY }
  }
}

function onFsPointerMove(e) {
  if (!fsPointers.has(e.pointerId)) return
  fsPointers.set(e.pointerId, { x: e.clientX, y: e.clientY })

  if (fsPointers.size >= 2 && fsPinchStartDist > 0) {
    const dist = fsPointerDist([...fsPointers.values()])
    const next = clampFsZoom(fsPinchStartZoom * (dist / fsPinchStartDist))
    if (Math.abs(next - fsZoom.value) > 0.001) fsDidGesture = true
    fsZoom.value = next
    if (fsZoom.value <= 1.01) {
      fsZoom.value = 1
      fsPanX.value = 0
      fsPanY.value = 0
    }
    return
  }

  // 확대 상태에서 한 손가락 팬
  if (fsPointers.size === 1 && fsPanLast && fsZoom.value > 1.01) {
    const dx = e.clientX - fsPanLast.x
    const dy = e.clientY - fsPanLast.y
    if (Math.abs(dx) > 1 || Math.abs(dy) > 1) fsDidGesture = true
    fsPanX.value += dx
    fsPanY.value += dy
    fsPanLast = { x: e.clientX, y: e.clientY }
  }
}

function onFsPointerUp(e) {
  fsPointers.delete(e.pointerId)
  if (fsPointers.size < 2) fsPinchStartDist = 0
  if (fsPointers.size === 1) {
    const only = [...fsPointers.values()][0]
    fsPanLast = { x: only.x, y: only.y }
  } else {
    fsPanLast = null
  }
}

function onFsClick() {
  // 핀치/팬 직후 합성 click 은 무시
  if (fsDidGesture) {
    fsDidGesture = false
    return
  }
  // 1배율일 때만 탭으로 닫기 (확대 중에는 실수 방지)
  if (fsZoom.value <= 1.01) closeFullscreen()
}

function fsZoomIn() {
  fsZoom.value = clampFsZoom(fsZoom.value + 0.5)
}
function fsZoomOut() {
  const z = clampFsZoom(fsZoom.value - 0.5)
  fsZoom.value = z
  if (z <= 1) {
    fsPanX.value = 0
    fsPanY.value = 0
  }
}

function onKeydown(e) {
  if (!fullscreen.value) return
  if (e.key === 'Escape') closeFullscreen()
  if (e.key === '+' || e.key === '=') fsZoomIn()
  if (e.key === '-' || e.key === '_') fsZoomOut()
  if (e.key === '0') resetFsView()
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

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
  let all
  if (lines[0]?.items) {
    all = lines.flatMap((L) =>
      (L.items || []).map((it) => transposeChordName(it.chord, delta)),
    )
  } else {
    all = lines.map((c) => transposeChordName(typeof c === 'string' ? c : c.chord, delta))
  }
  // 중복 코드는 한 번만 - 처음 등장한 순서는 유지 (공간 절약)
  return [...new Set(all)]
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

    <p v-if="message" class="msg" :class="{ error: renderFailed }">
      {{ message }}
      <button v-if="renderFailed" type="button" class="retry-link" @click="renderPreview">다시 시도</button>
    </p>

    <!-- 캔버스: 화면 대부분 차지, 곧바로 보임 -->
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
          class="result-img"
          :class="{ dim: imageLoading }"
          @load="onImageLoad"
          @error="onImageError"
          @click="openFullscreen"
        />
        <button
          v-if="previewUrl && !imageLoading && !rendering"
          type="button"
          class="fs-hint"
          @click="openFullscreen"
          title="전체 화면"
        >
          ⛶ 전체 화면
        </button>
      </div>
    </div>
    <p v-else class="muted empty">± 버튼으로 조옮김하면 결과가 여기에 표시됩니다.</p>

    <!-- 하단 고정 도구: ChordEditor와 동일한 위치·스타일 -->
    <div class="bottom-tools">
      <div class="bt-panel">
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

        <div class="tool-divider"></div>

        <div class="actions">
          <button type="button" class="btn-delete" :disabled="deleting" @click="deleteSong">
            {{ deleting ? '삭제 중…' : '삭제' }}
          </button>
          <div class="actions-spacer"></div>
          <button type="button" class="btn-edit" @click="emit('edit')">수정</button>
          <button type="button" class="btn-dl" :disabled="!previewUrl || rendering" @click="downloadResult">
            다운로드
          </button>
        </div>
      </div>
    </div>

    <!-- 악보 전체 화면 오버레이 (핀치 줌 · 드래그 팬) -->
    <Teleport to="body">
      <div
        v-if="fullscreen && previewUrl"
        class="fs-overlay"
        role="dialog"
        aria-modal="true"
        aria-label="악보 전체 화면"
        @pointerdown="onFsPointerDown"
        @pointermove="onFsPointerMove"
        @pointerup="onFsPointerUp"
        @pointercancel="onFsPointerUp"
        @click="onFsClick"
      >
        <button type="button" class="fs-close" aria-label="닫기" @click.stop="closeFullscreen">
          ✕
        </button>
        <div class="fs-zoom-bar" @click.stop @pointerdown.stop>
          <button type="button" class="fs-zbtn" :disabled="fsZoom <= FS_ZOOM_MIN" @click="fsZoomOut">−</button>
          <span class="fs-zval">{{ Math.round(fsZoom * 100) }}%</span>
          <button type="button" class="fs-zbtn" :disabled="fsZoom >= FS_ZOOM_MAX" @click="fsZoomIn">+</button>
        </div>
        <img
          :src="previewUrl"
          alt="조옮김 결과 전체 화면"
          class="fs-img"
          :style="fsImgStyle"
          draggable="false"
        />
      </div>
    </Teleport>
  </div>
</template>


<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
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
  padding: 2.5rem 1rem;
  text-align: center;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px dashed #d8dee8;
}

/* --- 하단 고정 도구 (ChordEditor와 동일한 톤) --- */
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
.bt-panel {
  padding: 0.85rem 0.9rem calc(0.85rem + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}
.bt-panel h3 {
  margin: 0;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
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
.tool-divider {
  height: 1px;
  background: #e2e6ef;
  margin: 0.1rem 0;
}
.actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.actions-spacer {
  flex: 1;
  min-width: 0.5rem;
}
.btn-edit,
.btn-delete {
  padding: 0.6rem 1rem;
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
  padding: 0.6rem 1rem;
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
.result-img {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  display: block;
  cursor: zoom-in;
}
.fs-hint {
  position: absolute;
  right: 0.5rem;
  bottom: 0.5rem;
  z-index: 3;
  padding: 0.35rem 0.65rem;
  border: none;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  backdrop-filter: blur(4px);
}
.fs-hint:active {
  transform: scale(0.97);
}

/* --- 전체 화면 오버레이 --- */
.fs-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #0b0f17;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom)
    env(safe-area-inset-left);
  overscroll-behavior: none;
  touch-action: none;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
}
.fs-close {
  position: absolute;
  top: max(0.75rem, env(safe-area-inset-top));
  right: max(0.75rem, env(safe-area-inset-right));
  z-index: 3;
  width: 2.5rem;
  height: 2.5rem;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 1.15rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.fs-close:active {
  background: rgba(255, 255, 255, 0.28);
}
.fs-zoom-bar {
  position: absolute;
  left: 50%;
  bottom: max(1rem, env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.5rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(6px);
  color: #fff;
}
.fs-zbtn {
  width: 2.1rem;
  height: 2.1rem;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
}
.fs-zbtn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.fs-zbtn:not(:disabled):active {
  background: rgba(255, 255, 255, 0.28);
}
.fs-zval {
  min-width: 3.2rem;
  text-align: center;
  font-size: 0.85rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.fs-img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
  pointer-events: none; /* 제스처는 오버레이에서 처리 */
  will-change: transform;
  transition: none;
}
</style>
