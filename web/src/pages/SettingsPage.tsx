import { useEffect, useMemo, useState } from 'react';
import { RefreshCcw, Save, CheckCircle2, AlertCircle } from 'lucide-react';
import { MetricCard, Pill, Surface } from '../components/workbench/atoms';
import {
  CREDIT_CATEGORIES,
  DEFAULT_CREDIT_REQUIREMENTS,
  getCategoryShortLabel,
} from '../lib/categories';
import { getCreditSettings, getCreditStatus, updateCreditSettings } from '../lib/workbenchApi';
import type { CreditRequirement } from '../types/models';

export function SettingsPage() {
  const [requirements, setRequirements] = useState<Record<string, number>>(DEFAULT_CREDIT_REQUIREMENTS);
  const [creditStatus, setCreditStatus] = useState<CreditRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settings, status] = await Promise.all([getCreditSettings(), getCreditStatus()]);
      setRequirements(Object.keys(settings).length > 0 ? settings : DEFAULT_CREDIT_REQUIREMENTS);
      setCreditStatus(status);
      setMessage(null);
    } catch (error) {
      setMessage({ type: 'err', text: error instanceof Error ? error.message : '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData().catch(() => undefined); }, []);

  const totalRequired  = useMemo(() => Object.values(requirements).reduce((s, n) => s + n, 0), [requirements]);
  const totalCompleted = useMemo(() => creditStatus.reduce((s, i) => s + i.completed_credits, 0), [creditStatus]);
  const completionRate = totalRequired === 0 ? 0 : Math.round((totalCompleted / totalRequired) * 100);
  const statusMap = useMemo(() => new Map(creditStatus.map((i) => [i.category, i])), [creditStatus]);

  const handleSave = async () => {
    setSaving(true); setMessage(null);
    try {
      await updateCreditSettings(requirements);
      await loadData();
      setMessage({ type: 'ok', text: '学分要求已保存。' });
    } catch (error) {
      setMessage({ type: 'err', text: error instanceof Error ? error.message : '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setRequirements(DEFAULT_CREDIT_REQUIREMENTS);
    setMessage({ type: 'ok', text: '已恢复默认值，点击保存后生效。' });
  };

  return (
    <div className="space-y-5">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em]"
             style={{ color: 'var(--text-muted)' }}>
            Credit Baseline
          </p>
          <h2 className="mt-0.5 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            学分策略设置
          </h2>
          <p className="mt-1 max-w-xl text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
            默认值是整个学位阶段的培养方案总量；做单学期排课时，请填写本学期尚需完成的学分缺口。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={handleReset} className="btn-ghost">
            <RefreshCcw className="h-3.5 w-3.5" />
            恢复默认
          </button>
          <button type="button" onClick={handleSave} disabled={saving} className="btn-primary">
            <Save className="h-3.5 w-3.5" />
            {saving ? '保存中…' : '保存设置'}
          </button>
        </div>
      </div>

      {/* ── Metrics ─────────────────────────────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="总要求学分"   value={totalRequired.toFixed(1)}  hint="会话目标基线"      tone="pine"  />
        <MetricCard label="当前完成学分" value={totalCompleted.toFixed(1)} hint="已选课程实时计算"  tone="teal"  />
        <MetricCard label="完成率"        value={`${completionRate}%`}       hint="配置 vs 选课差距"  tone="sand"  />
      </div>

      {/* ── Toast ───────────────────────────────────────────────────────── */}
      {message && (
        <div
          className="flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm"
          style={message.type === 'ok'
            ? { borderColor: 'var(--success-border)', background: 'var(--success-bg)', color: 'var(--success-text)' }
            : { borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger-text)' }}
          role={message.type === 'err' ? 'alert' : 'status'}
          aria-live="polite"
        >
          {message.type === 'ok'
            ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            : <AlertCircle   className="mt-0.5 h-4 w-4 shrink-0" />}
          {message.text}
        </div>
      )}

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">

        {/* Left: input grid */}
        <Surface className="min-w-0">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              要求学分配置
            </h3>
            <span className="tag tag-gray shrink-0">CONFIG</span>
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg"
                     style={{ background: 'var(--border-subtle)' }} />
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {CREDIT_CATEGORIES.map((category) => (
                <label
                  key={category}
                  className="group flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors"
                  style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-ui)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {category}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      aria-label={`${category} 要求学分`}
                      value={requirements[category] ?? 0}
                      onChange={(e) =>
                        setRequirements((prev) => ({
                          ...prev,
                          [category]: Math.max(0, Number(e.target.value || 0)),
                        }))
                      }
                      className="input-base w-20 text-right"
                    />
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>学分</span>
                  </div>
                </label>
              ))}
            </div>
          )}
        </Surface>

        {/* Right: live progress */}
        <Surface className="min-w-0">
          <div className="mb-4 flex items-center justify-between gap-2">
            <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              当前完成情况
            </h3>
            <span className="tag tag-teal shrink-0">LIVE</span>
          </div>

          {creditStatus.length === 0 ? (
            <div className="py-8 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
              加载中或暂无数据
            </div>
          ) : (
            <div className="space-y-3">
              {CREDIT_CATEGORIES.map((category) => {
                const item = statusMap.get(category);
                if (!item) return null;
                const pct = item.required_credits === 0
                  ? 100
                  : Math.min(100, (item.completed_credits / item.required_credits) * 100);
                return (
                  <div key={category} className="min-w-0 rounded-lg border px-4 py-3"
                       style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="min-w-0 flex-1 truncate text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                        {getCategoryShortLabel(item.category)}
                      </p>
                      <Pill tone={item.is_completed ? 'success' : 'warning'}>
                        {item.is_completed ? '✓ 完成' : '待补足'}
                      </Pill>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-2.5 h-1.5 overflow-hidden rounded-full"
                         style={{ background: 'var(--border-card)' }}>
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          background: item.is_completed
                            ? 'var(--accent-ui)'
                            : 'linear-gradient(90deg, var(--accent-dark), #14b8a6)',
                        }}
                      />
                    </div>
                    <div className="mt-1.5 flex justify-between text-[11px]"
                         style={{ color: 'var(--text-muted)' }}>
                      <span>{item.completed_credits.toFixed(1)} / {item.required_credits.toFixed(1)} 学分</span>
                      <span>剩 {Math.max(0, item.remaining_credits).toFixed(1)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}
