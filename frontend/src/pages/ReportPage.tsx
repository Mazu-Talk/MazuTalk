import { useEffect } from 'react'
import { useAppStore } from '@/stores/appStore'
import { useSessionStore } from '@/stores/sessionStore'
import { getScenario } from '@/data/scenarios'
import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/common/Button'
import { ReportView } from '@/features/feedback/ReportView'

export function ReportPage() {
  const navigate = useAppStore((s) => s.navigate)
  const report = useSessionStore((s) => s.report)
  const startSession = useSessionStore((s) => s.startSession)
  const reset = useSessionStore((s) => s.reset)

  // 리포트가 없으면(직접 진입 등) 홈으로
  useEffect(() => {
    if (!report) navigate('home')
  }, [report, navigate])

  if (!report) return null

  const scenario = getScenario(report.scenario_id)

  const handleRetry = async () => {
    if (!scenario) return
    await startSession(scenario)
    navigate('roleplay')
  }

  const handleHome = () => {
    reset()
    navigate('home')
  }

  return (
    <AppLayout
      header={
        <>
          <h1 className="text-2xl font-bold text-brand-700">🎉 오늘의 결과</h1>
          <Button variant="ghost" size="md" icon="🏠" onClick={handleHome}>
            처음으로
          </Button>
        </>
      }
    >
      <ReportView report={report} scenario={scenario} />

      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button size="lg" icon="🔁" onClick={handleRetry} disabled={!scenario}>
          한 번 더 하기
        </Button>
        <Button
          variant="secondary"
          size="lg"
          icon="🎲"
          onClick={() => {
            reset()
            navigate('scenario-select')
          }}
        >
          다른 놀이 하기
        </Button>
      </div>

      <p className="mt-6 text-center text-sm text-brand-400">
        이 결과는 보호자·치료사가 아이의 연습을 살펴볼 수 있도록 만든 참고 자료예요.
        진단이나 평가가 아니랍니다.
      </p>
    </AppLayout>
  )
}
