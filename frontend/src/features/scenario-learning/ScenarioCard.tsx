import type { Scenario } from '@/types/domain'
import { DIFFICULTY_META, SKILL_LABEL } from '@/constants/labels'
import { Card } from '@/components/common/Card'

interface ScenarioCardProps {
  scenario: Scenario
  onSelect: (scenario: Scenario) => void
}

export function ScenarioCard({ scenario, onSelect }: ScenarioCardProps) {
  const difficulty = DIFFICULTY_META[scenario.difficulty]

  return (
    <Card
      interactive
      role="button"
      tabIndex={0}
      aria-label={`${scenario.title} 시나리오 시작하기`}
      onClick={() => onSelect(scenario)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(scenario)
        }
      }}
      className="flex flex-col gap-3"
    >
      <div className="flex items-start justify-between">
        <div
          className="grid h-20 w-20 place-items-center rounded-2xl text-5xl"
          style={{ backgroundColor: `${scenario.accent}55` }}
        >
          {scenario.emoji}
        </div>
        <span
          className="rounded-full px-3 py-1 text-sm font-semibold text-brand-800"
          style={{ backgroundColor: `${difficulty.color}66` }}
        >
          {'⭐'.repeat(difficulty.stars)} {difficulty.label}
        </span>
      </div>

      <div>
        <h3 className="text-2xl font-bold text-brand-800">{scenario.title}</h3>
        <p className="mt-1 text-base text-brand-600">{scenario.description}</p>
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-1 text-sm text-brand-500">
        <span className="rounded-full bg-brand-50 px-3 py-1">📍 {scenario.location}</span>
        <span className="rounded-full bg-brand-50 px-3 py-1">
          🎯 {SKILL_LABEL[scenario.target_skill]}
        </span>
      </div>
    </Card>
  )
}
