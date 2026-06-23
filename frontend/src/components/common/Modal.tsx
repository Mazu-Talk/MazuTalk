import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { Button } from './Button'

interface ModalProps {
  open: boolean
  title: string
  children?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel?: () => void
  tone?: 'default' | 'danger'
}

/** 아동/보호자용 확인 모달. 큰 버튼, 단순 메시지. */
export function Modal({
  open,
  title,
  children,
  confirmLabel = '확인',
  cancelLabel,
  onConfirm,
  onCancel,
  tone = 'default',
}: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onCancel) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-brand-900/30 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onCancel}
    >
      <div
        className="surface w-full max-w-md p-7 animate-pop-in"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-2xl font-bold text-brand-800">{title}</h2>
        {children && <div className="mt-3 text-lg text-brand-700/90">{children}</div>}
        <div className="mt-7 flex gap-3 justify-end">
          {cancelLabel && onCancel && (
            <Button variant="secondary" onClick={onCancel}>
              {cancelLabel}
            </Button>
          )}
          <Button variant={tone === 'danger' ? 'danger' : 'primary'} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
