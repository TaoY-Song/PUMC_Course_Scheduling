import { useMemo, useState } from 'react';
import { PERIODS, WEEKDAY_LABELS, WEEKS, weekSelectionLabel } from '../../lib/time';
import type { TimeSlot } from '../../types/models';

interface TimeSlotEditorProps {
  initialValue?: TimeSlot;
  onSave: (timeSlot: TimeSlot) => void;
  onCancel: () => void;
}

export function TimeSlotEditor({ initialValue, onSave, onCancel }: TimeSlotEditorProps) {
  const [dayOfWeek, setDayOfWeek] = useState(initialValue?.day_of_week ?? 1);
  const [startPeriod, setStartPeriod] = useState(initialValue?.start_period ?? 1);
  const [endPeriod, setEndPeriod] = useState(initialValue?.end_period ?? 2);
  const [selectedWeeks, setSelectedWeeks] = useState<number[]>(initialValue?.weeks ?? []);
  const [error, setError] = useState<string | null>(null);
  const sortedWeeks = useMemo(() => [...selectedWeeks].sort((a, b) => a - b), [selectedWeeks]);

  const toggleWeek = (week: number) => {
    setSelectedWeeks((current) =>
      current.includes(week) ? current.filter((item) => item !== week) : [...current, week],
    );
  };

  const handleSave = () => {
    if (endPeriod < startPeriod) {
      setError('结束节次不能早于开始节次。');
      return;
    }
    if (sortedWeeks.length === 0) {
      setError('至少选择一个上课周次。');
      return;
    }
    setError(null);
    onSave({ day_of_week: dayOfWeek, start_period: startPeriod, end_period: endPeriod, weeks: sortedWeeks });
  };

  const labelClass = 'mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em]';

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-3">
        <label>
          <span className={labelClass} style={{ color: 'var(--text-muted)' }}>星期</span>
          <select value={dayOfWeek} onChange={(e) => setDayOfWeek(Number(e.target.value))} className="input-base">
            {WEEKDAY_LABELS.slice(1).map((label, index) => (
              <option key={label} value={index + 1}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className={labelClass} style={{ color: 'var(--text-muted)' }}>开始节次</span>
          <select
            value={startPeriod}
            onChange={(e) => {
              const next = Number(e.target.value);
              setStartPeriod(next);
              if (endPeriod < next) setEndPeriod(next);
            }}
            className="input-base"
          >
            {PERIODS.map((period) => <option key={period} value={period}>第 {period} 节</option>)}
          </select>
        </label>
        <label>
          <span className={labelClass} style={{ color: 'var(--text-muted)' }}>结束节次</span>
          <select value={endPeriod} onChange={(e) => setEndPeriod(Number(e.target.value))} className="input-base">
            {PERIODS.filter((period) => period >= startPeriod).map((period) => (
              <option key={period} value={period}>第 {period} 节</option>
            ))}
          </select>
        </label>
      </div>

      <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border-subtle)', background: '#faf9f6' }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>上课周次</p>
            <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>{weekSelectionLabel(sortedWeeks)}</p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setSelectedWeeks([...WEEKS])} className="btn-ghost">全选</button>
            <button type="button" onClick={() => setSelectedWeeks([])} className="btn-ghost">清空</button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-5 gap-1.5 sm:grid-cols-10">
          {WEEKS.map((week) => {
            const active = selectedWeeks.includes(week);
            return (
              <button
                key={week}
                type="button"
                aria-pressed={active}
                onClick={() => toggleWeek(week)}
                className="h-9 rounded-md border text-xs font-medium transition"
                style={active
                  ? { borderColor: 'var(--accent-ui)', background: 'var(--accent-ui)', color: 'white' }
                  : { borderColor: 'var(--border-base)', background: 'white', color: 'var(--text-secondary)' }}
              >
                {week}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border px-4 py-3 text-sm"
             style={{ borderColor: '#fca5a5', background: '#fff5f5', color: '#991b1b' }}>
          {error}
        </div>
      )}

      <div className="flex justify-end gap-2 border-t pt-4" style={{ borderColor: 'var(--border-subtle)' }}>
        <button type="button" onClick={onCancel} className="btn-ghost">取消</button>
        <button type="button" onClick={handleSave} className="btn-primary">保存时间段</button>
      </div>
    </div>
  );
}

export default TimeSlotEditor;
