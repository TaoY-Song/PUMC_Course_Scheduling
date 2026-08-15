import { Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import type { SchedulingConfig } from '../../types/models';
import { Pill, Surface } from '../workbench/atoms';

interface SchedulingConfigPanelProps {
  value: SchedulingConfig;
  campuses: string[];
  isDirty: boolean;
  isSaving: boolean;
  onChange: (next: SchedulingConfig) => void;
  onSave: () => void;
  onReset: () => void;
}

function updateConfig<K extends keyof SchedulingConfig>(
  value: SchedulingConfig,
  key: K,
  nextValue: SchedulingConfig[K],
): SchedulingConfig {
  return { ...value, [key]: nextValue };
}

export function SchedulingConfigPanel({
  value,
  campuses,
  isDirty,
  isSaving,
  onChange,
  onSave,
  onReset,
}: SchedulingConfigPanelProps) {
  const campusGroups = value.campus_equivalence_groups;
  const campusOptions = Array.from(new Set([...campuses, ...campusGroups.flat()]));
  const assignedCampuses = new Set(campusGroups.flat());
  const invalidCampusGroup = campusGroups.some((group) => group.length < 2)
    || campusGroups.some((group, groupIndex) => group.some((campus) =>
      campusGroups.some((other, otherIndex) => otherIndex !== groupIndex && other.includes(campus))
    ));
  const ungroupedCampuses = campuses.filter((campus) => !assignedCampuses.has(campus));

  const addCampusGroup = () => {
    if (ungroupedCampuses.length < 2) {
      return;
    }
    onChange(updateConfig(value, 'campus_equivalence_groups', [
      ...campusGroups,
      ungroupedCampuses.slice(0, 2),
    ]));
  };

  const removeCampusGroup = (groupIndex: number) => {
    onChange(updateConfig(
      value,
      'campus_equivalence_groups',
      campusGroups.filter((_, index) => index !== groupIndex),
    ));
  };

  const toggleCampus = (groupIndex: number, campus: string, checked: boolean) => {
    if (
      checked
      && campusGroups.some((group, index) => index !== groupIndex && group.includes(campus))
    ) {
      return;
    }

    const nextGroups = campusGroups.map((group, index) => {
      if (index !== groupIndex) {
        return group;
      }
      return checked
        ? [...group, campus]
        : group.filter((item) => item !== campus);
    });
    onChange(updateConfig(value, 'campus_equivalence_groups', nextGroups));
  };

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
                 style={{ borderColor: 'var(--border-card)', background: 'var(--bg-subtle)' }}>
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
              onChange={(e) => onChange(updateConfig(
                value,
                'campus_conflict_mode',
                e.target.value as SchedulingConfig['campus_conflict_mode'],
              ))}
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

        {value.campus_conflict_mode === 'DISABLED' ? (
          <div
            className="rounded-lg border px-3 py-2.5 text-[11px] leading-5"
            style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}
          >
            当前已禁用校区冲突检查。已保存的等价校区组会保留，切回 DAILY 或 PERIOD 后继续生效。
          </div>
        ) : (
          <div
            className="rounded-lg border p-3"
            style={{ borderColor: 'var(--border-card)', background: 'var(--bg-subtle)' }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>等价校区组</p>
                <p className="mt-0.5 text-[11px] leading-5" style={{ color: 'var(--text-muted)' }}>
                  当前已选课程中的组内校区，会按同一校区判断。
                </p>
              </div>
              <button
                type="button"
                className="btn-ghost shrink-0 px-2.5 py-1.5 text-[11px]"
                onClick={addCampusGroup}
                disabled={ungroupedCampuses.length < 2}
                title={ungroupedCampuses.length < 2 ? '至少需要两个未分组校区' : '新建等价校区组'}
              >
                <Plus className="h-3.5 w-3.5" />
                新建组
              </button>
            </div>

            {campusGroups.length === 0 ? (
              <p className="mt-3 rounded-md border border-dashed px-3 py-2 text-[11px]"
                 style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
                {campuses.length < 2
                  ? '当前已选课程中还没有至少两个不同校区。'
                  : '暂无等价组。点击“新建组”后选择需要视为同一校区的课程地点。'}
              </p>
            ) : (
              <div className="mt-3 space-y-2">
                {campusGroups.map((group, groupIndex) => (
                  <div
                    key={`campus-group-${groupIndex}`}
                    role="group"
                    aria-label={`等价组 ${groupIndex + 1}`}
                    className="rounded-md border bg-white/70 px-3 py-2.5"
                    style={{ borderColor: 'var(--border-subtle)' }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] font-semibold" style={{ color: 'var(--text-secondary)' }}>
                        等价组 {groupIndex + 1}
                      </p>
                      <button
                        type="button"
                        className="btn-ghost px-2 py-1 text-[11px] text-rose-600"
                        onClick={() => removeCampusGroup(groupIndex)}
                      >
                        <Trash2 className="h-3 w-3" />
                        删除
                      </button>
                    </div>
                    <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                      {campusOptions.map((campus) => {
                        const checked = group.includes(campus);
                        const inAnotherGroup = campusGroups.some(
                          (other, otherIndex) => otherIndex !== groupIndex && other.includes(campus),
                        );
                        const isStale = !campuses.includes(campus);
                        return (
                          <label
                            key={campus}
                            className="flex min-w-0 items-center gap-2 rounded-md border px-2 py-1.5 text-[11px]"
                            style={{
                              borderColor: checked ? 'var(--accent-ui)' : 'var(--border-subtle)',
                              background: checked ? 'var(--accent-light)' : 'var(--bg-card)',
                              color: inAnotherGroup ? 'var(--text-muted)' : 'var(--text-secondary)',
                              opacity: inAnotherGroup ? 0.55 : 1,
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={inAnotherGroup}
                              onChange={(event) => toggleCampus(groupIndex, campus, event.target.checked)}
                              className="h-3.5 w-3.5 accent-[var(--accent-ui)]"
                            />
                            <span className="min-w-0 flex-1 truncate">{campus}</span>
                            {isStale && <span className="shrink-0 text-[10px] opacity-70">当前未选</span>}
                          </label>
                        );
                      })}
                    </div>
                    {group.length < 2 && (
                      <p className="mt-2 text-[11px]" style={{ color: 'var(--danger-text)' }}>
                        每个等价组至少需要选择两个校区。
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
            {invalidCampusGroup && (
              <p className="mt-2 text-[11px]" style={{ color: 'var(--danger-text)' }}>
                请先修正等价校区组后再保存配置。
              </p>
            )}
          </div>
        )}

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
          <Pill tone={invalidCampusGroup ? 'danger' : isDirty ? 'warning' : 'success'}>
            {invalidCampusGroup ? '等价组配置无效' : isDirty ? '有未保存修改' : '配置已同步'}
          </Pill>
          <div className="flex gap-2">
            <button type="button" onClick={onReset} className="btn-ghost">
              <RotateCcw className="h-3.5 w-3.5" />
              重置
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={!isDirty || isSaving || invalidCampusGroup}
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
