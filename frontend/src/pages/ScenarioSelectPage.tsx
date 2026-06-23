import { useEffect, useState } from 'react'
import type { Scenario } from '@/types/domain'
import { fetchScenarios } from '@/api/client'
import { useAppStore } from '@/stores/appStore'
import { useSessionStore } from '@/stores/sessionStore'
import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/common/Button'
import { ScenarioCard } from '@/features/scenario-learning/ScenarioCard'

export function ScenarioSelectPage() {
  const navigate = useAppStore((s) => s.navigate)
  const startSession = useSessionStore((s) => s.startSession)

  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    let active = true
    fetchScenarios()
      .then((data) => active && setScenarios(data))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  const handleSelect = async (scenario: Scenario) => {
    if (starting) return
    setStarting(true)
    await startSession(scenario)
    navigate('roleplay')
  }

  return (
    <AppLayout
      header={
        <>
          <Button variant="ghost" size="md" icon="←" onClick={() => navigate('home')}>
            처음으로
          </Button>
          <h1 className="text-2xl font-bold text-brand-700">무슨 놀이를 해볼까?</h1>
          <span className="w-24" aria-hidden />
        </>
      }
    >
      {loading ? (
        <p className="py-20 text-center text-xl text-brand-400">불러오는 중...</p>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {scenarios.map((scenario) => (
            <ScenarioCard
              key={scenario.scenario_id}
              scenario={scenario}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}
    </AppLayout>
  )
}
