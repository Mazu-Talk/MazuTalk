import { useAppStore } from '@/stores/appStore'
import { Button } from '@/components/common/Button'
import { Avatar } from '@/features/voice-interaction/Avatar'

export function HomePage() {
  const navigate = useAppStore((s) => s.navigate)

  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-8 px-6 py-12 text-center">
      <div className="animate-float">
        <Avatar state="happy" name="미래" size={220} />
      </div>

      <div>
        <h1 className="text-5xl font-extrabold tracking-tight text-brand-700">
          마주<span className="text-brand-500">톡</span>
        </h1>
        <p className="mt-3 text-xl text-brand-600">
          친구 미래랑 이야기 연습을 해볼까요?
        </p>
      </div>

      <Button size="xl" icon="🎈" onClick={() => navigate('scenario-select')}>
        시작하기
      </Button>

      <p className="max-w-md text-sm leading-relaxed text-brand-400">
        마주톡은 아이가 또래 친구와 대화하는 방법을 안전하게 연습하도록 돕는 친구예요.
        정답을 맞히는 곳이 아니라, 마음껏 시도해보는 놀이터랍니다.
      </p>
    </div>
  )
}
