import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteStaticCopy } from 'vite-plugin-static-copy'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // 표정 인식 모델은 ai/models 를 단일 출처로 두되, 브라우저(onnxruntime-web)가
    // 로드해야 하므로 dev 서빙/빌드 시 프론트 루트(/best.onnx)로 복사한다.
    viteStaticCopy({
      targets: [{ src: '../ai/models/best.onnx', dest: '.' }],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 백엔드(FastAPI)가 준비되면 아래 프록시로 REST/WS를 연결한다.
    // 백엔드가 없을 때는 mock 엔진이 동작하므로 프록시 없이도 UI가 완전히 작동한다.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
