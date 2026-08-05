<script setup>
import { ref } from 'vue'
import { apiFetch, API_BASE } from '@/api/api.js'

const props = defineProps({ initialTitle: { type: String, default: '' } })
const emit = defineEmits(['uploaded'])
const file = ref(null)
const title = ref(props.initialTitle || '')
const loading = ref(false)
const error = ref('')

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (!f) return
  file.value = f
  error.value = ''
  // 선택 즉시 바로 업로드 -> 편집기로 이동 (미리보기 없음)
  upload()
}

async function upload() {
  if (!file.value) {
    error.value = '이미지를 선택해주세요'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('image', file.value)
    if (title.value) form.append('title', title.value)
    form.append('run_ocr', 'false')
    const res = await apiFetch('/api/temp/upload/', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `업로드 실패 (${res.status})`)
    }
    const data = await res.json()
    if (data.image_url?.startsWith('/')) data.image_url = `${API_BASE}${data.image_url}`
    if (data.optimized_image?.startsWith('/')) data.optimized_image = `${API_BASE}${data.optimized_image}`
    emit('uploaded', data)
  } catch (e) {
    error.value = e.message || '업로드 중 오류'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="upload">
    <h2>새 악보 업로드</h2>
    <p class="hint">이미지를 선택하면 바로 편집 화면으로 이동합니다.</p>
    <label class="file-label" :class="{ disabled: loading }">
      <input type="file" accept="image/*" :disabled="loading" @change="onFileChange" />
      <span v-if="!loading">{{ file ? file.name : '이미지 선택 (클릭)' }}</span>
      <span v-else>업로드 중…</span>
    </label>
    <input v-model="title" type="text" placeholder="제목 (선택)" class="title-input" :disabled="loading" />
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="loading-msg">업로드 중… 편집기로 이동합니다.</p>
  </div>
</template>

<style scoped>
.upload { display: flex; flex-direction: column; gap: 1rem; }
.hint { color: #666; font-size: 0.9rem; margin: 0; }
.file-label { border: 2px dashed #ccc; border-radius: 8px; padding: 2rem; text-align: center; cursor: pointer; font-weight: 600; background: #fafafa; }
.file-label.disabled { opacity: 0.6; pointer-events: none; }
.file-label input { display: none; }
.title-input { padding: 0.6rem 0.8rem; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }
.error { color: #c00; }
.loading-msg { color: #0d6efd; font-weight: 600; text-align: center; }
</style>
