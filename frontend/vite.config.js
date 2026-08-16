import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig(({ mode }) => {
  // 현재 mode(development, production 등)에 맞는 .env 파일을 로드합니다.
  // 세 번째 인자 ''는 VITE_ 접두사 외 모든 변수를 로드하도록 지정합니다.
  const env = loadEnv(mode, process.cwd(), '')

  // .env에 VITE_API_URL이 없으면 기본값으로 'http://127.0.0.1:8000' 사용
  const apiTarget = env.VITE_API_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
        manifest: {
          name: 'ChordShift',
          short_name: 'ChordShift',
          description: '기타 악보 OCR · 조옮김',
          lang: 'ko',
          start_url: '/',
          display: 'standalone',
          background_color: '#3b5bdb',
          theme_color: '#2563eb',
          orientation: 'any',
          icons: [
            { src: '/icons/icon-72x72.png', sizes: '72x72', type: 'image/png' },
            { src: '/icons/icon-96x96.png', sizes: '96x96', type: 'image/png' },
            { src: '/icons/icon-128x128.png', sizes: '128x128', type: 'image/png' },
            { src: '/icons/icon-144x144.png', sizes: '144x144', type: 'image/png' },
            { src: '/icons/icon-152x152.png', sizes: '152x152', type: 'image/png' },
            { src: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/icon-384x384.png', sizes: '384x384', type: 'image/png' },
            { src: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icons/maskable-icon-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
            { src: '/icons/maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          // 빌드 산출물(js/css/html/이미지) 프리캐시
          globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
          // 백엔드가 다른 오리진(API 서버)이어도 same-scope 페이지의 요청은 SW가 가로챌 수 있음
          runtimeCaching: [
            {
              // 곡 목록/상세 조회(GET)만 캐시 - 쓰기 요청(POST/PATCH/DELETE)은 절대 캐시하지 않음
              urlPattern: ({ url, request }) =>
                request.method === 'GET' && url.pathname.startsWith('/api/songs'),
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-songs-cache',
                networkTimeoutSeconds: 5,
                expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 }, // 1일
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // 악보 원본/변형 이미지 - 자주 안 바뀌니 캐시 우선
              urlPattern: ({ url, request }) =>
                request.method === 'GET' &&
                (url.pathname.startsWith('/media/') || url.pathname.startsWith('/api/files/')),
              handler: 'CacheFirst',
              options: {
                cacheName: 'images-cache',
                expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 }, // 30일
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
        },
        devOptions: {
          // 개발 중엔 SW 캐시 때문에 최신 코드가 안 보이는 혼란을 피하려고 기본은 꺼둠.
          // 서비스워커 자체를 로컬에서 테스트하고 싶으면 true로.
          enabled: false,
        },
      }),
    ],
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