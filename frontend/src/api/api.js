import axios from 'axios'

/**
 * Cloudtype 배포 환경 및 로컬 개발 환경을 지원하는 Axios 인스턴스
 *
 * 1. 배포 환경 (npm run build):
 *    Cloudtype 프론트엔드 환경변수 VITE_API_URL 값을 최우선 적용합니다.
 * 2. 개발 환경 (npm run dev):
 *    VITE_API_URL이 없을 경우 상대 경로 ''(또는 '/api')를 사용하여
 *    vite.config.js의 proxy 설정을 타도록 동작합니다.
 */

// 백엔드 Base URL 설정
const baseURL = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: baseURL,
  timeout: 10000, // 10초 타임아웃
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// [요청 인터셉터] - 토큰(JWT 등)이 필요한 경우 자동 첨부
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// [응답 인터셉터] - 공통 에러 처리 (401 Unauthorized 등)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // 필요 시 로그인 페이지 이동 처리
      // window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api