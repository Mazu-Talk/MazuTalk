/**
 * API 동작 모드.
 *
 * USE_MOCK = true  → 백엔드 없이 브라우저 내장 STT/TTS + mock 엔진으로 동작
 * USE_MOCK = false → 실제 FastAPI/WebSocket 백엔드에 연결 (vite proxy 사용)
 *
 * VITE_USE_MOCK 환경변수로 덮어쓸 수 있다.
 */
const env = import.meta.env as Record<string, string | undefined>

export const USE_MOCK = env.VITE_USE_MOCK === 'true'

const apiOrigin = (env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export const REST_BASE = env.VITE_API_BASE ?? `${apiOrigin}/api/v1`
export const WS_BASE =
  env.VITE_WS_BASE ??
  (apiOrigin
    ? `${apiOrigin.replace(/^http/, 'ws')}/api/v1`
    : `ws://${location.host}/api/v1`)

/** 고유 ID 생성 (브라우저 런타임) */
export function uid(prefix: string): string {
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().slice(0, 8)
      : Math.random().toString(16).slice(2, 10)
  return `${prefix}_${rand}`
}
