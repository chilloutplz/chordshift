import { ref } from 'vue'
import { apiFetch } from '@/api/api.js'

export function useOcr(props) {
  const ocrLoading = ref(false)
  const ocrError = ref('')
  const ocrQueueInfo = ref(null)
  const ocrHasRun = ref(!!(props.sheet.chords?.length || props.sheet.ocr_raw_text))

  async function runOcr(lines, toLines, askConfirm, onDone) {
    const temp_id = props.sheet.temp_id
    if (!temp_id) { ocrError.value = '임시 ID가 없습니다.'; return }
    if (ocrHasRun.value) {
      const ok = await askConfirm('OCR을 다시 실행하면 지금까지 수정한 코드 내용이 모두 사라집니다. 계속할까요?')
      if (!ok) return
    }
    ocrLoading.value = true
    ocrError.value = ''
    ocrQueueInfo.value = null
    try {
      let res = await apiFetch(`/api/temp/${temp_id}/ocr/`, { method: 'POST' })
      if (res.status === 404) res = await apiFetch(`/api/temp/${temp_id}/ocr-sync/`, { method: 'POST' })
      if (!res.ok) throw new Error((await res.json().catch(()=>({}))).error || `OCR 실패`)
      let data = await res.json()
      if (data.job_id) {
        for (let i=0;i<60;i++) {
          await new Promise(r=>setTimeout(r,1000))
          const jr = await apiFetch(`/api/temp/job/${data.job_id}/`)
          if (!jr.ok) continue
          const jd = await jr.json()
          if (jd.status === 'queued') ocrQueueInfo.value = { status:'queued', aheadCount: jd.ahead_count??0, estimatedWaitSeconds: jd.estimated_wait_seconds }
          if (jd.status === 'processing') ocrQueueInfo.value = { status:'processing' }
          if (jd.status === 'done' && jd.result) { data = jd.result; break }
          if (jd.status === 'failed') throw new Error(jd.error || 'OCR 실패')
        }
      }
      const chords = data.chords || data.result?.chords || []
      if (chords?.length) {
        onDone(chords)
        ocrHasRun.value = true
      } else {
        ocrError.value = 'OCR 결과가 비어있습니다.'
      }
    } catch(e) { ocrError.value = e.message }
    finally { ocrLoading.value = false; ocrQueueInfo.value = null }
  }
  return { ocrLoading, ocrError, ocrQueueInfo, ocrHasRun, runOcr }
}