import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean
}

export function Card({ interactive, className, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-3xl bg-white/85 backdrop-blur p-6 shadow-card',
        interactive &&
          'cursor-pointer transition-transform duration-150 hover:-translate-y-1 hover:shadow-soft active:scale-[0.98] focus-visible:ring-4 focus-visible:ring-brand-300 focus:outline-none',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
