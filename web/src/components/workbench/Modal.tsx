import type { ReactNode } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
  title: string;
  description?: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  widthClassName?: string;
}

export function Modal({
  title,
  description,
  open,
  onClose,
  children,
  footer,
  widthClassName = 'max-w-3xl',
}: ModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <button
        type="button"
        aria-label="关闭弹窗"
        className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        className={`relative z-10 w-full ${widthClassName} overflow-hidden rounded-xl border bg-white shadow-2xl`}
        style={{ borderColor: 'var(--border-base)' }}
      >
        <div className="flex items-start justify-between gap-4 border-b px-5 py-4"
             style={{ borderColor: 'var(--border-card)', background: '#faf9f6' }}>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--text-muted)' }}>Dialog</p>
            <h3 id="modal-title" className="mt-0.5 text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
            {description && <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>{description}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="关闭" className="btn-ghost p-2">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[78vh] overflow-y-auto px-5 py-5">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t px-5 py-4"
               style={{ borderColor: 'var(--border-card)', background: '#faf9f6' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
