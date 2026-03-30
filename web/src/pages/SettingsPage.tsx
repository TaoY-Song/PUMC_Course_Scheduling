import { useEffect, useMemo, useState } from 'react';
import { RefreshCcw, Save } from 'lucide-react';
import { MetricCard, Pill, SectionTitle, Surface } from '../components/workbench/atoms';
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
  const [message, setMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [settings, status] = await Promise.all([getCreditSettings(), getCreditStatus()]);
      setRequirements(Object.keys(settings).length > 0 ? settings : DEFAULT_CREDIT_REQUIREMENTS);
      setCreditStatus(status);
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '学分设置加载失败。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData().catch(() => undefined);
  }, []);

  const totalRequired = useMemo(
    () => Object.values(requirements).reduce((sum, item) => sum + item, 0),
    [requirements],
  );
  const totalCompleted = useMemo(
    () => creditStatus.reduce((sum, item) => sum + item.completed_credits, 0),
    [creditStatus],
  );
  const completionRate = totalRequired === 0 ? 0 : Math.round((totalCompleted / totalRequired) * 100);
  const statusMap = useMemo(
    () => new Map(creditStatus.map((item) => [item.category, item])),
    [creditStatus],
  );

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await updateCreditSettings(requirements);
      await loadData();
      setMessage('学分要求已保存，并已刷新统计视图。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '保存失败。');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setRequirements(DEFAULT_CREDIT_REQUIREMENTS);
    setMessage('已恢复默认学分要求。点击保存后生效。');
  };

  return (
    <div className="space-y-6">
      <SectionTitle
        eyebrow="Credit Baseline"
        title="学分策略设置"
        description="这一页对应 Qt 的学分设置对话框。后端现在复用同一个 CreditManager，会话内的设置会直接影响统计视图。"
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-2 rounded-full border border-[#d6cab3] bg-white px-4 py-2 text-sm font-medium text-[#3d4a42] transition hover:bg-[#f8efde]"
            >
              <RefreshCcw className="h-4 w-4" />
              恢复默认
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-full border border-[#244f42] bg-[#19362d] px-4 py-2 text-sm font-medium text-[#f8f4ea] transition hover:bg-[#22463a] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Save className="h-4 w-4" />
              {saving ? '保存中...' : '保存设置'}
            </button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="总要求学分" value={`${totalRequired.toFixed(1)}`} hint="当前会话下的目标基线" tone="pine" />
        <MetricCard label="当前完成学分" value={`${totalCompleted.toFixed(1)}`} hint="基于当前已选课程实时计算" tone="amber" />
        <MetricCard label="完成率" value={`${completionRate}%`} hint="用于快速判断配置与选课差距" tone="sand" />
      </div>

      {message && (
        <div className="rounded-[1.2rem] border border-[#d9cfbc] bg-[#fff8ea] px-4 py-3 text-sm text-[#6d6045]">
          {message}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Surface eyebrow="Config" title="要求学分">
          {loading ? (
            <div className="py-8 text-sm text-[#6b766d]">正在拉取学分设置...</div>
          ) : (
            <div className="space-y-4">
              {CREDIT_CATEGORIES.map((category) => (
                <label
                  key={category}
                  className="flex flex-col gap-3 rounded-[1.25rem] border border-[#e7dcc8] bg-white/85 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <div className="font-medium text-[#1b2822]">{category}</div>
                    <div className="mt-1 text-sm text-[#67736a]">用于 REQUIRED / OPTIMAL 模式的学分目标。</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={requirements[category] ?? 0}
                      onChange={(event) =>
                        setRequirements((current) => ({
                          ...current,
                          [category]: Math.max(0, Number(event.target.value || 0)),
                        }))
                      }
                      className="w-24 rounded-2xl border border-[#d7ccb8] bg-[#fffdfa] px-3 py-2 text-right text-sm text-[#17211d] outline-none transition focus:border-[#8f7441] focus:ring-2 focus:ring-[#d8c39a]"
                    />
                    <span className="text-sm text-[#67736a]">学分</span>
                  </div>
                </label>
              ))}
            </div>
          )}
        </Surface>

        <Surface eyebrow="Live Summary" title="当前完成情况">
          <div className="space-y-3">
            {CREDIT_CATEGORIES.map((category) => {
              const item = statusMap.get(category);
              if (!item) {
                return null;
              }

              return (
                <div key={item.category} className="rounded-[1.2rem] border border-[#e7dcc8] bg-white/85 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-[#19251f]">{getCategoryShortLabel(item.category)}</div>
                      <div className="mt-1 text-xs text-[#6c766d]">{item.category}</div>
                    </div>
                    <Pill tone={item.is_completed ? 'success' : 'warning'}>
                      {item.is_completed ? '已完成' : '仍需补足'}
                    </Pill>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#efe7d8]">
                    <div
                      className="h-full rounded-full bg-[linear-gradient(90deg,#1b4334,#c6943a)]"
                      style={{
                        width: `${Math.min(
                          100,
                          item.required_credits === 0
                            ? 100
                            : (item.completed_credits / item.required_credits) * 100,
                        )}%`,
                      }}
                    />
                  </div>
                  <div className="mt-3 flex items-center justify-between text-sm text-[#606a62]">
                    <span>
                      {item.completed_credits.toFixed(1)} / {item.required_credits.toFixed(1)} 学分
                    </span>
                    <span>剩余 {Math.max(0, item.remaining_credits).toFixed(1)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Surface>
      </div>
    </div>
  );
}
