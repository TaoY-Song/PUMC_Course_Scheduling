import type { TimeSlot } from '../types/models';

export const WEEKDAY_LABELS = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'];
export const PERIODS = Array.from({ length: 10 }, (_, index) => index + 1);
export const WEEKS = Array.from({ length: 20 }, (_, index) => index + 1);

export function getWeekdayLabel(day: number): string {
  return WEEKDAY_LABELS[day] || `周${day}`;
}

export function formatWeeks(weeks: number[]): string {
  if (!weeks || weeks.length === 0) {
    return '无周次';
  }

  const sorted = [...new Set(weeks)].sort((left, right) => left - right);
  const ranges: string[] = [];
  let start = sorted[0];
  let end = sorted[0];

  for (let index = 1; index < sorted.length; index += 1) {
    const value = sorted[index];

    if (value === end + 1) {
      end = value;
      continue;
    }

    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    start = value;
    end = value;
  }

  ranges.push(start === end ? `${start}` : `${start}-${end}`);
  return `第 ${ranges.join('、')} 周`;
}

export function formatTimeSlot(slot: TimeSlot): string {
  return `${getWeekdayLabel(slot.day_of_week)} 第 ${slot.start_period}-${slot.end_period} 节 · ${formatWeeks(slot.weeks)}`;
}

export function weekSelectionLabel(selectedWeeks: number[]): string {
  if (!selectedWeeks.length) {
    return '未选择周次';
  }

  if (selectedWeeks.length === WEEKS.length) {
    return '全周';
  }

  return `已选 ${selectedWeeks.length} 周`;
}
