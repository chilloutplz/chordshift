<script setup>
import { ref } from 'vue'
import HomePage from './components/HomePage.vue'
import ChordEditor from './components/ChordEditor.vue'
import TransposePage from './components/TransposePage.vue'

// home | correct | transpose
const page = ref('home')
const currentSheet = ref(null)

function openSheet(sheet) {
  currentSheet.value = sheet
  // 이미 결과 있으면 조옮김 페이지, 아니면 보정
  page.value = sheet.result_image ? 'transpose' : 'correct'
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
      <nav v-if="page !== 'home'" class="steps">
        <button type="button" :class="{ on: page === 'correct' }" @click="goCorrect">2. 보정·확정</button>
        <button type="button" :class="{ on: page === 'transpose' }" @click="goTranspose()">3. 조옮김·저장</button>
      </nav>
    </header>

    <main>
      <HomePage
        v-if="page === 'home'"
        @open="openSheet"
        @uploaded="onUploaded"
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
.steps { display: flex; justify-content: center; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
.steps button {
  padding: 0.4rem 0.8rem; border: 1px solid #ccc; border-radius: 20px;
  background: #fff; cursor: pointer; font-size: 0.85rem;
}
.steps button.on { background: #0d6efd; color: #fff; border-color: #0d6efd; }
</style>
