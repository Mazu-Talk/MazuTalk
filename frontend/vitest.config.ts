import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// E2E(클라이언트 오케스트레이션 + 리포트) 테스트용 설정.
// VITE_USE_MOCK=true 로 두어 백엔드 없이 MockConnection 으로 전체 대화 흐름을 구동한다.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    env: {
      VITE_USE_MOCK: 'true',
      VITE_API_BASE_URL: '',
    },
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
