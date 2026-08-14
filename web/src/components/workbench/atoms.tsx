import type { ReactNode } from 'react';

// ─── Surface ─────────────────────────────────────────────────────────────────
interface SurfaceProps {
  title?: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

export function Surface({ title, eyebrow, children, className = '', action }: SurfaceProps) {
  return (
    <section
      className={`rounded-xl border bg-white shadow-sm ${className}`}
      style={{ borderColor: 'var(--border-card)' }}
    >
      {(title || eyebrow || action) && (
        <div
          className="flex items-center justify-between gap-4 px-5 py-3.5"
          style={{ borderBottom: '1px solid var(--border-subtle)' }}
        >
          <div>
            {eyebrow && (
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em]" style={{ color: 'var(--text-muted)' }}>
                {eyebrow}
              </p>
            )}
            {title && (
              <h3 className="mt-0.5 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {title}
              </h3>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

// ─── MetricCard ───────────────────────────────────────────────────────────────
interface MetricCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: 'pine' | 'teal' | 'amber' | 'sand' | 'ink';
}

export function MetricCard({ label, value, hint, tone = 'sand' }: MetricCardProps) {
  const base = 'rounded-xl px-4 py-4 shadow-sm';
  const toneMap: Record<string, string> = {
    pine:  'metric-pine',
    teal:  'metric-teal',
    amber: 'metric-amber',
    sand:  'metric-sand',
    ink:   'metric-pine',
  };

  return (
    <div className={`${base} ${toneMap[tone]}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] opacity-70">{label}</p>
      <p className="mt-2 text-2xl font-semibold leading-none tabular-nums">{value}</p>
      {hint && <p className="mt-1.5 text-xs leading-5 opacity-65">{hint}</p>}
    </div>
  );
}

// ─── Pill ─────────────────────────────────────────────────────────────────────
interface PillProps {
  children: ReactNode;
  tone?: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  className?: string;
}

const pillClass: Record<string, string> = {
  success: 'tag tag-teal',
  warning: 'tag tag-amber',
  danger:  'tag tag-red',
  info:    'tag tag-blue',
  neutral: 'tag tag-gray',
};

export function Pill({ children, tone = 'neutral', className = '' }: PillProps) {
  return (
    <span className={`${pillClass[tone]} ${className}`}>{children}</span>
  );
}

// ─── SectionTitle ─────────────────────────────────────────────────────────────
interface SectionTitleProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionTitle({ eyebrow, title, description, action }: SectionTitleProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 pb-1">
      <div>
        {eyebrow && (
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em]" style={{ color: 'var(--text-muted)' }}>
            {eyebrow}
          </p>
        )}
        <h2 className="mt-0.5 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h2>
        {description && (
          <p className="mt-1 max-w-2xl text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

// ─── IconChip (kept for compatibility) ───────────────────────────────────────
interface IconChipProps {
  children: ReactNode;
}

export function IconChip({ children }: IconChipProps) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium"
      style={{ borderColor: 'var(--border-base)', color: 'var(--text-secondary)' }}
    >
      {children}
    </span>
  );
}

// ─── Badge (new) ──────────────────────────────────────────────────────────────
interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'teal' | 'amber' | 'red';
}

export function Badge({ children, variant = 'default' }: BadgeProps) {
  const v: Record<string, string> = {
    default: 'tag tag-gray',
    teal:    'tag tag-teal',
    amber:   'tag tag-amber',
    red:     'tag tag-red',
  };
  return <span className={v[variant]}>{children}</span>;
}

// ─── EmptyState ───────────────────────────────────────────────────────────────
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-12 text-center"
         style={{ borderColor: 'var(--border-base)', background: 'rgba(0,0,0,0.01)' }}>
      {icon && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full"
             style={{ background: 'var(--accent-light)', color: 'var(--accent-ui)' }}>
          {icon}
        </div>
      )}
      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{title}</p>
      {description && (
        <p className="max-w-xs text-xs leading-5" style={{ color: 'var(--text-muted)' }}>{description}</p>
      )}
      {action}
    </div>
  );
}

// ─── Separator ────────────────────────────────────────────────────────────────
export function Separator({ className = '' }: { className?: string }) {
  return <hr className={`border-0 border-t ${className}`} style={{ borderColor: 'var(--border-subtle)' }} />;
}
