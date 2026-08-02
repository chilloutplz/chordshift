import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 현재 mode(development, production 등)에 맞는 .env 파일을 로드합니다.
  // 세 번째 인자 ''는 VITE_ 접두사 외 모든 변수를 로드하도록 지정합니다.
  const env = loadEnv(mode, process.cwd(), '')

  // .env에 VITE_API_URL이 없으면 기본값으로 'http://127.0.0.1:8000' 사용
  const apiTarget = env.VITE_API_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'), // <- 이게 핵심
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/media': {  // ← 이거 추가!
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})