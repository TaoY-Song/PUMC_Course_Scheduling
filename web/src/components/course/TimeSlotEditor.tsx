import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CalendarClock, Info } from 'lucide-react';
import { PERIODS, WEEKDAY_LABELS, WEEKS, formatWeeks, weekSelectionLabel } from '../../lib/time';
import type { TimeSlot } from '../../types/models';

interface TimeSlotEditorProps {
  initialValue?: TimeSlot;
  /** 同一门课已有的其它时间段，用于「例外周」自动扣周 */
  siblingSlots?: TimeSlot[];
  /** 正在编辑的下标；新增时为 null。扣周时要跳过自己 */
  editingIndex?: number | null;
  onSave: (timeSlot: TimeSlot, options: { exceptionOf: number | null }) => void;
  onCancel: () => void;
}

interface DragState {
  anchor: number;
  current: number;
  /** true = 刷选，false = 刷取消。由锚点原本的状态决定 */
  additive: boolean;
  moved: boolean;
}

function rangeBetween(a: number, b: number): number[] {
  const [low, high] = a <= b ? [a, b] : [b, a];
  return Array.from({ length: high - low + 1 }, (_, index) => low + index);
}

export function TimeSlotEditor({
  initialValue,
  siblingSlots = [],
  editingIndex = null,
  onSave,
  onCancel,
}: TimeSlotEditorProps) {
  const [dayOfWeek, setDayOfWeek] = useState(initialValue?.day_of_week ?? 1);
  const [startPeriod, setStartPeriod] = useState(initialValue?.start_period ?? 1);
  const [endPeriod, setEndPeriod] = useState(initialValue?.end_period ?? 2);
  const [selectedWeeks, setSelectedWeeks] = useState<number[]>(initialValue?.weeks ?? []);
  const [error, setError] = useState<string | null>(null);
  // 「例外周」模式：这个时间段是某个常规时间段在特定几周的替代安排。
  // 保存时会把这些周从常规段里扣掉——一门课同一周不会既在上午又在晚上。
  const [exceptionOf, setExceptionOf] = useState<number | null>(null);

  const [drag, setDrag] = useState<DragState | null>(null);
  const dragRef = useRef<DragState | null>(null);

  useEffect(() => {
    dragRef.current = drag;
  }, [drag]);

  const baseSet = useMemo(() => new Set(selectedWeeks), [selectedWeeks]);

  /** 拖拽过程中的预览：把待生效的区间叠加到已选集合上 */
  const previewSet = useMemo(() => {
    if (!drag) return baseSet;
    const next = new Set(baseSet);
    for (const week of rangeBetween(drag.anchor, drag.current)) {
      if (drag.additive) next.add(week);
      else next.delete(week);
    }
    return next;
  }, [baseSet, drag]);

  const previewWeeks = useMemo(
    () => [...previewSet].sort((a, b) => a - b),
    [previewSet],
  );

  const commitDrag = useCallback(() => {
    const state = dragRef.current;
    dragRef.current = null;
    setDrag(null);
    if (!state) return;
    // 没有移动过 → 交给 onClick 处理单击切换，避免双重触发
    if (!state.moved) return;

    setSelectedWeeks((current) => {
      const next = new Set(current);
      for (const week of rangeBetween(state.anchor, state.current)) {
        if (state.additive) next.add(week);
        else next.delete(week);
      }
      return [...next].sort((a, b) => a - b);
    });
  }, []);

  // 指针可能在网格外抬起，必须挂到 window 才不会漏掉收尾
  useEffect(() => {
    if (!drag) return;
    const handleUp = () => commitDrag();
    window.addEventListener('pointerup', handleUp);
    window.addEventListener('pointercancel', handleUp);
    return () => {
      window.removeEventListener('pointerup', handleUp);
      window.removeEventListener('pointercancel', handleUp);
    };
  }, [drag, commitDrag]);

  const toggleWeek = (week: number) => {
    setSelectedWeeks((current) =>
      current.includes(week) ? current.filter((item) => item !== week) : [...current, week].sort((a, b) => a - b),
    );
  };

  /** 触摸端 pointerenter 不可靠，改为按坐标反查格子上的 data-week */
  const handleGridPointerMove = (event: React.PointerEvent) => {
    if (!dragRef.current) return;
    const element = document.elementFromPoint(event.clientX, event.clientY);
    const raw = element?.closest('[data-week]')?.getAttribute('data-week');
    if (!raw) return;
    const week = Number(raw);
    if (!Number.isFinite(week) || week === dragRef.current.current) return;
    setDrag((state) => (state ? { ...state, current: week, moved: true } : state));
  };

  const handleSave = () => {
    if (endPeriod < startPeriod) {
      setError('结束节次不能早于开始节次。');
      return;
    }
    if (selectedWeeks.length === 0) {
      setError('至少选择一个上课周次。');
      return;
    }
    if (exceptionOf !== null) {
      const base = siblingSlots[exceptionOf];
      if (!base) {
        setError('作为例外的常规时间段已不存在，请重新选择。');
        return;
      }
      const covered = selectedWeeks.filter((week) => base.weeks.includes(week));
      if (covered.length === 0) {
        setError('例外周必须落在所选常规时间段的周次范围内。');
        return;
      }
    }
    setError(null);
    onSave(
      {
        day_of_week: dayOfWeek,
        start_period: startPeriod,
        end_period: endPeriod,
        weeks: [...selectedWeeks].sort((a, b) => a - b),
      },
      { exceptionOf },
    );
  };

  const labelClass = 'mb-1 block text-[11px] font-semibold uppercase tracking-[0.16em]';
  // 编辑已有段时不提供「设为例外」——避免自己扣自己
  const canBeException = editingIndex === null && siblingSlots.length > 0;
  const baseSlot = exceptionOf !== null ? siblingSlots[exceptionOf] : null;
  const remainingBaseWeeks = baseSlot
    ? baseSlot.weeks.filter((week) => !selectedWeeks.includes(week))
    : [];

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

      {/* 例外周：这个时段是某个常规时段在特定几周的替代安排 */}
      {canBeException && (
        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border-subtle)', background: '#faf9f6' }}>
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={exceptionOf !== null}
              onChange={(e) => setExceptionOf(e.target.checked ? 0 : null)}
              className="mt-0.5 h-4 w-4 shrink-0"
              style={{ accentColor: 'var(--accent-ui)' }}
            />
            <span className="min-w-0">
              <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                <CalendarClock className="h-3.5 w-3.5" />
                这几周改到别的时间上（例外周）
              </span>
              <span className="mt-0.5 block text-xs leading-5" style={{ color: 'var(--text-muted)' }}>
                例如常规是周四上午，但第 15、17 周改到晚上。保存时会自动把这几周从常规时间段里去掉。
              </span>
            </span>
          </label>

          {exceptionOf !== null && (
            <div className="mt-3 space-y-2 border-t pt-3" style={{ borderColor: 'var(--border-subtle)' }}>
              <label>
                <span className={labelClass} style={{ color: 'var(--text-muted)' }}>替代哪个常规时间段</span>
                <select
                  value={exceptionOf}
                  onChange={(e) => setExceptionOf(Number(e.target.value))}
                  className="input-base"
                >
                  {siblingSlots.map((slot, index) => (
                    <option key={index} value={index}>
                      {WEEKDAY_LABELS[slot.day_of_week]} 第 {slot.start_period}-{slot.end_period} 节 · {formatWeeks(slot.weeks)}
                    </option>
                  ))}
                </select>
              </label>
              {baseSlot && (
                <div
                  className="flex items-start gap-2 rounded-md px-3 py-2 text-[11px] leading-5"
                  style={{ background: 'var(--accent-light)', color: 'var(--accent-dark)' }}
                  role="status"
                >
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    保存后常规时间段变为 <strong>{formatWeeks(remainingBaseWeeks)}</strong>
                    {remainingBaseWeeks.length === 0 && '（已无剩余周次，等于整段被替换）'}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border-subtle)', background: '#faf9f6' }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {exceptionOf !== null ? '例外周次' : '上课周次'}
            </p>
            <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
              {weekSelectionLabel(previewWeeks)}
              <span className="ml-1.5 opacity-70">· 可按住拖动连选</span>
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setSelectedWeeks([...WEEKS])} className="btn-ghost">全选</button>
            <button type="button" onClick={() => setSelectedWeeks([])} className="btn-ghost">清空</button>
          </div>
        </div>
        <div
          onPointerMove={handleGridPointerMove}
          className="mt-3 grid grid-cols-5 gap-1.5 select-none sm:grid-cols-10"
          style={{ touchAction: 'none' }}
        >
          {WEEKS.map((week) => {
            const active = previewSet.has(week);
            const inBaseSlot = baseSlot?.weeks.includes(week) ?? false;
            return (
              <button
                key={week}
                type="button"
                data-week={week}
                aria-pressed={active}
                onPointerDown={(event) => {
                  event.preventDefault();
                  const next: DragState = {
                    anchor: week,
                    current: week,
                    additive: !baseSet.has(week),
                    moved: false,
                  };
                  dragRef.current = next;
                  setDrag(next);
                }}
                onClick={() => {
                  // 拖过就由 commitDrag 负责，单击才走这里
                  if (dragRef.current?.moved) return;
                  toggleWeek(week);
                }}
                className="h-9 rounded-md border text-xs font-medium transition"
                style={
                  active
                    ? { borderColor: 'var(--accent-ui)', background: 'var(--accent-ui)', color: 'white' }
                    : {
                        // 例外模式下，常规段覆盖到的周次做浅色提示：这些才是可替代的范围
                        borderColor: inBaseSlot ? 'var(--accent-ui)' : 'var(--border-base)',
                        background: inBaseSlot ? 'var(--accent-light)' : 'white',
                        color: 'var(--text-secondary)',
                      }
                }
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
