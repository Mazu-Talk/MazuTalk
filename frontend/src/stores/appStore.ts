import { create } from 'zustand'

/** 단순 뷰 기반 라우팅 (라우터 의존성 없이 아동용 단방향 흐름을 표현) */
export type View = 'home' | 'scenario-select' | 'roleplay' | 'report'

interface AppState {
  view: View
  navigate: (view: View) => void
}

export const useAppStore = create<AppState>((set) => ({
  view: 'home',
  navigate: (view) => set({ view }),
}))
