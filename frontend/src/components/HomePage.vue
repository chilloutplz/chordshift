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
const isSearchResult = ref(false) // allSongs가 검색 필터링된 결과인지 여부
const currentFolder = ref(null) // 탐색기처럼: null이면 폴더 루트, 아니면 그 폴더 안
const uploading = ref(false)
const uploadError = ref('')
const fileInput = ref(null)
const pendingTitle = ref('')
const searchInputRef = ref(null)

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

const currentFolderSongs = computed(() => {
  const f = folders.value.find((f) => f.key === currentFolder.value)
  return f ? f.songs : []
})

function thumbUrl(s) {
  let u = s.optimized_image || s.original_image || ''
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
  return u
}

async function loadAll() {
  loading.value = true
  error.value = ''
  isSearchResult.value = false
  currentFolder.value = null
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
  currentFolder.value = null
  try {
    if (!q) {
      await loadAll()
      return
    }
    isSearchResult.value = true
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

function openFolderNav(key) {
  currentFolder.value = key
}
function goToRoot() {
  currentFolder.value = null
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
  searchInputRef.value?.focus()
})
</script>

<template>
  <section class="home">
    <div class="hero">
      <h2>곡 찾아보기</h2>
      <p class="lead">제목의 일부로 검색할 수 있어요. 초성 폴더에서 골라도 됩니다.</p>
    </div>

    <input ref="fileInput" type="file" accept="image/*" class="sr-only" @change="onFileSelected" />

    <form class="search-row card" @submit.prevent="search">
      <input
        ref="searchInputRef"
        v-model="query"
        class="field"
        type="search"
        placeholder="검색"
        autocomplete="off"
        enterkeyhint="search"
      />
      <button type="submit" class="btn btn-primary" :disabled="loading">
        {{ loading ? '검색 중…' : '검색' }}
      </button>
      <button
        type="button"
        class="btn btn-dashed upload-inline"
        :disabled="uploading"
        @click="triggerUpload(query)"
        title="악보 이미지 업로드"
      >
        {{ uploading ? '업로드 중…' : '+ 업로드' }}
      </button>
    </form>

    <p v-if="uploading" class="uploading-msg">업로드 중… 편집 화면으로 이동합니다.</p>
    <p v-if="uploadError" class="error">{{ uploadError }}</p>

    <div v-if="isSearchResult" class="upload-panel card">
      <p v-if="!loading && !allSongs.length" class="empty-msg">
        「{{ query || '검색어' }}」에 해당하는 곡이 없습니다.
      </p>
      <p v-else-if="!loading && allSongs.length" class="hint-msg">
        원하는 곡이 없나요? 제목이 같아도 다른 악보일 수 있어요. 위 「+ 업로드」로 새로 추가할 수 있어요.
      </p>
    </div>

    <p v-if="error" class="error status">{{ error }}</p>
    <p v-else-if="loading" class="muted status">불러오는 중…</p>

    <template v-else>
      <!-- 검색 결과: 폴더 없이 바로 평면 목록 -->
      <template v-if="isSearchResult">
        <div class="list-head">
          <h3 class="sub">검색 결과 {{ allSongs.length }}곡</h3>
        </div>
        <ul v-if="allSongs.length" class="file-list">
          <li v-for="s in allSongs" :key="s.id">
            <button type="button" class="file-item" @click="emit('open', s)">
              <span class="file-thumb">
                <img v-if="thumbUrl(s)" :src="thumbUrl(s)" alt="" loading="lazy" />
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M9 18V5l11-2v13" stroke="#94a3b8" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                  <circle cx="6" cy="18" r="3" stroke="#94a3b8" stroke-width="1.6" />
                  <circle cx="17" cy="16" r="3" stroke="#94a3b8" stroke-width="1.6" />
                </svg>
              </span>
              <span class="file-title">{{ s.title || '(제목 없음)' }}</span>
            </button>
          </li>
        </ul>
      </template>

      <!-- 폴더 안: 탐색기처럼 해당 폴더 곡만 -->
      <template v-else-if="currentFolder">
        <div class="breadcrumb">
          <button type="button" class="crumb" @click="goToRoot">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M3 11.5 12 4l9 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
              <path d="M5 10v9a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            전체 곡
          </button>
          <span class="crumb-sep">›</span>
          <span class="crumb-current">{{ currentFolder }} <em>({{ currentFolderSongs.length }})</em></span>
        </div>
        <ul v-if="currentFolderSongs.length" class="file-list">
          <li v-for="s in currentFolderSongs" :key="s.id">
            <button type="button" class="file-item" @click="emit('open', s)">
              <span class="file-thumb">
                <img v-if="thumbUrl(s)" :src="thumbUrl(s)" alt="" loading="lazy" />
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M9 18V5l11-2v13" stroke="#94a3b8" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
                  <circle cx="6" cy="18" r="3" stroke="#94a3b8" stroke-width="1.6" />
                  <circle cx="17" cy="16" r="3" stroke="#94a3b8" stroke-width="1.6" />
                </svg>
              </span>
              <span class="file-title">{{ s.title || '(제목 없음)' }}</span>
            </button>
          </li>
        </ul>
      </template>

      <!-- 루트: 폴더 아이콘 그리드 -->
      <template v-else>
        <div class="list-head">
          <h3 class="sub">전체 {{ allSongs.length }}곡</h3>
        </div>
        <ul v-if="folders.length" class="folder-grid">
          <li v-for="f in folders" :key="f.key">
            <button type="button" class="folder-tile" @click="openFolderNav(f.key)">
              <span class="folder-icon-wrap">
                <svg width="42" height="42" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4.379a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 12.12 7H19.5A1.5 1.5 0 0 1 21 8.5v9A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5v-11Z" fill="#facc15" stroke="#d97706" stroke-width="1" />
                </svg>
                <span class="folder-glyph">{{ f.key }}</span>
              </span>
              <span class="folder-count">{{ f.count }}곡</span>
            </button>
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
  flex-wrap: wrap;
}
.search-row .field {
  flex: 1;
  min-width: 120px;
}
.upload-inline {
  flex-shrink: 0;
  white-space: nowrap;
  padding: 0.65rem 0.9rem;
}
@media (max-width: 480px) {
  .search-row {
    padding: 0.5rem;
    gap: 0.35rem;
  }
  .search-row .field {
    padding: 0.55rem 0.65rem;
    font-size: 0.9rem;
    min-width: 80px;
  }
  .search-row .btn {
    padding: 0.5rem 0.7rem;
    font-size: 0.85rem;
  }
  .upload-inline {
    padding: 0.5rem 0.6rem;
  }
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
.folder-grid {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 0.6rem;
}
.folder-tile {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 0.4rem 0.6rem;
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 8px);
  background: transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}
