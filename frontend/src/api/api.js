// 배포/로컬 모두 커버
export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export function apiUrl(path) {
  // path는 /api/songs/ 처럼 /로 시작
  if (!path.startsWith('/')) path = '/' + path
  return `${API_BASE}${path}`
}

// 편하게 쓰려고 wrapper
export function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), options)
}