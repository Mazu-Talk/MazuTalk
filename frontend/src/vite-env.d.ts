/// <reference types="vite/client" />

// VRM 모델을 URL 에셋으로 임포트 (Vite ?url)
declare module '*.vrm?url' {
  const src: string
  export default src
}
