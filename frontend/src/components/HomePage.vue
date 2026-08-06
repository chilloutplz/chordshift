<script setup>
import { ref, computed, onMounted } from 'vue'
import { apiFetch, API_BASE } from '../api/api'

const emit = defineEmits(['open', 'go-upload'])

const CHO = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

const query = ref('')
const allSongs = ref([])
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const openFolder = ref(null)
const uploading = ref(false)
const uploadError = ref('')
const fileInput = ref(null)
const pendingTitle = ref('')

function getCho(title) {
  const c = (title || '').trim().charAt(0)
  if (!c) return '기타'
  const code = c.charCodeAt(0)
  if (code >= 0xac00 && code <= 0xd7a3) {
    return CHO[Math.floor((code - 0xac00) / (21 * 28))] || '기타'
  }
  const choIdx = CHO.indexOf(c)
  if (choIdx >= 0) return CHO[choIdx]
  if (/[A-Za-z]/.test(c)) return c.toUpperCase()
  if (/[0-9]/.test(c)) return '0-9'
  return '기타'
}

const folders = computed(() => {
  const map = new Map()
  for (const s of allSongs.value) {
    const key = getCho(s.title)
    if (!map.has(key)) map.set(key, [])
    map.get(key).push(s)
  }
  const keys = [...map.keys()].sort((a, b) => {
    const order = (k) => {
      const i = CHO.indexOf(k)
      if (i >= 0) return i
      if (/^[A-Z]$/.test(k)) return 100 + k.charCodeAt(0)
      if (k === '0-9') return 200
      return 300
    }
    return order(a) - order(b)
  })
  return keys.map((key) => ({
    key,
    count: map.get(key).length,
    songs: map.get(key).sort((a, b) => (a.title || '').localeCompare(b.title || '', 'ko')),
  }))
})

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const res = await apiFetch(`/api/songs/`)
    if (!res.ok) throw new Error('목록을 불러오지 못했습니다')
    const data = await res.json()
    allSongs.value = Array.isArray(data) ? data : (data.results || [])
  } catch (e) {
    error.value = e.message
    allSongs.value = []
  } finally {
    loading.value = false
  }
}

async function search() {
  const q = query.value.trim()
  searched.value = true
  loading.value = true
  error.value = ''
  try {
    if (!q) {
      await loadAll()
      return
    }
    const res = await apiFetch(`/api/songs/search/?q=${encodeURIComponent(q)}`)
    if (!res.ok) throw new Error('검색 실패')
    const data = await res.json()
    allSongs.value = Array.isArray(data) ? data : (data.results || [])
  } catch (e) {
    error.value = e.message
    allSongs.value = []
  } finally {
    loading.value = false
  }
}

function toggleFolder(key) {
  openFolder.value = openFolder.value === key ? null : key
}

// ★ 핵심: 업로드 중간 페이지 없이 바로 편집으로!
function triggerUpload(titleHint = '') {
  pendingTitle.value = titleHint || query.value.trim()
  uploadError.value = ''
  fileInput.value?.click()
}

