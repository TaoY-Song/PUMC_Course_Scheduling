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
  return { ...value, [key]: nextValue };
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
    <Surface>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>排课参数</h3>
        <span className="tag tag-gray">CONFIG</span>
      </div>

      <div className="space-y-4">
        {/* Mode toggles */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Credit constraint mode */}
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.15em]"
               style={{ color: 'var(--text-muted)' }}>学分约束</p>
            <div className="grid grid-cols-2 gap-1.5 rounded-lg border p-1"
                 style={{ borderColor: 'var(--border-card)', background: '#f8f7f4' }}>
              {(['REQUIRED', 'OPTIMAL'] as const).map((mode) => {
                const active = value.credit_constraint_mode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => onChange(updateConfig(value, 'credit_constraint_mode', mode))}
                    className="rounded-md px-3 py-2 text-left text-xs font-medium transition-all"
                    style={active
                      ? { background: 'var(--accent-ui)', color: 'white', boxShadow: '0 1px 3px rgba(0,0,0,0.15)' }
                      : { color: 'var(--text-secondary)' }}
                  >
                    <div className="font-semibold">{mode === 'REQUIRED' ? '硬约束' : '优化'}</div>
                    <div className="mt-0.5 opacity-75">
                      {mode === 'REQUIRED' ? '必须满足' : '尽量满足'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Campus conflict mode */}
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.15em]"
               style={{ color: 'var(--text-muted)' }}>校区冲突</p>
            <select
              value={value.campus_conflict_mode}
              onChange={(e) => onChange(updateConfig(value, 'campus_conflict_mode', e.target.value))}
              className="input-base"
            >
              <option value="DAILY">DAILY — 同一天不得跳校区</option>
              <option value="PERIOD">PERIOD — 跳校区需留转场间隔</option>
              <option value="DISABLED">DISABLED — 不检查</option>
            </select>
            {/* PERIOD 按半天时段分块判定，没有可调阈值：能不能赶取决于
                两节课中间有没有午休/晚饭，而不是隔了几节。*/}
            <p className="mt-1.5 text-[11px] leading-5" style={{ color: 'var(--text-muted)' }}>
              {value.campus_conflict_mode === 'DAILY'
                ? '同一天内只允许一个校区的课。'
                : value.campus_conflict_mode === 'PERIOD'
                  ? '同一半天时段内不得跨校区（1-4 上午 / 5-8 下午 / 9-10 晚上）；隔着午休或晚饭则允许。例：1-2 节与 3-4 节不得跨校区，3-4 节与 5-6 节可以。'
                  : '不做校区检查，跟头跟尾的跨校区也会接受。'}
            </p>
          </div>
        </div>

        {/* Numeric fields */}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
          {([
            { key: 'time_limit'            as const, label: '时间限制', unit: 's', min: 10,  max: 300, step: 5    },
            { key: 'max_solutions'         as const, label: '最大解数', unit: '',  min: 1,   max: 10,  step: 1    },
            { key: 'credit_overflow'       as const, label: '溢出学分', unit: '分', min: 0,   max: 10,  step: 0.5  },
          ] as const).map((f) => (
            <label key={f.key}>
              <span className="mb-1 block text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>
                {f.label}{f.unit && <span className="ml-1 opacity-60">({f.unit})</span>}
              </span>
              <input
                type="number"
                min={f.min}
                max={f.max}
                step={f.step}
                value={value[f.key]}
                onChange={(e) =>
                  onChange(updateConfig(value, f.key,
                    f.key === 'credit_overflow'
                      ? Number(e.target.value)
                      : Number.parseInt(e.target.value || '0', 10),
                  ))
                }
                className="input-base"
              />
            </label>
          ))}
        </div>
        <p className="text-[11px] leading-5" style={{ color: 'var(--text-muted)' }}>
          溢出学分：每个类别允许超出要求的学分数。培养方案只规定下限
          （如「限选 {'>='}1 分」），所以适当超出是合规的。若某类别一门都没排上，
          系统会突破此上限收下一门——该类 0 学分比超出更不合规。
        </p>

        {/* Footer */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3"
             style={{ borderColor: 'var(--border-subtle)' }}>
          <Pill tone={isDirty ? 'warning' : 'success'}>
            {isDirty ? '有未保存修改' : '配置已同步'}
          </Pill>
          <div className="flex gap-2">
            <button type="button" onClick={onReset} className="btn-ghost">
              <RotateCcw className="h-3.5 w-3.5" />
              重置
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={!isDirty || isSaving}
              className="btn-primary"
            >
              <Save className="h-3.5 w-3.5" />
              {isSaving ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </Surface>
  );
}
