<script setup>
import { ref } from 'vue'
import { apiFetch, API_BASE } from '@/api/api.js'

const props = defineProps({ initialTitle: { type: String, default: '' } })
const emit = defineEmits(['uploaded'])
const file = ref(null)
const title = ref(props.initialTitle || '')
const loading = ref(false)
const phase = ref('')
const error = ref('')
const preview = ref(null)

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (!f) return
  file.value = f
  error.value = ''
  preview.value = f.type.startsWith('image/') ? URL.createObjectURL(f) : null
}

async function upload() {
  if (!file.value) {
    error.value = '이미지를 선택해주세요'
    return
  }
  loading.value = true
  phase.value = 'ocr'
  error.value = ''
  try {
    const form = new FormData()
    form.append('image', file.value)
    if (title.value) form.append('title', title.value)
    form.append('run_ocr', 'true')
    // DB 생성 없이 임시 저장
    const res = await apiFetch('/api/temp/upload/', { method: 'POST', body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `업로드 실패 (${res.status})`)
    }
    const data = await res.json()
     // 상대경로면 절대주소로 바꿔주기
    if (data.image_url?.startsWith('/')) data.image_url = `${API_BASE}${data.image_url}`
    if (data.optimized_image?.startsWith('/')) data.optimized_image = `${API_BASE}${data.optimized_image}`
    emit('uploaded', data)
  } catch (e) {
    error.value = e.message || '업로드 중 오류'
    phase.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="upload">
    <h2>새 악보 업로드</h2>
    <p class="hint">임시 분석만 하며, <b>보정본 저장</b> 전까지 DB에 남지 않습니다.</p>
    <label class="file-label" :class="{ disabled: loading }">
      <input type="file" accept="image/*" :disabled="loading" @change="onFileChange" />
      <span>{{ file ? file.name : '이미지 선택' }}</span>
    </label>
    <img v-if="preview && !loading" :src="preview" class="preview" alt="미리보기" />
    <input v-model="title" type="text" placeholder="제목 (선택)" class="title-input" :disabled="loading" />
    <button :disabled="loading || !file" @click="upload">
      {{ loading ? 'OCR 분석 중…' : '업로드 & OCR' }}
    </button>
    <div v-if="loading && phase === 'ocr'" class="ocr-overlay">
      <div class="ocr-stage">
        <div class="sheet-fake" />
        <div class="glass"><div class="glass-lens" /><div class="glass-handle" /></div>
      </div>
      <p class="ocr-text">코드를 찾는 중… (아직 저장되지 않음)</p>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.upload { display: flex; flex-direction: column; gap: 1rem; position: relative; }
.hint { color: #666; font-size: 0.9rem; margin: 0; }
.file-label { border: 2px dashed #ccc; border-radius: 8px; padding: 2rem; text-align: center; cursor: pointer; }
.file-label.disabled { opacity: 0.6; pointer-events: none; }
.file-label input { display: none; }
.preview {
  display: block;
  width: 100%;
  max-width: 400px;
  max-height: 280px;
  margin: 0 auto;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #eee;
  background: #f5f5f5;
}
.title-input { padding: 0.6rem 0.8rem; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }
button { padding: 0.75rem 1.25rem; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; font-size: 1rem; cursor: pointer; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.error { color: #c00; }
.ocr-overlay { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 1.5rem; background: #f8faff; border-radius: 12px; border: 1px solid #d0e0ff; }
.ocr-stage { position: relative; width: 160px; height: 120px; }
.sheet-fake { position: absolute; inset: 10px 20px; background: linear-gradient(#fff, #f0f0f0); border: 1px solid #ccc; border-radius: 4px; }
.sheet-fake::before { content: ''; position: absolute; left: 12%; right: 12%; top: 28%; height: 3px; background: #ddd; border-radius: 2px; box-shadow: 0 14px 0 #ddd, 0 28px 0 #ddd, 0 42px 0 #e8e8e8; }
.glass { position: absolute; width: 56px; height: 56px; animation: scan 2.2s ease-in-out infinite; }
.glass-lens { width: 40px; height: 40px; border: 4px solid #0d6efd; border-radius: 50%; background: rgba(13, 110, 253, 0.12); }
.glass-handle { position: absolute; width: 6px; height: 22px; background: #0d6efd; border-radius: 3px; right: 2px; bottom: 0; transform: rotate(-45deg); transform-origin: top center; }
@keyframes scan { 0% { left: 8%; top: 12%; } 25% { left: 55%; top: 18%; } 50% { left: 40%; top: 48%; } 75% { left: 15%; top: 55%; } 100% { left: 8%; top: 12%; } }
.ocr-text { margin: 0; font-weight: 600; color: #0d6efd; font-size: 0.95rem; }
</style>
