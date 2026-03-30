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

  const sortedWeeks = useMemo(
    () => [...selectedWeeks].sort((left, right) => left - right),
    [selectedWeeks],
  );

  const toggleWeek = (week: number) => {
    setSelectedWeeks((current) =>
      current.includes(week)
        ? current.filter((item) => item !== week)
        : [...current, week],
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
    onSave({
      day_of_week: dayOfWeek,
      start_period: startPeriod,
      end_period: endPeriod,
      weeks: sortedWeeks,
    });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.24em] text-[#85785f]">星期</span>
          <select
            value={dayOfWeek}
            onChange={(event) => setDayOfWeek(Number(event.target.value))}
            className="w-full rounded-2xl border border-[#d7ccb8] bg-[#fffdfa] px-3 py-2.5 text-sm text-[#17211d] outline-none transition focus:border-[#8f7441] focus:ring-2 focus:ring-[#dcc79f]"
          >
            {WEEKDAY_LABELS.slice(1).map((label, index) => (
              <option key={label} value={index + 1}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.24em] text-[#85785f]">开始节次</span>
          <select
            value={startPeriod}
            onChange={(event) => {
              const nextValue = Number(event.target.value);
              setStartPeriod(nextValue);
              if (endPeriod < nextValue) {
                setEndPeriod(nextValue);
              }
            }}
            className="w-full rounded-2xl border border-[#d7ccb8] bg-[#fffdfa] px-3 py-2.5 text-sm text-[#17211d] outline-none transition focus:border-[#8f7441] focus:ring-2 focus:ring-[#dcc79f]"
          >
            {PERIODS.map((period) => (
              <option key={period} value={period}>
                第 {period} 节
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2">
          <span className="text-xs uppercase tracking-[0.24em] text-[#85785f]">结束节次</span>
          <select
            value={endPeriod}
            onChange={(event) => setEndPeriod(Number(event.target.value))}
            className="w-full rounded-2xl border border-[#d7ccb8] bg-[#fffdfa] px-3 py-2.5 text-sm text-[#17211d] outline-none transition focus:border-[#8f7441] focus:ring-2 focus:ring-[#dcc79f]"
          >
            {PERIODS.filter((period) => period >= startPeriod).map((period) => (
              <option key={period} value={period}>
                第 {period} 节
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="rounded-[1.35rem] border border-[#e7dcc8] bg-[#fffdf8] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-[#1a2620]">上课周次</div>
            <div className="mt-1 text-xs text-[#6d776d]">{weekSelectionLabel(sortedWeeks)}</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSelectedWeeks([...WEEKS])}
              className="rounded-full border border-[#d6cab3] bg-white px-3 py-1.5 text-xs font-medium text-[#455147] transition hover:bg-[#f8efde]"
            >
              全选
            </button>
            <button
              type="button"
              onClick={() => setSelectedWeeks([])}
              className="rounded-full border border-[#d6cab3] bg-white px-3 py-1.5 text-xs font-medium text-[#455147] transition hover:bg-[#f8efde]"
            >
              清空
            </button>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-5 gap-2 sm:grid-cols-10">
          {WEEKS.map((week) => {
            const active = selectedWeeks.includes(week);

            return (
              <button
                key={week}
                type="button"
                onClick={() => toggleWeek(week)}
                className={[
                  'h-10 rounded-xl border text-sm font-medium transition',
                  active
                    ? 'border-[#1d4a3b] bg-[#17382e] text-[#f7f2e8]'
                    : 'border-[#ddd1bd] bg-white text-[#3e4942] hover:bg-[#f8efde]',
                ].join(' ')}
              >
                {week}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      )}

      <div className="flex justify-end gap-3 border-t border-[#eadfcb] pt-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full border border-[#d6cab3] bg-white px-4 py-2 text-sm font-medium text-[#435047] transition hover:bg-[#f8efde]"
        >
          取消
        </button>
        <button
          type="button"
          onClick={handleSave}
          className="rounded-full border border-[#1f4739] bg-[#17362d] px-4 py-2 text-sm font-medium text-[#f8f4ea] transition hover:bg-[#21463a]"
        >
          保存时间段
        </button>
      </div>
    </div>
  );
}

export default TimeSlotEditor;
