import type { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';

interface SurfaceProps {
  title?: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

export function Surface({ title, eyebrow, children, className = '', action }: SurfaceProps) {
  return (
    <section className={`rounded-[1.5rem] border border-[#d5ccb8] bg-[#fffaf0]/95 shadow-[0_24px_80px_rgba(20,34,28,0.08)] backdrop-blur ${className}`}>
      {(title || eyebrow || action) && (
        <div className="flex items-start justify-between gap-4 border-b border-[#eadfcb] px-5 py-4">
          <div>
            {eyebrow && (
              <p className="text-[0.7rem] uppercase tracking-[0.3em] text-[#7f7259]">
                {eyebrow}
              </p>
            )}
            {title && (
              <h3 className="mt-1 text-lg font-semibold text-[#17221d]">{title}</h3>
            )}
          </div>
          {action}
        </div>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

interface MetricCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: 'pine' | 'amber' | 'sand' | 'ink';
}

const metricTone: Record<NonNullable<MetricCardProps['tone']>, string> = {
  pine: 'from-[#153128] to-[#2f5d50] text-white',
  amber: 'from-[#9c6a1d] to-[#c58f3a] text-white',
  sand: 'from-[#f4efe2] to-[#ede2cc] text-[#2a322d]',
  ink: 'from-[#101d1a] to-[#263832] text-white',
};

export function MetricCard({ label, value, hint, tone = 'sand' }: MetricCardProps) {
  return (
    <div className={`rounded-[1.25rem] border border-[#ddd0ba] bg-gradient-to-br ${metricTone[tone]} px-4 py-4 shadow-[0_18px_45px_rgba(20,34,28,0.08)]`}>
      <div className="text-[0.68rem] uppercase tracking-[0.28em] opacity-80">{label}</div>
      <div className="mt-3 break-words text-2xl font-semibold leading-[1.08]">{value}</div>
      {hint && <div className="mt-2 break-all text-sm leading-5 opacity-80">{hint}</div>}
    </div>
  );
}

interface PillProps {
  children: ReactNode;
  tone?: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  className?: string;
}

const pillTone: Record<NonNullable<PillProps['tone']>, string> = {
  success: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  warning: 'bg-amber-100 text-amber-900 border-amber-200',
  danger: 'bg-rose-100 text-rose-900 border-rose-200',
  info: 'bg-sky-100 text-sky-900 border-sky-200',
  neutral: 'bg-[#efe6d6] text-[#445047] border-[#dccfb8]',
};

export function Pill({ children, tone = 'neutral', className = '' }: PillProps) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[0.72rem] font-medium ${pillTone[tone]} ${className}`}>
      {children}
    </span>
  );
}

interface SectionTitleProps {
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionTitle({ eyebrow, title, description, action }: SectionTitleProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-[0.72rem] uppercase tracking-[0.36em] text-[#8c7f67]">{eyebrow}</p>
        <h2 className="mt-2 text-2xl font-semibold text-[#18241f]">{title}</h2>
        {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-[#58645b]">{description}</p>}
      </div>
      {action}
    </div>
  );
}

interface IconChipProps {
  children: ReactNode;
}

export function IconChip({ children }: IconChipProps) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[#d8cfbc] bg-white/80 px-3 py-1 text-xs font-medium text-[#39433c] shadow-sm">
      <ChevronRight className="h-3 w-3" />
      {children}
    </span>
  );
}
