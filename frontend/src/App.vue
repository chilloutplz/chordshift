<script setup>
import { ref, onMounted } from 'vue'
import HomePage from './components/HomePage.vue'
import ChordEditor from './components/ChordEditor.vue'
import TransposePage from './components/TransposePage.vue'
import HelpPage from './components/HelpPage.vue'
import { apiFetch } from './api/api.js'

/**
 * 커피 한 잔 기부 링크
 * - Buy Me a Coffee: https://www.buymeacoffee.com/아이디
 * - Ko-fi: https://ko-fi.com/아이디
 * - 토스 송금 등 원하는 URL로 바꾸세요
 */
const COFFEE_URL = 'https://www.buymeacoffee.com/chordshift'

const page = ref('home')
const currentSheet = ref(null)
const ocrUsage = ref(null)
const previousPage = ref('home') // 도움말 진입 전 화면 - 도움말에서 뒤로가면 여기로 복귀

async function loadOcrUsage() {
  try {
    const res = await apiFetch('/api/ocr-usage/')
    if (res.ok) ocrUsage.value = await res.json()
  } catch (_) {}
}

function openSheet(sheet) {
  currentSheet.value = sheet
  // 새 업로드(임시) → 보정 화면 / 목록에서 고른 저장곡 → 조옮김 화면
  // 조옮김에서 「보정으로」링크 → 보정 화면 (goCorrect)
  const isTemp = !!(sheet.is_temp || sheet.temp_id)
  page.value = isTemp ? 'correct' : 'transpose'
}

function onUpdated(sheet) {
  currentSheet.value = sheet
  if (sheet?.ocr_usage) ocrUsage.value = sheet.ocr_usage
  else loadOcrUsage()
}

function openHelp() {
  previousPage.value = page.value
  page.value = 'help'
}
function closeHelp() {
  page.value = previousPage.value
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
    <header class="topbar">
      <button type="button" class="brand" @click="backHome" :title="page !== 'home' ? '홈으로' : ''">
        <img src="/icons/icon-96x96.png" alt="" class="logo" width="38" height="38" />
        <span class="brand-text">
          <span class="name">ChordShift</span>
          <span class="tag">기타 악보 OCR · 조옮김</span>
        </span>
      </button>

      <div class="topbar-actions">
        <button type="button" class="help-link" title="사용법" aria-label="사용법" @click="openHelp">?</button>
        <div
          v-if="ocrUsage"
          class="ocr-badge"
          :class="{ warn: ocrUsage.remaining <= 50, danger: ocrUsage.exceeded }"
          :title="`${ocrUsage.month} 월간 OCR 사용량`"
        >
          <span class="ocr-label">OCR</span>
          <span class="ocr-count">{{ ocrUsage.used }} / {{ ocrUsage.limit }}</span>
        </div>
      </div>
    </header>

    <main class="main">
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
      <HelpPage v-else-if="page === 'help'" @back="closeHelp" />
    </main>

    <footer class="foot">
      <a
        class="credit"
        :href="COFFEE_URL"
        target="_blank"
        rel="noopener noreferrer"
        title="Uncle Bob"
      >
        <img src="/coffee/coffee-48.png" alt="" class="coffee-icon" width="18" height="18" />
        2026 Uncle Bob
      </a>
    </footer>
  </div>
</template>

<style>
.app {
  max-width: 960px;
  margin: 0 auto;
  padding: 0.75rem 1rem 2rem;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 0 1rem;
  margin-bottom: 0.25rem;
  border-bottom: 1px solid var(--border, #e2e6ef);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  border: none;
  background: transparent;
  padding: 0;
  text-align: left;
  cursor: pointer;
}
.brand:hover .name {
  color: var(--primary, #2563eb);
}
.logo {
  width: 2.4rem;
  height: 2.4rem;
  border-radius: 10px;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
  display: block;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}
.name {
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text, #1a1d26);
  letter-spacing: -0.02em;
  line-height: 1.2;
  transition: color 0.15s;
}
.tag {
  font-size: 0.75rem;
  color: var(--text-muted, #5c6578);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.help-link {
  width: 1.85rem;
  height: 1.85rem;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--border-strong, #c8d0e0);
  background: var(--surface, #fff);
  color: var(--text-muted, #5c6578);
  font-weight: 800;
  font-size: 0.95rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.help-link:hover {
  border-color: var(--primary, #2563eb);
  color: var(--primary, #2563eb);
  background: var(--primary-soft, #eff4ff);
}

.ocr-badge {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding: 0.35rem 0.65rem;
  border-radius: 10px;
  background: #f0f4f8;
  border: 1px solid #d0dbe6;
  font-size: 0.75rem;
  color: #334;
  line-height: 1.25;
}
.ocr-badge .ocr-label {
  font-weight: 700;
  font-size: 0.65rem;
  letter-spacing: 0.04em;
  color: #667;
  text-transform: uppercase;
}
.ocr-badge .ocr-count {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
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

.main {
  flex: 1;
  padding-top: 1rem;
}

.foot {
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border, #e2e6ef);
  display: flex;
  justify-content: center;
}

.credit {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: #7a8294;
  text-decoration: none;
  letter-spacing: 0.01em;
  font-weight: 500;
  transition: color 0.15s, opacity 0.15s;
}
.credit:hover {
  color: #5c6578;
}
.coffee-icon {
  display: block;
  opacity: 0.85;
  transition: opacity 0.15s;
}
.credit:hover .coffee-icon {
  opacity: 1;
}

@media (max-width: 480px) {
  .tag {
    display: none;
  }
}
</style>