.folder-tile:hover {
  border-color: #93c5fd;
  background: var(--primary-soft, #eff4ff);
}
.folder-tile:active {
  transform: scale(0.96);
}
.folder-icon-wrap {
  position: relative;
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.folder-glyph {
  position: absolute;
  top: 58%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-weight: 800;
  font-size: 0.95rem;
  color: #78350f;
  line-height: 1;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.55);
}
.folder-count {
  font-size: 0.72rem;
  color: var(--text-muted, #5c6578);
  font-variant-numeric: tabular-nums;
}
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.1rem;
  margin-bottom: 0.15rem;
  font-size: 0.9rem;
}
.crumb {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: none;
  border: none;
  padding: 0.2rem 0.3rem;
  color: var(--primary, #2563eb);
  font-weight: 600;
  cursor: pointer;
  border-radius: 6px;
}
.crumb:hover {
  background: var(--primary-soft, #eff4ff);
}
.crumb-sep {
  color: #b0b8c4;
}
.crumb-current {
  font-weight: 700;
  color: #1f2937;
}
.crumb-current em {
  font-style: normal;
  font-weight: 500;
  color: var(--text-muted, #5c6578);
  font-size: 0.85rem;
}
.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.file-item {
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border, #e2e6ef);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  transition: border-color 0.15s, background 0.15s;
}
.file-item:hover {
  border-color: #93c5fd;
  background: var(--primary-soft, #eff4ff);
}
.file-thumb {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 6px;
  overflow: hidden;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e9f0;
}
.file-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.file-title {
  font-weight: 600;
  color: #1f2937;
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
