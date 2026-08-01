<script setup>
import { ref } from 'vue'
import HomePage from './components/HomePage.vue'
import UploadPage from './components/UploadPage.vue'
import ChordEditor from './components/ChordEditor.vue'
import TransposePage from './components/TransposePage.vue'

// home | upload | correct | transpose
const page = ref('home')
const currentSheet = ref(null)
const uploadHintTitle = ref('')

function openSheet(sheet) {
  currentSheet.value = sheet
  page.value = sheet.result_image || (sheet.variants && sheet.variants.length)
    ? 'transpose'
    : 'correct'
}

function goUpload(titleHint = '') {
  uploadHintTitle.value = typeof titleHint === 'string' ? titleHint : ''
  page.value = 'upload'
}

function onUploaded(sheet) {
  currentSheet.value = sheet
  page.value = 'correct'
}

function onUpdated(sheet) {
  currentSheet.value = sheet
}

function backHome() {
  currentSheet.value = null
  uploadHintTitle.value = ''
  page.value = 'home'
}

function goTranspose(sheet) {
  if (sheet) currentSheet.value = sheet
  page.value = 'transpose'
}

function goCorrect() {
  page.value = 'correct'
}
</script>

<template>
  <div class="app">
    <header>
      <h1>ChordShift</h1>
      <p class="subtitle">기타 악보 OCR · 조옮김 · 저장</p>
    </header>

    <main>
      <HomePage
        v-if="page === 'home'"
        @open="openSheet"
        @go-upload="goUpload"
      />
      <UploadPage
        v-else-if="page === 'upload'"
        :initial-title="uploadHintTitle"
        @uploaded="onUploaded"
        @back="backHome"
      />
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
  font-family: system-ui, -apple-system, sans-serif;
}
header { text-align: center; margin-bottom: 1.25rem; }
header h1 { margin: 0; font-size: 1.8rem; color: #1a1a2e; }
.subtitle { color: #666; margin-top: 0.25rem; }
</style>
