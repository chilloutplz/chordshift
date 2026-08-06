<script setup>
import { ref, onMounted } from 'vue'
import HomePage from './components/HomePage.vue'
import ChordEditor from './components/ChordEditor.vue'
import TransposePage from './components/TransposePage.vue'
import { apiFetch } from './api/api.js'

// home | correct | transpose
const page = ref('home')
const currentSheet = ref(null)
const ocrUsage = ref(null)

async function loadOcrUsage() {
  try {
    const res = await apiFetch('/api/ocr-usage/')
    if (res.ok) {
      ocrUsage.value = await res.json()
    }
  } catch (_) {
    /* ignore */
  }
}

function openSheet(sheet) {
  currentSheet.value = sheet
  page.value = sheet.result_image || (sheet.variants && sheet.variants.length) ? 'transpose' : 'correct'
}

function onUpdated(sheet) {
  currentSheet.value = sheet
  // OCR 직후 사용량 갱신
  if (sheet?.ocr_usage) {
    ocrUsage.value = sheet.ocr_usage
  } else {
    loadOcrUsage()
  }
}

function backHome() {
  currentSheet.value = null
  page.value = 'home'
  loadOcrUsage()
}

function goTranspose(sheet) {
  if (sheet) currentSheet.value = sheet
  page.value = 'transpose'
}

function goCorrect() {
  page.value = 'correct'
}

onMounted(loadOcrUsage)
</script>

<template>
  <div class="app">
    <header>
      <div class="header-top">
        <div>
          <h1>ChordShift</h1>
          <p class="subtitle">기타 악보 OCR · 조옮김 · 저장</p>
        </div>
        <div
          v-if="ocrUsage"
          class="ocr-badge"
          :class="{ warn: ocrUsage.remaining <= 50, danger: ocrUsage.exceeded }"
          :title="`${ocrUsage.month} 월간 Google Vision OCR 사용량`"
        >
          <span class="ocr-label">OCR</span>
          <span class="ocr-count">{{ ocrUsage.used }} / {{ ocrUsage.limit }}</span>
        </div>
      </div>
    </header>
    <main>
      <HomePage v-if="page === 'home'" @open="openSheet" @usage-updated="loadOcrUsage" />
      <ChordEditor
        v-else-if="page === 'correct' && currentSheet"
        :sheet="currentSheet"
        page-mode="correct"
        @updated="onUpdated"
        @back="backHome"
        @next="goTranspose"
      />
      <TransposePage
        v-else-if="page === 'transpose' && currentSheet"
        :sheet="currentSheet"
        @updated="onUpdated"
        @back="backHome"
        @edit="goCorrect"
      />
    </main>
  </div>
</template>

<style>
.app {
  max-width: 920px;
  margin: 0 auto;
  padding: 1rem;
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.header-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}
header h1 {
  margin: 0;
  font-size: 1.8rem;
  color: #1a1a2e;
}
.subtitle {
  color: #666;
  margin: 0.25rem 0 0;
  font-size: 0.95rem;
}
.ocr-badge {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding: 0.4rem 0.75rem;
  border-radius: 10px;
  background: #f0f4f8;
  border: 1px solid #d0dbe6;
  font-size: 0.8rem;
  color: #334;
  line-height: 1.3;
}
.ocr-badge .ocr-label {
  font-weight: 600;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #667;
}
.ocr-badge .ocr-count {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.ocr-badge.warn {
  background: #fff8e6;
  border-color: #f0d78c;
  color: #8a6d00;
}
.ocr-badge.danger {
  background: #fdecea;
  border-color: #f5c2c0;
  color: #b33;
}
</style>
