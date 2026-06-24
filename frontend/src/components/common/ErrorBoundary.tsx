// frontend/src/components/common/ErrorBoundary.tsx
// [역할] 렌더/이펙트에서 throw가 나도 앱 전체가 하얗게 비지 않도록 잡아
// 에러 메시지를 화면에 표시한다. (디버깅 + 사용자 안내 겸용)

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}
interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 콘솔에도 남겨 원인 추적을 돕는다.
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleReset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-brand-50 p-6 text-center">
        <p className="text-4xl">😵</p>
        <h1 className="text-xl font-bold text-brand-800">화면을 그리다가 문제가 생겼어요</h1>
        <pre className="max-w-xl overflow-auto whitespace-pre-wrap rounded-2xl bg-white p-4 text-left text-sm text-red-600 shadow-card">
          {error.message}
          {error.stack ? `\n\n${error.stack}` : ''}
        </pre>
        <button
          onClick={this.handleReset}
          className="rounded-2xl bg-brand-500 px-6 py-3 text-lg font-bold text-white shadow-soft active:scale-95"
        >
          다시 시도
        </button>
      </div>
    )
  }
}

export default ErrorBoundary
