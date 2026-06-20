import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface AppLayoutProps {
  children: ReactNode
  /** roleplay 화면은 몰입을 위해 여백/배경을 다르게 둔다 */
  variant?: 'default' | 'immersive'
  header?: ReactNode
}

export function AppLayout({ children, variant = 'default', header }: AppLayoutProps) {
  return (
    <div className="min-h-full flex flex-col">
      {header && (
        <header className="px-4 sm:px-8 pt-5 pb-2 flex items-center justify-between">
          {header}
        </header>
      )}
      <main
        className={cn(
          'flex-1 w-full mx-auto px-4 sm:px-8',
          variant === 'default' ? 'max-w-5xl py-6' : 'max-w-3xl py-2 flex flex-col',
        )}
      >
        {children}
      </main>
    </div>
  )
}
