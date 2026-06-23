/**
 * REST API 클라이언트 — ARCHITECTURE.md §8.1
 *
 * 백엔드가 없을 때(USE_MOCK)는 로컬 시나리오 데이터와 메모리 세션으로 동작한다.
 * 백엔드가 준비되면 USE_MOCK=false 로 두고 동일한 시그니처로 실제 호출한다.
 */
import type { Report, Scenario, Session } from '@/types/domain'
import { REST_BASE, USE_MOCK, uid } from './config'
import { SCENARIOS, getScenario } from '@/data/scenarios'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${REST_BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return (await res.json()) as T
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${REST_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`)
  return (await res.json()) as T
}

/** GET /api/scenarios */
export async function fetchScenarios(): Promise<Scenario[]> {
  return SCENARIOS
}

/** GET /api/scenarios/{id} */
export async function fetchScenario(id: string): Promise<Scenario | undefined> {
  return getScenario(id)
}

/** POST /api/sessions */
export async function createSession(
  scenarioId: string,
  childId = 'anonymous',
): Promise<Session> {
  if (USE_MOCK) {
    return {
      session_id: uid('session'),
      child_id: childId,
      scenario_id: scenarioId,
      started_at: new Date().toISOString(),
      status: 'active',
    }
  }
  return postJson<Session>('/sessions', {
    scenario_id: scenarioId,
    child_id: childId,
  })
}

/** POST /api/sessions/{id}/end */
export async function endSession(
  sessionId: string,
  status: 'completed' | 'interrupted' = 'completed',
): Promise<void> {
  if (USE_MOCK) return
  await postJson(`/sessions/${sessionId}/end`, { status })
}

/** GET /api/reports/{session_id} */
export async function fetchReport(sessionId: string): Promise<Report> {
  // mock 모드에서는 리포트를 클라이언트(sessionStore)에서 계산하므로 호출되지 않는다.
  return getJson<Report>(`/reports/${sessionId}`)
}
