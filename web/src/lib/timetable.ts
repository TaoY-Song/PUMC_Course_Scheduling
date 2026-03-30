import type { SelectedCourse, TimeSlot } from '../types/models';

export type TimetableWeekFilter = 'all' | number;

export interface TimetableOccurrence {
  id: string;
  courseId: string;
  courseCode: string;
  courseName: string;
  teacher?: string;
  department?: string;
  category?: string;
  credits: number;
  campus?: string;
  isOnline: boolean;
  dayOfWeek: number;
  startPeriod: number;
  endPeriod: number;
  weeks: number[];
  timeSlotIndex: number;
  course: SelectedCourse;
}

export interface TimetableOccurrenceLayout extends TimetableOccurrence {
  laneIndex: number;
  laneCount: number;
}

export interface TimetableDayLayout {
  dayOfWeek: number;
  label: string;
  blocks: TimetableOccurrenceLayout[];
}

export interface TimetableModel {
  weekFilter: TimetableWeekFilter;
  weeks: number[];
  totalPeriods: number;
  dayLayouts: TimetableDayLayout[];
  onlineCourses: SelectedCourse[];
  floatingCourses: SelectedCourse[];
  visibleCourses: SelectedCourse[];
}

export interface CourseColorTokens {
  background: string;
  border: string;
  accent: string;
  shadow: string;
  text: string;
}

export const DAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'] as const;
export const DEFAULT_TOTAL_PERIODS = 10;

function uniqueSorted(values: number[]): number[] {
  return Array.from(new Set(values.filter((value) => Number.isFinite(value) && value > 0))).sort((a, b) => a - b);
}

function hashString(input: string): number {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  }
  return hash;
}

export function getCourseColorTokens(seed: string): CourseColorTokens {
  const hash = hashString(seed || 'PUMC');
  const hue = hash % 360;
  const accentHue = (hue + 18) % 360;

  return {
    background: `linear-gradient(135deg, hsla(${hue}, 46%, 26%, 0.96), hsla(${accentHue}, 44%, 34%, 0.92))`,
    border: `hsla(${hue}, 28%, 18%, 0.45)`,
    accent: `hsla(${hue}, 50%, 72%, 0.95)`,
    shadow: `0 16px 28px hsla(${hue}, 34%, 18%, 0.18)`,
    text: '#ffffff',
  };
}

function isWeekVisible(weeks: number[], weekFilter: TimetableWeekFilter): boolean {
  if (weekFilter === 'all') {
    return true;
  }

  if (weeks.length === 0) {
    return true;
  }

  return weeks.includes(weekFilter);
}

function hasTimeSlotOverlap(left: TimetableOccurrence, right: TimetableOccurrence): boolean {
  if (left.dayOfWeek !== right.dayOfWeek) {
    return false;
  }

  const weeksA = left.weeks;
  const weeksB = right.weeks;
  const weeksOverlap =
    weeksA.length === 0 ||
    weeksB.length === 0 ||
    weeksA.some((week) => weeksB.includes(week));

  if (!weeksOverlap) {
    return false;
  }

  return !(left.endPeriod < right.startPeriod || right.endPeriod < left.startPeriod);
}

function buildOccurrence(course: SelectedCourse, timeSlot: TimeSlot, timeSlotIndex: number): TimetableOccurrence {
  const courseCode = course.course.course_code || course.id;
  return {
    id: `${course.id}-${timeSlotIndex}`,
    courseId: course.id,
    courseCode,
    courseName: course.course.course_name,
    teacher: course.course.teacher,
    department: course.course.department,
    category: course.custom_category || course.course.category,
    credits: course.course.credits,
    campus: course.course.campus,
    isOnline: course.is_online || course.course.is_online,
    dayOfWeek: timeSlot.day_of_week,
    startPeriod: timeSlot.start_period,
    endPeriod: timeSlot.end_period,
    weeks: uniqueSorted(timeSlot.weeks),
    timeSlotIndex,
    course,
  };
}

