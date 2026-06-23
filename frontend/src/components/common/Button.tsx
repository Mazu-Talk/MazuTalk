import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'md' | 'lg' | 'xl'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  icon?: ReactNode
  fullWidth?: boolean
}

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-500 text-white shadow-soft hover:bg-brand-600 active:bg-brand-700',
  secondary:
    'bg-white text-brand-700 border-2 border-brand-200 hover:border-brand-300 hover:bg-brand-50',
  ghost: 'bg-transparent text-brand-700 hover:bg-brand-50',
  danger: 'bg-emotion-frustrated text-white hover:brightness-95',
}

// NFR-004(큰 버튼) — 기본도 충분히 크게
const SIZES: Record<Size, string> = {
  md: 'text-lg px-5 py-3 rounded-2xl gap-2',
  lg: 'text-xl px-7 py-4 rounded-2xl gap-2.5',
  xl: 'text-2xl px-9 py-5 rounded-3xl gap-3',
}

export function Button({
  variant = 'primary',
  size = 'lg',
  icon,
  fullWidth,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-semibold',
        'transition-all duration-150 select-none',
        'focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-300',
        'disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none',
        'active:scale-95',
        VARIANTS[variant],
        SIZES[size],
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {icon && <span aria-hidden className="text-[1.2em] leading-none">{icon}</span>}
      {children}
    </button>
  )
}
