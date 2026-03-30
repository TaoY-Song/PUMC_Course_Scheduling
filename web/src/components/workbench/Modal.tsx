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
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      <button
        type="button"
        aria-label="关闭弹窗"
        className="absolute inset-0 bg-[#09110f]/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className={`relative z-10 w-full ${widthClassName} overflow-hidden rounded-[1.75rem] border border-[#d7cbb4] bg-[#fffaf0] shadow-[0_30px_90px_rgba(5,15,12,0.28)]`}>
        <div className="flex items-start justify-between gap-4 border-b border-[#eadfcb] px-6 py-5">
          <div>
            <h3 className="text-xl font-semibold text-[#17221d]">{title}</h3>
            {description && <p className="mt-1 text-sm leading-6 text-[#637268]">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[#d7cbb4] bg-white p-2 text-[#5e665f] transition hover:bg-[#f4ebdc]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[78vh] overflow-y-auto px-6 py-5">
          {children}
        </div>

        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-[#eadfcb] px-6 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
