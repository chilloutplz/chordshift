<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({ sheet: { type: Object, required: true } })
const emit = defineEmits(['updated', 'back', 'edit'])

const NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const NOTE_IDX = Object.fromEntries(NOTES.map((n, i) => [n, i]))
NOTE_IDX['Db']=1; NOTE_IDX['Eb']=3; NOTE_IDX['Gb']=6; NOTE_IDX['Ab']=8; NOTE_IDX['Bb']=10

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

const semitones = ref(0)
const saving = ref(false)
const rendering = ref(false)
const message = ref('')

watch(() => props.sheet, (s) => {
  semitones.value = s.transpose_semitones || 0
}, { immediate: true })

const resultUrl = computed(() => {
  const u = props.sheet.result_image
  if (!u) return ''
  return u + (u.includes('?') ? '&' : '?') + 't=' + (props.sheet.updated_at || Date.now())
})

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

async function doTranspose(delta) {
  const target = semitones.value + delta
  saving.value = true
  message.value = ''
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
    message.value = `조옮김 ${target > 0 ? '+' : ''}${target}`
  } catch (e) {
    message.value = e.message
  } finally {
    saving.value = false
  }
}

async function renderAndSave() {
  rendering.value = true
  message.value = ''
  try {
    // 서버가 원본 chords + transpose_semitones 로 렌더
    const res = await fetch(`/api/scores/${props.sheet.id}/confirm/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || '저장 실패')
    }
    const data = await res.json()
    emit('updated', data)
    message.value = '결과 악보 저장됨'
  } catch (e) {
    message.value = e.message
  } finally {
    rendering.value = false
  }
}

async function deleteThis() {
  const name = props.sheet.title || '이 악보'
  if (!confirm(`"${name}" 을(를) 삭제할까요?`)) return
  const res = await fetch(`/api/scores/${props.sheet.id}/`, { method: 'DELETE' })
  if (!res.ok && res.status !== 204) {
    message.value = '삭제 실패'
    return
  }
  emit('back')
}
</script>

<template>
  <div class="page">
    <div class="top">
      <button type="button" class="link" @click="emit('back')">← 목록</button>
      <button type="button" class="link" @click="emit('edit')">보정으로</button>
      <button type="button" class="danger" @click="deleteThis">삭제</button>
    </div>

    <h2>{{ sheet.title || '제목 없음' }}</h2>
    <p class="meta">공유: <code>{{ sheet.share_token }}</code></p>

    <section class="transpose">
      <h3>조옮김</h3>
      <div class="btns">
        <button @click="doTranspose(-1)" :disabled="saving">−1</button>
        <button @click="doTranspose(-2)" :disabled="saving">−2</button>
        <span class="cur">{{ semitones > 0 ? '+' : '' }}{{ semitones }}</span>
        <button @click="doTranspose(1)" :disabled="saving">+1</button>
        <button @click="doTranspose(2)" :disabled="saving">+2</button>
      </div>
      <p class="preview" v-if="previewChords.length">
        미리보기: {{ previewChords.slice(0, 12).join(' · ') }}{{ previewChords.length > 12 ? ' …' : '' }}
      </p>
    </section>

    <button class="save" :disabled="rendering" @click="renderAndSave">
      {{ rendering ? '생성 중…' : '결과 악보 생성 · 저장' }}
    </button>

    <section v-if="resultUrl" class="result">
      <h3>결과 악보</h3>
      <img :src="resultUrl" alt="결과" />
      <a :href="resultUrl" target="_blank" rel="noopener" download class="dl">다운로드 / 열기</a>
    </section>
    <p v-else class="muted">아직 결과 이미지가 없습니다. 위 버튼으로 생성하세요.</p>

    <p v-if="message" class="msg">{{ message }}</p>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; gap: 1rem; }
.top { display: flex; gap: 0.75rem; align-items: center; }
.link { background: none; border: none; cursor: pointer; color: #1a1a2e; }
.danger { margin-left: auto; border: 1px solid #f0c0c0; background: #fff5f5; color: #c00; border-radius: 6px; padding: 0.3rem 0.6rem; cursor: pointer; }
.meta { color: #666; font-size: 0.9rem; }
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
.result img { width: 100%; border-radius: 6px; border: 1px solid #ddd; }
.dl { display: inline-block; margin-top: 0.5rem; color: #0d6efd; }
.msg { color: #0a7; }
.muted { color: #888; }
</style>
