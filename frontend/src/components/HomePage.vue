<script setup>
import { ref, onMounted } from 'vue'
import UploadScore from './UploadScore.vue'

const emit = defineEmits(['open', 'uploaded'])
const query = ref('')
const results = ref([])
const loading = ref(false)
const showUpload = ref(false)
const error = ref('')

async function search(q = query.value) {
  loading.value = true
  error.value = ''
  try {
    const url = q.trim()
      ? `/api/scores/search/?q=${encodeURIComponent(q.trim())}`
      : '/api/scores/'
    const res = await fetch(url)
    if (!res.ok) throw new Error('검색 실패')
    const data = await res.json()
    const list = Array.isArray(data) ? data : (data.results || [])
    // 최근 5개
    results.value = list.slice(0, 5)
  } catch (e) {
    error.value = e.message
    results.value = []
  } finally {
    loading.value = false
  }
}

async function deleteSheet(sheet, e) {
  e?.stopPropagation?.()
  const name = sheet.title || sheet.share_token || '이 악보'
  if (!confirm(`"${name}" 을(를) 삭제할까요?\n이미지 파일과 데이터가 모두 삭제됩니다.`)) return
  try {
    const res = await fetch(`/api/scores/${sheet.id}/`, { method: 'DELETE' })
    if (!res.ok && res.status !== 204) throw new Error('삭제 실패')
    results.value = results.value.filter((s) => s.id !== sheet.id)
  } catch (err) {
    alert(err.message || '삭제 중 오류')
  }
}

function onUploaded(sheet) {
  showUpload.value = false
  emit('uploaded', sheet)
}

onMounted(() => search())
</script>

<template>
  <section class="home">
    <h2>내 악보 찾기</h2>
    <form class="search-row" @submit.prevent="search()">
      <input v-model="query" type="search" placeholder="제목 또는 공유 토큰 검색" />
      <button type="submit" :disabled="loading">검색</button>
    </form>

    <h3 class="sub">최근 업로드</h3>
    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else-if="!results.length" class="muted">저장된 악보가 없습니다.</p>
    <ul v-else class="sheet-list">
      <li v-for="s in results" :key="s.id" class="sheet-row">
        <button type="button" class="sheet-item" @click="emit('open', s)">
          <span class="title">{{ s.title || '제목 없음' }}</span>
          <span class="meta">{{ s.share_token }} · {{ (s.updated_at || '').slice(0, 10) }}</span>
        </button>
        <button type="button" class="del-btn" @click="deleteSheet(s, $event)">삭제</button>
      </li>
    </ul>

    <div class="divider">또는</div>
    <button v-if="!showUpload" type="button" class="new-btn" @click="showUpload = true">+ 새 악보 업로드</button>
    <UploadScore v-else @uploaded="onUploaded" />
  </section>
</template>

<style scoped>
.home h2 { margin: 0 0 0.75rem; font-size: 1.15rem; }
.sub { margin: 0.5rem 0; font-size: 0.95rem; color: #555; }
.search-row { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.search-row input { flex: 1; padding: 0.6rem 0.8rem; border: 1px solid #ccc; border-radius: 8px; }
.search-row button { padding: 0.6rem 1rem; border: none; border-radius: 8px; background: #1a1a2e; color: #fff; cursor: pointer; }
.sheet-list { list-style: none; padding: 0; margin: 0 0 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.sheet-row { display: flex; gap: 0.4rem; }
.sheet-item {
  flex: 1; text-align: left; padding: 0.75rem 1rem; border: 1px solid #e0e0e0;
  border-radius: 8px; background: #fff; cursor: pointer; display: flex; flex-direction: column; gap: 0.2rem;
}
.sheet-item:hover { border-color: #0d6efd; background: #f8faff; }
.title { font-weight: 700; }
.meta { font-size: 0.8rem; color: #777; }
.del-btn {
  padding: 0 0.75rem; border: 1px solid #f0c0c0; border-radius: 8px;
  background: #fff5f5; color: #c00; cursor: pointer; font-size: 0.85rem;
}
.divider { text-align: center; color: #999; margin: 1rem 0; }
.new-btn {
  width: 100%; padding: 0.85rem; border: 2px dashed #0d6efd; border-radius: 10px;
  background: #f0f6ff; color: #0d6efd; font-weight: 700; cursor: pointer;
}
.muted { color: #888; }
.error { color: #c00; }
</style>