function assignLanes(blocks: TimetableOccurrence[]): TimetableOccurrenceLayout[] {
  if (blocks.length === 0) {
    return [];
  }

  const sorted = [...blocks].sort((left, right) => {
    if (left.startPeriod !== right.startPeriod) {
      return left.startPeriod - right.startPeriod;
    }
    if (left.endPeriod !== right.endPeriod) {
      return left.endPeriod - right.endPeriod;
    }
    if (left.courseCode !== right.courseCode) {
      return left.courseCode.localeCompare(right.courseCode);
    }
    return left.timeSlotIndex - right.timeSlotIndex;
  });

  const adjacency = new Map<string, Set<string>>();
  for (let leftIndex = 0; leftIndex < sorted.length; leftIndex += 1) {
    const left = sorted[leftIndex];
    for (let rightIndex = leftIndex + 1; rightIndex < sorted.length; rightIndex += 1) {
      const right = sorted[rightIndex];
      if (hasTimeSlotOverlap(left, right)) {
        if (!adjacency.has(left.id)) {
          adjacency.set(left.id, new Set());
        }
        if (!adjacency.has(right.id)) {
          adjacency.set(right.id, new Set());
        }
        adjacency.get(left.id)?.add(right.id);
        adjacency.get(right.id)?.add(left.id);
      }
    }
  }

  const visited = new Set<string>();
  const layouts: TimetableOccurrenceLayout[] = [];

  for (const block of sorted) {
    if (visited.has(block.id)) {
      continue;
    }

    const stack = [block];
    const component: TimetableOccurrence[] = [];
    visited.add(block.id);

    while (stack.length > 0) {
      const current = stack.pop();
      if (!current) {
        continue;
      }
      component.push(current);

      const neighbours = adjacency.get(current.id);
      if (!neighbours) {
        continue;
      }

      for (const neighbourId of neighbours) {
        if (visited.has(neighbourId)) {
          continue;
        }
        const neighbour = sorted.find((item) => item.id === neighbourId);
        if (neighbour) {
          visited.add(neighbourId);
          stack.push(neighbour);
        }
      }
    }

    const lanes: TimetableOccurrence[][] = [];
    const componentSorted = [...component].sort((left, right) => {
      if (left.startPeriod !== right.startPeriod) {
        return left.startPeriod - right.startPeriod;
      }
      if (left.endPeriod !== right.endPeriod) {
        return left.endPeriod - right.endPeriod;
      }
      return left.courseCode.localeCompare(right.courseCode);
    });

    for (const item of componentSorted) {
      let laneIndex = 0;
      while (laneIndex < lanes.length) {
        const lane = lanes[laneIndex];
        const conflict = lane.some((existing) => hasTimeSlotOverlap(existing, item));
        if (!conflict) {
          break;
        }
        laneIndex += 1;
      }

      if (laneIndex === lanes.length) {
        lanes.push([item]);
      } else {
        lanes[laneIndex].push(item);
      }
    }

    const laneCount = Math.max(1, lanes.length);
    for (const [laneIndex, laneItems] of lanes.entries()) {
      for (const item of laneItems) {
        layouts.push({
          ...item,
          laneIndex,
          laneCount,
        });
      }
    }
  }

  return layouts.sort((left, right) => {
    if (left.dayOfWeek !== right.dayOfWeek) {
      return left.dayOfWeek - right.dayOfWeek;
    }
    if (left.startPeriod !== right.startPeriod) {
      return left.startPeriod - right.startPeriod;
    }
    if (left.laneIndex !== right.laneIndex) {
      return left.laneIndex - right.laneIndex;
    }
    return left.courseCode.localeCompare(right.courseCode);
  });
}

export function formatWeekSummary(weeks: number[]): string {
  const ordered = uniqueSorted(weeks);
  if (ordered.length === 0) {
    return '全周';
  }

  const segments: string[] = [];
  let start = ordered[0];
  let previous = ordered[0];

  for (let index = 1; index < ordered.length; index += 1) {
    const current = ordered[index];
    if (current === previous + 1) {
      previous = current;
      continue;
    }

    segments.push(start === previous ? `${start}` : `${start}-${previous}`);
    start = current;
    previous = current;
  }

  segments.push(start === previous ? `${start}` : `${start}-${previous}`);
  return segments.join(', ');
}

export function formatTimeSlot(slot: TimeSlot): string {
  return `${DAY_LABELS[Math.max(0, Math.min(6, slot.day_of_week - 1))]} ${slot.start_period}-${slot.end_period}节 · ${formatWeekSummary(slot.weeks)}`;
}

export function formatCourseSchedule(course: SelectedCourse): string {
  if (course.is_online || course.course.is_online) {
    return '线上课程';
  }

  if (!course.time_slots.length) {
    return '暂无时间安排';
  }

  return course.time_slots.map((slot) => formatTimeSlot(slot)).join('；');
}

export function buildAcademicTimetable(
  courses: SelectedCourse[],
  weekFilter: TimetableWeekFilter = 'all',
): TimetableModel {
  const visibleCourses = courses;
  const onlineCourses = courses.filter((course) => course.is_online || course.course.is_online);
  const floatingCourses = courses.filter(
    (course) => !course.is_online && !course.course.is_online && course.time_slots.length === 0,
  );

  const allWeeks = uniqueSorted(
    visibleCourses.flatMap((course) => course.time_slots.flatMap((slot) => uniqueSorted(slot.weeks))),
  );

  const occurrences = visibleCourses.flatMap((course) =>
    course.time_slots.flatMap((slot, timeSlotIndex) => {
      const occurrence = buildOccurrence(course, slot, timeSlotIndex);
      if (!isWeekVisible(occurrence.weeks, weekFilter)) {
        return [];
      }
      if (course.is_online || course.course.is_online) {
        return [];
      }
      return [occurrence];
    }),
  );

  const maxPeriod = Math.max(DEFAULT_TOTAL_PERIODS, ...occurrences.map((occurrence) => occurrence.endPeriod));

  const dayLayouts: TimetableDayLayout[] = [];
  for (let dayOfWeek = 1; dayOfWeek <= 7; dayOfWeek += 1) {
    const dayBlocks = occurrences.filter((occurrence) => occurrence.dayOfWeek === dayOfWeek);
    dayLayouts.push({
      dayOfWeek,
      label: DAY_LABELS[dayOfWeek - 1],
      blocks: assignLanes(dayBlocks),
    });
  }

  return {
    weekFilter,
    weeks: allWeeks,
    totalPeriods: maxPeriod,
    dayLayouts,
    onlineCourses,
    floatingCourses,
    visibleCourses,
  };
}
