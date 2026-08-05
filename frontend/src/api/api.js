// frontend/src/api/api.js - 성역! 절대 하드코딩 금지!
// 백엔드 URL을 환경변수로 관리, apiFetch로만 호출

export const API_BASE = 
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export function apiUrl(path) {
  // path는 반드시 /api/ 로 시작
  if (!path.startsWith('/')) path = '/' + path
  return `${API_BASE}${path}`
}

export function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : apiUrl(path)
  // FormData일 때는 Content-Type 자동 설정되게 헤더 건들지 않음
  return fetch(url, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
  })
}

// --- 분리형 업로드 헬퍼 (프론트에서 이렇게 쓰면 502 해결) ---
export async function uploadAndOcr(file, onProgress) {
  const fd = new FormData()
  fd.append('image', file)
  
  // 1. 업로드만 (1초컷)
  const upRes = await apiFetch('/api/temp/upload/', { method: 'POST', body: fd })
  if (!upRes.ok) throw new Error('업로드 실패: ' + upRes.status)
  const upData = await upRes.json()
  
  // 2. OCR 시작
  const ocrRes = await apiFetch(`/api/temp/${upData.temp_id}/ocr/`, { method: 'POST' })
  if (!ocrRes.ok) throw new Error('OCR 시작 실패')
  const { job_id } = await ocrRes.json()
  
  // 3. 폴링
  while (true) {
    if (onProgress) onProgress('OCR 분석 중...')
    const jobRes = await apiFetch(`/api/temp/job/${job_id}/`)
    const job = await jobRes.json()
    if (job.status === 'done') {
      return { temp_id: upData.temp_id, ...job.result, optimized_image: upData.optimized_image }
    }
    if (job.status === 'failed') throw new Error(job.error || 'OCR 실패')
    await new Promise(r => setTimeout(r, 1500))
  }
}
