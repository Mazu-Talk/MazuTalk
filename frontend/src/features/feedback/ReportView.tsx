import type { Report, Scenario } from '@/types/domain'
import { EMOTION_META } from '@/constants/labels'
import { Card } from '@/components/common/Card'

interface ReportViewProps {
  report: Report
  scenario?: Scenario
}

/** 학습 리포트 시각화 — FD-07 (막대 그래프 / 감정 추이 / 참여도 게이지) */
export function ReportView({ report, scenario }: ReportViewProps) {
  const dominant = EMOTION_META[report.dominant_emotion]

  return (
    <div className="flex flex-col gap-5">
      {/* 요약 헤더 */}
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-brand-500">오늘의 연습</p>
          <h2 className="text-3xl font-bold text-brand-800">
            {scenario ? `${scenario.emoji} ${scenario.title}` : '대화 연습'}
          </h2>
        </div>
        <div className="flex items-center gap-2 rounded-2xl bg-brand-50 px-5 py-3">
          <span className="text-3xl">{dominant.emoji}</span>
          <div>
            <p className="text-xs text-brand-500">가장 많이 보인 기분</p>
            <p className="text-lg font-bold text-brand-800">{dominant.label}</p>
          </div>
        </div>
      </Card>

      {/* 참여도 + 정면 집중도 게이지 (한 행) */}
      <div className="grid gap-5 md:grid-cols-2">
        <Card className="flex flex-col items-center justify-center gap-2">
          <h3 className="text-lg font-bold text-brand-700">참여도</h3>
          <Gauge value={report.participation_score} suffix="점" />
          <p className="text-base text-brand-600">
            {report.completion_status === 'completed'
              ? '끝까지 잘 해냈어요! 🎉'
              : '오늘도 멋지게 연습했어요 👍'}
          </p>
        </Card>

        <Card className="flex flex-col items-center justify-center gap-2">
          <h3 className="text-lg font-bold text-brand-700">정면 집중도</h3>
          <Gauge value={report.gaze_summary?.center ?? 0} suffix="%" />
          <p className="text-base text-brand-600">
            {report.gaze_summary ? '친구를 잘 바라봤어요 👀' : '시선 데이터가 없어요'}
          </p>
        </Card>
      </div>

      {/* 핵심 지표 3종 (하단 한 행 전체) */}
      <Card>
        <div className="grid gap-5 sm:grid-cols-3">
          <StatBar
            label="총 대화 수"
            value={report.total_turns}
            max={20}
            unit="번"
            emoji="💬"
          />
          <StatBar
            label="평균 대답 시간"
            value={Math.round(report.avg_response_time_ms / 100) / 10}
            max={7}
            unit="초"
            emoji="⏱️"
            invert
          />
          <StatBar
            label="평균 말 길이"
            value={report.avg_utterance_length}
            max={20}
            unit="글자"
            emoji="✍️"
          />
        </div>
      </Card>

      {/* 감정 추이 그래프 */}
      <Card>
        <h3 className="mb-3 text-lg font-bold text-brand-700">기분의 변화 🌈</h3>
        <EmotionTimeline report={report} />
      </Card>
    </div>
  )
}

/** 반원형 게이지 (0~100) — 참여도·정면 집중도 공용 */
function Gauge({ value, suffix = '점' }: { value: number; suffix?: string }) {
  const clamped = Math.max(0, Math.min(100, value))
  const radius = 80
  const circumference = Math.PI * radius
  const offset = circumference * (1 - clamped / 100)
  const color = clamped >= 70 ? '#7bd389' : clamped >= 40 ? '#ffd166' : '#a0c4ff'

  return (
    <div className="relative" style={{ width: 200, height: 120 }}>
      <svg viewBox="0 0 200 110" width="200" height="110">
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="#e6eefb"
          strokeWidth="18"
          strokeLinecap="round"
        />
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke={color}
          strokeWidth="18"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <span className="text-4xl font-extrabold text-brand-800">{clamped}</span>
        <span className="text-lg text-brand-500"> {suffix}</span>
      </div>
    </div>
  )
}

interface StatBarProps {
  label: string
  value: number
  max: number
  unit: string
  emoji: string
  invert?: boolean
}

function StatBar({ label, value, max, unit, emoji, invert }: StatBarProps) {
  const pct = Math.max(4, Math.min(100, (value / max) * 100))
  const good = invert ? value <= max * 0.6 : value >= max * 0.4
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-base text-brand-700">
        <span>
          {emoji} {label}
        </span>
        <span className="font-bold">
          {value}
          {unit}
        </span>
      </div>
      <div className="h-4 w-full overflow-hidden rounded-full bg-brand-50">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${pct}%`,
            backgroundColor: good ? '#3385f6' : '#ffd166',
          }}
        />
      </div>
    </div>
  )
}

/** 턴별 감정 추이 — 점 그래프 */
function EmotionTimeline({ report }: { report: Report }) {
  const points = report.emotion_timeline
  if (points.length === 0) {
    return <p className="text-brand-400">대화 기록이 아직 없어요.</p>
  }

  // 감정을 세로 위치(0=차분 ~ 4=기쁨)에 매핑
  // YOLOv8 감정 클래스(happy, neutral, sad, surprised) 포함
  const order: Record<string, number> = {
    frustrated: 0,
    anxious: 1,
    confused: 1,
    sad: 1,        // YOLOv8 감정 클래스
    passive: 2,
    shy: 2,
    surprised: 2,  // YOLOv8 감정 클래스
    neutral: 3,
    happy: 4,
  }
  const rows = 5
  const colW = 56
  const rowH = 40
  const width = Math.max(points.length * colW, colW)
  const height = rows * rowH

  const coords = points.map((p, i) => ({
    x: i * colW + colW / 2,
    y: (rows - 1 - (order[p.emotion] ?? 3)) * rowH + rowH / 2,
    emotion: p.emotion,
  }))

  const path = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`)
    .join(' ')

  return (
    <div className="overflow-x-auto pb-2">
      <svg width={width} height={height} className="min-w-full">
        {Array.from({ length: rows }).map((_, r) => (
          <line
            key={r}
            x1={0}
            x2={width}
            y1={r * rowH + rowH / 2}
            y2={r * rowH + rowH / 2}
            stroke="#eef3fb"
            strokeWidth={1}
          />
        ))}
        <path d={path} fill="none" stroke="#bcdcff" strokeWidth={4} strokeLinejoin="round" />
        {coords.map((c, i) => (
          <g key={i}>
            <circle cx={c.x} cy={c.y} r={14} fill="white" stroke="#3385f6" strokeWidth={2} />
            <text x={c.x} y={c.y + 6} textAnchor="middle" fontSize={16}>
              {EMOTION_META[c.emotion]?.emoji ?? '😐'}
            </text>
            <text x={c.x} y={height - 4} textAnchor="middle" fontSize={11} fill="#7c93b5">
              {i + 1}턴
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}