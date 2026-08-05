<script setup>
import UploadScore from './UploadScore.vue'

defineProps({
  initialTitle: { type: String, default: '' },
  initialFile: { type: Object, default: null },
})
const emit = defineEmits(['uploaded', 'back'])
</script>

<template>
  <section class="upload-page">
    <button type="button" class="back" @click="emit('back')">← 검색으로</button>
    <UploadScore :initial-title="initialTitle" :initial-file="initialFile" @uploaded="emit('uploaded', $event)" />
  </section>
</template>

<style scoped>
.upload-page { display: flex; flex-direction: column; gap: 0.75rem; }
.back {
  align-self: flex-start; background: none; border: none;
  cursor: pointer; color: #1a1a2e; font-size: 0.95rem;
}
</style>
