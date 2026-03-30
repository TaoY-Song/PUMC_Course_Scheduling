import { RotateCcw, Save } from 'lucide-react';
import type { SchedulingConfig } from '../../types/models';
import { Pill, Surface } from '../workbench/atoms';

interface SchedulingConfigPanelProps {
  value: SchedulingConfig;
  isDirty: boolean;
  isSaving: boolean;
  onChange: (next: SchedulingConfig) => void;
  onSave: () => void;
  onReset: () => void;
}

function updateConfig(
  value: SchedulingConfig,
  key: keyof SchedulingConfig,
  nextValue: string | number,
): SchedulingConfig {
  return {
    ...value,
    [key]: nextValue,
  };
}

export function SchedulingConfigPanel({
  value,
  isDirty,
  isSaving,
  onChange,
  onSave,
  onReset,
}: SchedulingConfigPanelProps) {
  return (
    <Surface eyebrow="配置" title="排课参数">
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium text-[#24312c]">学分约束模式</span>
            <div className="grid grid-cols-2 gap-2">
              {(['REQUIRED', 'OPTIMAL'] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => onChange(updateConfig(value, 'credit_constraint_mode', mode))}
                  className={`rounded-[1rem] border px-3 py-3 text-left text-sm transition ${
                    value.credit_constraint_mode === mode
                      ? 'border-[#305243] bg-[#173327] text-white shadow-[0_14px_30px_rgba(23,51,39,0.18)]'
                      : 'border-[#d9cdb9] bg-white text-[#435148] hover:bg-[#f7f0e4]'
                  }`}
                >
                  <div className="font-medium">{mode === 'REQUIRED' ? '硬约束' : '优化模式'}</div>
                  <div className="mt-1 text-xs opacity-80">
                    {mode === 'REQUIRED' ? '必须满足学分目标' : '尽量满足学分目标'}
                  </div>
                </button>
              ))}
            </div>
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-[#24312c]">校区冲突模式</span>
            <select
              value={value.campus_conflict_mode}
              onChange={(event) => onChange(updateConfig(value, 'campus_conflict_mode', event.target.value))}
              className="w-full rounded-[1rem] border border-[#d9cdb9] bg-white px-3 py-3 text-sm text-[#24312c] outline-none transition focus:border-[#7c8d6f] focus:ring-2 focus:ring-[#c9d6b9]"
            >
              <option value="DAILY">DAILY - 同一天禁止跨校区</option>
              <option value="PERIOD">PERIOD - 相邻节次禁止跨校区</option>
              <option value="DISABLED">DISABLED - 关闭校区冲突</option>
            </select>
          </label>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            {
              key: 'time_limit' as const,
              label: '时间限制（秒）',
              min: 10,
              max: 300,
              step: 5,
            },
            {
              key: 'max_solutions' as const,
              label: '最大解数',
              min: 1,
              max: 10,
              step: 1,
            },
            {
              key: 'credit_overflow_ratio' as const,
              label: '学分溢出比例',
              min: 0,
              max: 0.5,
              step: 0.05,
            },
            {
              key: 'campus_transition_time' as const,
              label: '校区转换时间（分钟）',
              min: 0,
              max: 120,
              step: 1,
            },
          ].map((field) => (
            <label key={field.key} className="space-y-2">
              <span className="text-sm font-medium text-[#24312c]">{field.label}</span>
              <input
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                value={value[field.key]}
                onChange={(event) =>
                  onChange(
                    updateConfig(
                      value,
                      field.key,
                      field.key === 'credit_overflow_ratio'
                        ? Number(event.target.value)
                        : Number.parseInt(event.target.value || '0', 10),
                    ),
                  )
                }
                className="w-full rounded-[1rem] border border-[#d9cdb9] bg-white px-3 py-3 text-sm text-[#24312c] outline-none transition focus:border-[#7c8d6f] focus:ring-2 focus:ring-[#c9d6b9]"
              />
            </label>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#e6d8bf] pt-4">
          <div className="flex items-center gap-2">
            <Pill tone={isDirty ? 'warning' : 'success'}>
              {isDirty ? '有未保存修改' : '配置已同步'}
            </Pill>
            <span className="text-xs text-[#65726a]">
              建议先保存参数，再启动排课任务，避免前后端配置不一致。
            </span>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-2 rounded-full border border-[#d9cdb9] bg-white px-4 py-2 text-sm font-medium text-[#24312c] transition hover:bg-[#f7f0e4]"
            >
              <RotateCcw className="h-4 w-4" />
              重置
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={!isDirty || isSaving}
              className="inline-flex items-center gap-2 rounded-full bg-[#173327] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#204232] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {isSaving ? '保存中' : '保存配置'}
            </button>
          </div>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingConfigPanel;
