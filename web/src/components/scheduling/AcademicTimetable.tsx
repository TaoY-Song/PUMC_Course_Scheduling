import { CalendarDays, Layers3 } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  buildAcademicTimetable,
  formatWeekSummary,
  getCourseColorTokens,
  type TimetableWeekFilter,
} from '../../lib/timetable';
import type { SelectedCourse } from '../../types/models';
import { Pill, Surface } from '../workbench/atoms';

interface AcademicTimetableProps {
  courses: SelectedCourse[];
  title?: string;
  description?: string;
  defaultWeekFilter?: TimetableWeekFilter;
}

const ROW_HEIGHT = 52;

export function AcademicTimetable({
  courses,
  title = '周课表',
  description = '支持周次筛选、冲突分栏和线上课程独立展示。',
  defaultWeekFilter = 'all',
}: AcademicTimetableProps) {
  const [weekFilter, setWeekFilter] = useState<TimetableWeekFilter>(defaultWeekFilter);
  const model = useMemo(() => buildAcademicTimetable(courses, weekFilter), [courses, weekFilter]);
  const rowCount = Math.max(1, model.totalPeriods);
  const boardHeight = rowCount * ROW_HEIGHT;

  return (
    <Surface>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h3>
            <span className="tag tag-gray">TIMETABLE</span>
          </div>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>{description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Pill tone="neutral">{weekFilter === 'all' ? '全部周' : `第 ${weekFilter} 周`}</Pill>
          <select
            aria-label="筛选课表周次"
            value={String(weekFilter)}
            onChange={(event) => {
              const next = event.target.value;
              setWeekFilter(next === 'all' ? 'all' : Number(next));
            }}
            className="input-base w-auto py-1.5"
          >
            <option value="all">全部周</option>
            {model.weeks.map((week) => <option key={week} value={week}>第 {week} 周</option>)}
          </select>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px]" style={{ color: 'var(--text-muted)' }}>
        <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />7 × {rowCount} 网格</span>
        <span aria-hidden="true">·</span>
        <span className="inline-flex items-center gap-1"><Layers3 className="h-3.5 w-3.5" />冲突自动分栏</span>
      </div>

      {courses.length === 0 ? (
        <div className="rounded-lg border border-dashed py-10 text-center text-xs"
             style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
          当前没有课程。执行排课后将在此显示周课表。
        </div>
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--border-card)' }}>
            <div className="min-w-[980px]">
              <div className="grid grid-cols-[3.5rem_repeat(7,minmax(8.25rem,1fr))] border-b"
                   style={{ borderColor: 'var(--border-card)', background: '#f8f7f4' }}>
                <div className="border-r px-2 py-2 text-[10px] font-semibold uppercase tracking-[0.18em]"
                     style={{ borderColor: 'var(--border-card)', color: 'var(--text-muted)' }}>
                  节次
                </div>
                {model.dayLayouts.map((day) => (
                  <div key={day.dayOfWeek} className="border-r px-3 py-2 text-xs font-semibold last:border-r-0"
                       style={{ borderColor: 'var(--border-card)', color: 'var(--text-primary)' }}>
                    {day.label}
                  </div>
                ))}
              </div>

              <div className="flex">
                <div className="relative w-14 shrink-0 border-r" style={{ height: boardHeight, borderColor: 'var(--border-card)', background: '#f8f7f4' }}>
                  {Array.from({ length: rowCount }, (_, index) => (
                    <div key={index} className="absolute left-0 flex w-full items-center justify-center border-b font-mono text-[10px]"
                         style={{ top: index * ROW_HEIGHT, height: ROW_HEIGHT, borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
                      {index + 1}
                    </div>
                  ))}
                </div>

                <div className="grid flex-1 grid-cols-7" style={{ height: boardHeight }}>
                  {model.dayLayouts.map((day) => (
                    <div
                      key={day.dayOfWeek}
                      className="relative border-r last:border-r-0"
                      style={{
                        height: boardHeight,
                        borderColor: 'var(--border-card)',
                        backgroundColor: '#fff',
                        backgroundImage: `repeating-linear-gradient(to bottom, var(--border-subtle) 0, var(--border-subtle) 1px, transparent 1px, transparent ${ROW_HEIGHT}px)`,
                      }}
                    >
                      {day.blocks.map((block) => {
                        const tokens = getCourseColorTokens(block.courseCode);
                        const top = (block.startPeriod - 1) * ROW_HEIGHT + 3;
                        const height = Math.max(ROW_HEIGHT * (block.endPeriod - block.startPeriod + 1) - 6, 36);
                        const left = (block.laneIndex / block.laneCount) * 100;
                        const width = 100 / block.laneCount;
                        return (
                          <div
                            key={block.id}
                            className="absolute overflow-hidden rounded-md border px-2 py-1.5 text-[10px] leading-4 transition-transform hover:-translate-y-px"
                            style={{
                              top, height,
                              left: `calc(${left}% + 3px)`,
                              width: `calc(${width}% - 6px)`,
                              background: tokens.background,
                              borderColor: tokens.border,
                              color: tokens.text,
                              boxShadow: tokens.shadow,
                            }}
                            title={`${block.courseCode} ${block.courseName}`}
                          >
                            <p className="font-mono font-semibold">{block.courseCode}</p>
                            <p className="truncate font-medium">{block.courseName}</p>
                            {height > 55 && (
                              <p className="mt-0.5 truncate opacity-80">
                                {block.startPeriod}-{block.endPeriod}节 · {formatWeekSummary(block.weeks)}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {(model.onlineCourses.length > 0 || model.floatingCourses.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2">
              <CourseBucket title="线上课程" courses={model.onlineCourses} online />
              <CourseBucket title="无时间安排" courses={model.floatingCourses} />
            </div>
          )}
          <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            周次筛选仅影响当前展示，不会修改排课结果。
          </p>
        </div>
      )}
    </Surface>
  );
}

function CourseBucket({ title, courses, online = false }: { title: string; courses: SelectedCourse[]; online?: boolean }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: 'var(--border-subtle)', background: '#faf9f6' }}>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--text-muted)' }}>{title}</p>
      {courses.length === 0 ? (
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>无</p>
      ) : (
        <div className="space-y-1.5">
          {courses.map((course) => (
            <div key={course.id} className="flex items-center gap-2 rounded-md border bg-white px-3 py-2" style={{ borderColor: 'var(--border-subtle)' }}>
              <Pill tone={online ? 'info' : 'neutral'}>{course.course.course_code}</Pill>
              <span className="truncate text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{course.course.course_name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AcademicTimetable;
