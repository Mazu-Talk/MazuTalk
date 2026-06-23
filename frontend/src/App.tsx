import { useAppStore } from '@/stores/appStore'
import { HomePage } from '@/pages/HomePage'
import { ScenarioSelectPage } from '@/pages/ScenarioSelectPage'
import { RolePlayPage } from '@/pages/RolePlayPage'
import { ReportPage } from '@/pages/ReportPage'

/** 뷰 상태에 따른 단순 화면 전환 (아동용 단방향 흐름) */
export default function App() {
  const view = useAppStore((s) => s.view)

  switch (view) {
    case 'home':
      return <HomePage />
    case 'scenario-select':
      return <ScenarioSelectPage />
    case 'roleplay':
      return <RolePlayPage />
    case 'report':
      return <ReportPage />
    default:
      return <HomePage />
  }
}
