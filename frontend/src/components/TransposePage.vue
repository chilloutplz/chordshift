<script setup>
import { ref, computed, watch } from 'vue'
import { API_BASE } from '@/api/api.js'

const props = defineProps({ sheet: { type: Object, required: true } })
const emit = defineEmits(['updated', 'back', 'edit'])

const NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const NOTE_IDX = Object.fromEntries(NOTES.map((n, i) => [n, i]))
NOTE_IDX['Db']=1; NOTE_IDX['Eb']=3; NOTE_IDX['Gb']=6; NOTE_IDX['Ab']=8; NOTE_IDX['Bb']=10

function normalizeSemitones(n) {
  n = ((Number(n) || 0) % 12 + 12) % 12
  if (n > 6) n -= 12
  return n
}

function transposeChordName(name, semitones) {
  if (!name || !semitones) return name
  const s = String(name).trim()
  if (s.includes('/')) return s.split('/').map((p) => transposeChordName(p, semitones)).join('/')
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

/** 시작 코드 기준 라벨: "G코드", "A코드" … */
function keyLabel(chords, semitones) {
  const base = firstChordName(chords)
  const transposed = transposeChordName(base, semitones || 0)
  const root = rootOnly(transposed)
  return `${root}코드`
}


function withCache(url) {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return url + sep + 't=' + Date.now()
}

const semitones = ref(0)
const rendering = ref(false)
const imageLoading = ref(false)
const message = ref('')
const lastVariantUrl = ref('')
const localVariants = ref([])

watch(
  () => props.sheet,
  (s) => {
    if (!s) return
    semitones.value = s.transpose_semitones || 0
    localVariants.value = Array.isArray(s.variants) ? [...s.variants] : []
    // 최신 변형 또는 result_image
    if (s.result_image) {
      lastVariantUrl.value = s.result_image
    } else if (localVariants.value.length) {
      const sorted = [...localVariants.value].sort((a, b) =>
        String(b.created_at || '').localeCompare(String(a.created_at || ''))
      )
      const withImg = sorted.find((v) => v.image)
      if (withImg) lastVariantUrl.value = withImg.image
    }
  },
  { immediate: true, deep: true }
)

const resultUrl = computed(() => withCache(lastVariantUrl.value || props.sheet.result_image || ''))

watch(resultUrl, (url) => {
  imageLoading.value = !!url
}, { immediate: true })

function onImageLoad() {
  imageLoading.value = false
}
function onImageError() {
  imageLoading.value = false
  message.value = '이미지를 불러오지 못했습니다'
}

const previewChords = computed(() => {
  const delta = semitones.value || 0
  const lines = Array.isArray(props.sheet.chords) ? props.sheet.chords : []
  if (!lines.length) return []
  if (lines[0]?.items) {
    return lines.flatMap((L) =>
      (L.items || []).map((it) => transposeChordName(it.chord, delta))
    )
  }
  return lines.map((c) => transposeChordName(typeof c === 'string' ? c : c.chord, delta))
})

function doTranspose(delta) {
  semitones.value = normalizeSemitones(semitones.value + delta)
  message.value = `조옮김 ${semitones.value > 0 ? '+' : ''}${semitones.value} (미리보기) · 아래 버튼으로 결과 생성`
}

async function renderAndSave() {
  rendering.value = true
  message.value = '결과 악보 생성 중…'
  try {
    const id = props.sheet.id
    if (!id) throw new Error('곡 ID 없음')

    let res = await fetch(`${API_BASE}/api/songs/${id}/render_variant/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semitones: semitones.value,
        chords: props.sheet.chords || [],
        label: keyLabel(props.sheet.chords || [], semitones.value),
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || err.detail || '저장 실패')
    }

    const data = await res.json()
    const variant = data.variant
    const song = data.song || data

    if (variant?.image) {
      lastVariantUrl.value = variant.image
    } else if (song?.result_image) {
      lastVariantUrl.value = song.result_image
    }

    if (Array.isArray(song?.variants)) {
      localVariants.value = song.variants
    } else if (variant) {
      const rest = localVariants.value.filter(
        (v) => v.transpose_semitones !== variant.transpose_semitones
      )
      localVariants.value = [variant, ...rest]
    }

    emit('updated', song)
    message.value = `결과 저장됨 (${variant?.label || keyLabel(props.sheet.chords || [], semitones.value)})`
  } catch (e) {
    message.value = e.message || '저장 실패'
  } finally {
    rendering.value = false
  }
}


async function downloadResult() {
  let url = lastVariantUrl.value || props.sheet.result_image
  if (!url) {
    message.value = '다운로드할 이미지가 없습니다'
    return
  }
  // 캐시 쿼리 제거 + 같은 오리진(/media)으로 맞춤 (CORS 회피)
  url = String(url).split('?')[0]
  try {
    const u = new URL(url, window.location.origin)
    if (u.pathname.startsWith('/media') || u.pathname.startsWith('/api/files')) {
      url = u.pathname + (u.search || '')
    }
  } catch (_) { /* relative ok */ }
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error('이미지 요청 실패')
    const blob = await res.blob()
    const title = (props.sheet.title || 'chordshift').replace(/[\\/:*?"<>|]/g, '_')
    const key = keyLabel(props.sheet.chords || [], semitones.value)
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

function showVariant(v) {
  if (v?.image) {
    imageLoading.value = true
    lastVariantUrl.value = v.image
    semitones.value = normalizeSemitones(v.transpose_semitones || 0)
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

    <section class="transpose">
      <h3>조옮김</h3>
      <div class="btns">
        <button @click="doTranspose(-1)" :disabled="rendering">−1</button>
        <button @click="doTranspose(-2)" :disabled="rendering">−2</button>
        <span class="cur">{{ semitones > 0 ? '+' : '' }}{{ semitones }}</span>
        <button @click="doTranspose(1)" :disabled="rendering">+1</button>
        <button @click="doTranspose(2)" :disabled="rendering">+2</button>
      </div>
      <p class="preview" v-if="previewChords.length">
        미리보기: {{ previewChords.slice(0, 12).join(' · ') }}{{ previewChords.length > 12 ? ' …' : '' }}
      </p>
    </section>

    <button class="save" :disabled="rendering" @click="renderAndSave">
      {{ rendering ? '생성 중…' : '결과 악보 생성 · 저장' }}
    </button>

    <p v-if="message" class="msg">{{ message }}</p>

    <section v-if="localVariants.length" class="variants">
      <h3>저장된 코드</h3>
      <div class="var-list">
        <button
          v-for="v in localVariants"
          :key="v.id"
          type="button"
          class="var-chip"
          :class="{ on: lastVariantUrl && v.image && lastVariantUrl.includes(String(v.id)) === false && lastVariantUrl === v.image }"
          @click="showVariant(v)"
        >
          {{ v.label || ((v.transpose_semitones > 0 ? '+' : '') + v.transpose_semitones) }}
        </button>
      </div>
    </section>

    <section v-if="resultUrl || rendering" class="result">
      <h3>결과 악보</h3>
      <div class="img-wrap">
        <div v-if="rendering || imageLoading" class="img-loading">
          <div class="spinner"></div>
          <p>{{ rendering ? '결과 악보를 생성·저장하는 중…' : '이미지를 불러오는 중…' }}</p>
        </div>
        <img
          v-if="resultUrl"
          :src="resultUrl"
          alt="결과 악보"
          :class="{ dim: imageLoading || rendering }"
          @load="onImageLoad"
          @error="onImageError"
        />
      </div>
      <button type="button" class="dl" :disabled="!resultUrl || rendering || imageLoading" @click="downloadResult">
        다운로드
      </button>
    </section>
    <p v-else class="muted">아직 결과 이미지가 없습니다. 「결과 악보 생성 · 저장」을 눌러주세요.</p>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 1rem; }
.top { display: flex; gap: 0.75rem; align-items: center; }
.link { background: none; border: none; cursor: pointer; color: #1a1a2e; }
.btns { display: flex; gap: 0.5rem; align-items: center; }
.btns button { padding: 0.5rem 0.9rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.cur { min-width: 2.5rem; text-align: center; font-weight: 700; }
.preview { font-size: 0.9rem; color: #444; }
.save {
  padding: 0.85rem 1.2rem; background: #0a7a3e; color: #fff; border: none;
  border-radius: 8px; font-weight: 600; font-size: 1.05rem; cursor: pointer;
}
.save:disabled { opacity: 0.5; }
.result { padding: 1rem; border: 2px solid #0a7a3e; border-radius: 10px; background: #f6fbf8; }
.result img { width: 100%; border-radius: 6px; border: 1px solid #ddd; display: block; }
.result img.dim { opacity: 0.35; }
.img-wrap { position: relative; min-height: 120px; }
.img-loading {
  position: absolute; inset: 0; z-index: 2;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 0.6rem; background: rgba(246, 251, 248, 0.85);
  border-radius: 6px; color: #0a7a3e; font-weight: 600; font-size: 0.95rem;
}
.spinner {
  width: 32px; height: 32px;
  border: 3px solid #cce8d8; border-top-color: #0a7a3e;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.dl:disabled { opacity: 0.5; cursor: not-allowed; }
.dl {
  display: inline-block;
  margin-top: 0.5rem;
  padding: 0.45rem 0.9rem;
  background: #0d6efd;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}
.dl:hover { background: #0b5ed7; }
.msg { color: #0a7; font-weight: 600; }
.muted { color: #888; }
.variants h3 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.var-list { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.var-chip {
  padding: 0.35rem 0.7rem; border: 1px solid #ccc; border-radius: 16px;
  background: #fff; cursor: pointer; font-size: 0.85rem;
}
.var-chip.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
</style>