async function onFileSelected(e) {
  const f = e.target.files?.[0]
  if (!f) return
  uploading.value = true
  uploadError.value = ''
  try {
    const form = new FormData()
    form.append('image', f)
    if (pendingTitle.value) form.append('title', pendingTitle.value)
    form.append('run_ocr', 'false')
    const res = await apiFetch('/api/temp/upload/', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `업로드 실패 (${res.status})`)
    }
    const data = await res.json()
    if (data.image_url?.startsWith('/')) data.image_url = `${API_BASE}${data.image_url}`
    if (data.optimized_image?.startsWith('/')) data.optimized_image = `${API_BASE}${data.optimized_image}`
    // 바로 편집 화면으로!
    emit('open', data)
  } catch (err) {
    uploadError.value = err.message || '업로드 중 오류'
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

onMounted(() => {
  searched.value = false
  loadAll()
})
</script>

<template>
  <section class="home">
    <div class="hero">
      <h2>곡 찾아보기</h2>
      <p class="lead">제목으로 검색하거나, 초성 폴더에서 고른 뒤 조옮김하세요.</p>
    </div>

    <input ref="fileInput" type="file" accept="image/*" class="sr-only" @change="onFileSelected" />

    <form class="search-row card" @submit.prevent="search">
      <input
        v-model="query"
        class="field"
        type="search"
        placeholder="곡 제목 검색…"
        autocomplete="off"
        enterkeyhint="search"
      />
      <button type="submit" class="btn btn-primary" :disabled="loading">
        {{ loading ? '검색 중…' : '검색' }}
      </button>
    </form>

    <div v-if="searched" class="upload-panel card">
      <p v-if="!loading && !allSongs.length" class="empty-msg">
        「{{ query || '검색어' }}」에 해당하는 곡이 없습니다.
      </p>
      <p v-else-if="!loading && allSongs.length" class="hint-msg">
        원하는 곡이 없나요? 제목이 같아도 다른 악보일 수 있어요.
      </p>
      <button
        v-if="!loading && !uploading"
        type="button"
        class="btn btn-dashed upload-btn"
        @click="triggerUpload(query)"
      >
        + 새 악보 업로드
      </button>
      <p v-if="uploading" class="uploading-msg">업로드 중… 편집 화면으로 이동합니다.</p>
      <p v-if="uploadError" class="error">{{ uploadError }}</p>
    </div>

    <div v-if="!searched" class="quick-upload">
      <button type="button" class="btn btn-dashed upload-btn" :disabled="uploading" @click="triggerUpload()">
        {{ uploading ? '업로드 중…' : '+ 악보 이미지 업로드' }}
      </button>
      <p v-if="uploadError" class="error">{{ uploadError }}</p>
    </div>

    <p v-if="error" class="error status">{{ error }}</p>
    <p v-else-if="loading" class="muted status">불러오는 중…</p>

    <template v-else>
      <div class="list-head">
        <h3 class="sub">전체 {{ allSongs.length }}곡</h3>
      </div>
      <ul v-if="folders.length" class="folder-list">
        <li v-for="f in folders" :key="f.key" class="folder">
          <button type="button" class="folder-head" @click="toggleFolder(f.key)">
            <span class="cho">{{ f.key }}</span>
            <span class="fname">{{ f.key }} 폴더</span>
            <span class="count">{{ f.count }}</span>
            <span class="chev">{{ openFolder === f.key ? '▾' : '▸' }}</span>
          </button>
          <ul v-if="openFolder === f.key" class="song-list">
            <li v-for="s in f.songs" :key="s.id">
              <button type="button" class="song-item" @click="emit('open', s)">
                <span class="title">{{ s.title || '(제목 없음)' }}</span>
              </button>
            </li>
          </ul>
        </li>
      </ul>
      <div v-else class="empty-state card">
        <p class="empty-title">아직 저장된 곡이 없어요</p>
        <p class="muted">악보 이미지를 업로드하면 OCR 후 코드를 보정·조옮김할 수 있습니다.</p>
        <button type="button" class="btn btn-primary" :disabled="uploading" @click="triggerUpload()">
          첫 악보 업로드
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.hero h2 {
  margin: 0 0 0.25rem;
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.lead {
  margin: 0;
  color: var(--text-muted, #5c6578);
  font-size: 0.92rem;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  border: 0;
}
.search-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem;
  align-items: center;
}
.search-row .field {
  flex: 1;
  min-width: 0;
}
.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.empty-msg {
  margin: 0;
  font-weight: 700;
  color: #374151;
}
.hint-msg {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted, #5c6578);
}
.upload-btn {
  width: 100%;
  padding: 0.85rem 1rem;
}
.quick-upload {
  margin-top: 0.15rem;
}
.uploading-msg {
  margin: 0;
  color: var(--primary, #2563eb);
  font-weight: 700;
  text-align: center;
  font-size: 0.9rem;
}
.status {
  margin: 0.25rem 0 0;
  font-size: 0.9rem;
}
.list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: 0.35rem;
}
.sub {
  margin: 0;
  font-size: 0.95rem;
  color: #374151;
  font-weight: 700;
}
.folder-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.folder-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.7rem 0.85rem;
  border: 1px solid var(--border, #e2e6ef);
  border-radius: var(--radius-sm, 8px);
  background: var(--surface, #fff);
  cursor: pointer;
  text-align: left;
  box-shadow: var(--shadow, none);
  transition: border-color 0.15s, background 0.15s;
}
.folder-head:hover {
  border-color: #93c5fd;
  background: var(--primary-soft, #eff4ff);
}
.cho {
  width: 1.85rem;
  height: 1.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #1e293b, #334155);
  color: #fff;
  border-radius: 7px;
  font-weight: 800;
  font-size: 0.9rem;
  flex-shrink: 0;
}
.fname {
  flex: 1;
  font-weight: 600;
  color: #1f2937;
}
.count {
  font-size: 0.8rem;
  color: var(--text-muted, #5c6578);
  font-variant-numeric: tabular-nums;
}
.chev {
  color: #94a3b8;
  font-size: 0.85rem;
}
.song-list {
  list-style: none;
  padding: 0.4rem 0 0.2rem 0.65rem;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.song-item {
  width: 100%;
  text-align: left;
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border, #e2e6ef);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  transition: border-color 0.15s, background 0.15s;
}
.song-item:hover {
  border-color: #93c5fd;
  background: var(--primary-soft, #eff4ff);
}
.title {
  font-weight: 600;
  color: #1f2937;
}
.meta {
  font-size: 0.78rem;
  color: #94a3b8;
  flex-shrink: 0;
}
.empty-state {
  text-align: center;
  padding: 1.75rem 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.empty-title {
  margin: 0;
  font-weight: 800;
  font-size: 1.05rem;
}
.empty-state .muted {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  max-width: 22rem;
}
.error {
  color: var(--danger, #dc2626);
  margin: 0;
  font-size: 0.9rem;
}
.muted {
  color: var(--text-muted, #5c6578);
}
</style>
