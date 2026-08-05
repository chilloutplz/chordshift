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

function variantCount(s) {
  if (Array.isArray(s.variants)) return s.variants.length
  return 0
}

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
    <h2>곡 찾아보기</h2>
    <p class="lead">제목으로 검색하거나 폴더에서 고르세요.</p>

    <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileSelected" />

    <form class="search-row" @submit.prevent="search">
      <input v-model="query" type="search" placeholder="곡 제목 검색" autocomplete="off" />
      <button type="submit" :disabled="loading">검색</button>
    </form>

    <div v-if="searched" class="after-search">
      <p v-if="!loading && !allSongs.length" class="empty-msg">「{{ query || '검색어' }}」에 해당하는 곡이 없습니다.</p>
      <p v-else-if="!loading && allSongs.length" class="hint-msg">원하는 곡이 없나요? (제목은 같아도 다른 악보일 수 있어요)</p>
      <button v-if="!loading && !uploading" type="button" class="upload-link" @click="triggerUpload(query)">
        + 새 악보 업로드
      </button>
      <p v-if="uploading" class="uploading-msg">업로드 중… 바로 편집 화면으로 이동합니다.</p>
      <p v-if="uploadError" class="error">{{ uploadError }}</p>
    </div>

    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else>
      <h3 class="sub">전체 폴더 ({{ allSongs.length }}곡)</h3>
      <p v-if="!folders.length && !searched" class="muted">저장된 곡이 없습니다. 검색 후 새 악보를 업로드할 수 있습니다.</p>
      <ul v-else-if="folders.length" class="folder-list">
        <li v-for="f in folders" :key="f.key" class="folder">
          <button type="button" class="folder-head" @click="toggleFolder(f.key)">
            <span class="cho">{{ f.key }}</span>
            <span class="fname">{{ f.key }} ({{ f.count }}곡)</span>
            <span class="chev">{{ openFolder === f.key ? '▾' : '▸' }}</span>
          </button>
          <ul v-if="openFolder === f.key" class="song-list">
            <li v-for="s in f.songs" :key="s.id">
              <button type="button" class="song-item" @click="emit('open', s)">
                <span class="title">{{ s.title || '제목 없음' }}</span>
                <span class="meta" v-if="variantCount(s)">코드 {{ variantCount(s) }}</span>
              </button>
            </li>
          </ul>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.home h2 { margin: 0 0 0.35rem; font-size: 1.25rem; }
.lead { margin: 0 0 1rem; color: #666; font-size: 0.9rem; }
.search-row { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.search-row input { flex: 1; padding: 0.65rem 0.85rem; border: 1px solid #ccc; border-radius: 8px; font-size: 1rem; }
.search-row button { padding: 0.65rem 1.1rem; border: none; border-radius: 8px; background: #1a1a2e; color: #fff; cursor: pointer; font-weight: 600; }
.after-search { margin-bottom: 1.25rem; padding: 0.85rem; background: #f8faff; border: 1px solid #d0e0ff; border-radius: 10px; }
.empty-msg { margin: 0 0 0.6rem; color: #555; font-weight: 600; }
.hint-msg { margin: 0 0 0.6rem; color: #666; font-size: 0.9rem; }
.upload-link { width: 100%; padding: 0.7rem; border: 2px dashed #0d6efd; border-radius: 10px; background: #fff; color: #0d6efd; font-weight: 700; cursor: pointer; }
.uploading-msg { margin: 0.6rem 0 0; color: #0d6efd; font-weight: 700; text-align: center; }
.sub { margin: 0 0 0.6rem; font-size: 0.95rem; color: #444; font-weight: 700; }
.folder-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.35rem; }
.folder-head { width: 100%; display: flex; align-items: center; gap: 0.5rem; padding: 0.65rem 0.85rem; border: 1px solid #e5e5e5; border-radius: 8px; background: #fafafa; cursor: pointer; text-align: left; }
.folder-head:hover { border-color: #0d6efd; background: #f8faff; }
.cho { width: 1.8rem; height: 1.8rem; display: flex; align-items: center; justify-content: center; background: #1a1a2e; color: #fff; border-radius: 6px; font-weight: 800; font-size: 0.95rem; }
.fname { flex: 1; font-weight: 600; color: #333; }
.chev { color: #999; }
.song-list { list-style: none; padding: 0.35rem 0 0.35rem 1.5rem; margin: 0; display: flex; flex-direction: column; gap: 0.3rem; }
.song-item { width: 100%; text-align: left; padding: 0.55rem 0.75rem; border: 1px solid #eee; border-radius: 6px; background: #fff; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.song-item:hover { border-color: #0d6efd; background: #f8faff; }
.title { font-weight: 600; }
.meta { font-size: 0.8rem; color: #888; }
.muted { color: #888; }
.error { color: #c00; }
</style>
