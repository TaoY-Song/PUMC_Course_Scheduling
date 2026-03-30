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

const ROW_HEIGHT = 56;

function weekFilterLabel(filter: TimetableWeekFilter) {
  return filter === 'all' ? '全部周' : `第 ${filter} 周`;
}

export function AcademicTimetable({
  courses,
  title = '周课表视图',
  description = '支持周次筛选、冲突分栏和线上课程独立展示。',
  defaultWeekFilter = 'all',
}: AcademicTimetableProps) {
  const [weekFilter, setWeekFilter] = useState<TimetableWeekFilter>(defaultWeekFilter);

  const model = useMemo(() => buildAcademicTimetable(courses, weekFilter), [courses, weekFilter]);
  const rowCount = Math.max(1, model.totalPeriods);
  const boardHeight = rowCount * ROW_HEIGHT;

  return (
    <Surface
      eyebrow="课表"
      title={title}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="neutral">{weekFilterLabel(weekFilter)}</Pill>
          <select
            value={String(weekFilter)}
            onChange={(event) => {
              const next = event.target.value;
              setWeekFilter(next === 'all' ? 'all' : Number(next));
            }}
            className="rounded-full border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#24312c] outline-none transition focus:border-[#7c8d6f] focus:ring-2 focus:ring-[#c9d6b9]"
          >
            <option value="all">全部周</option>
            {model.weeks.map((week) => (
              <option key={week} value={week}>
                第 {week} 周
              </option>
            ))}
          </select>
        </div>
      }
    >
      <div className="space-y-4">
        <p className="text-sm leading-6 text-[#5c665f]">{description}</p>

        <div className="flex flex-wrap items-center gap-2 text-sm text-[#5c665f]">
          <span className="inline-flex items-center gap-1 rounded-full border border-[#d9cdb9] bg-[#fbf7ef] px-3 py-1">
            <CalendarDays className="h-4 w-4 text-[#8b734b]" />
            7 x {rowCount} 学术网格
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-[#d9cdb9] bg-[#fbf7ef] px-3 py-1">
            <Layers3 className="h-4 w-4 text-[#8b734b]" />
            冲突课程自动分栏
          </span>
          <span className="text-xs text-[#7a6f5c]">按 weekday / period / weeks 过滤，线上课程独立展示。</span>
        </div>

        {courses.length === 0 ? (
          <div className="rounded-[1rem] border border-dashed border-[#d8ccb8] bg-[#fbf7ef] px-4 py-8 text-sm text-[#6b756d]">
            当前没有课程可渲染。执行排课后，这里会显示周课表和冲突分栏。
          </div>
        ) : (
          <div className="space-y-5">
            <div className="overflow-x-auto rounded-[1.25rem] border border-[#e1d6c2] bg-white">
              <div className="min-w-[1120px]">
                <div className="grid grid-cols-[4.5rem_repeat(7,minmax(11.5rem,1fr))] border-b border-[#eadfcb] bg-[#fbf7ef]">
                  <div className="border-r border-[#eadfcb] px-3 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-[#7b6b55]">
                    节次
                  </div>
                  {model.dayLayouts.map((day) => (
                    <div
                      key={day.dayOfWeek}
                      className="border-r border-[#eadfcb] px-3 py-3 text-sm font-semibold text-[#24312c] last:border-r-0"
                    >
                      {day.label}
                    </div>
                  ))}
                </div>

                <div className="flex">
                  <div
                    className="relative w-[4.5rem] shrink-0 border-r border-[#eadfcb] bg-[#fbf7ef]"
                    style={{ height: boardHeight }}
                  >
                    {Array.from({ length: rowCount }, (_, index) => {
                      const period = index + 1;
                      return (
                        <div
                          key={period}
                          className="absolute left-0 flex h-[56px] w-full items-center justify-center border-b border-[#efe5d3] text-xs text-[#857763]"
                          style={{ top: index * ROW_HEIGHT }}
                        >
                          {period}
                        </div>
                      );
                    })}
                  </div>

                  <div className="grid flex-1 grid-cols-7" style={{ height: boardHeight }}>
                    {model.dayLayouts.map((day) => (
                      <div
                        key={day.dayOfWeek}
                        className="relative border-r border-[#eadfcb] last:border-r-0"
                        style={{
                          height: boardHeight,
                          backgroundImage:
                            'repeating-linear-gradient(to bottom, rgba(214,203,180,0.32) 0, rgba(214,203,180,0.32) 1px, transparent 1px, transparent 56px)',
                          backgroundColor: '#fffdf8',
                        }}
                      >
                        {day.blocks.map((block) => {
                          const tokens = getCourseColorTokens(block.courseCode);
                          const top = (block.startPeriod - 1) * ROW_HEIGHT + 4;
                          const height = Math.max(ROW_HEIGHT * (block.endPeriod - block.startPeriod + 1) - 8, 38);
                          const left = (block.laneIndex / block.laneCount) * 100;
                          const width = 100 / block.laneCount;

                          return (
                            <div
                              key={block.id}
                              className="absolute overflow-hidden rounded-[0.95rem] border px-3 py-2 text-[11px] leading-5 transition hover:translate-y-[-1px]"
                              style={{
                                top,
                                height,
                                left: `calc(${left}% + 4px)`,
                                width: `calc(${width}% - 8px)`,
                                background: tokens.background,
                                borderColor: tokens.border,
                                color: tokens.text,
                                boxShadow: tokens.shadow,
                              }}
                              title={`${block.courseCode} ${block.courseName}`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="font-semibold">{block.courseCode}</div>
                                  <div className="truncate text-[11px] opacity-95">{block.courseName}</div>
                                </div>
                                <Pill tone="neutral" className="shrink-0 border-white/20 bg-white/10 text-white">
                                  L{block.laneIndex + 1}/{block.laneCount}
                                </Pill>
                              </div>
                              <div className="mt-1 flex flex-wrap gap-1">
                                <span className="rounded-full bg-white/16 px-2 py-0.5 text-[10px]">
                                  {block.startPeriod}-{block.endPeriod} 节
                                </span>
                                <span className="rounded-full bg-white/16 px-2 py-0.5 text-[10px]">
                                  {formatWeekSummary(block.weeks)}
                                </span>
                              </div>
                              <div className="mt-1 truncate text-[10px] opacity-90">
                                {block.teacher || block.campus || block.category || '课表块'}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
                <div className="mb-3 text-sm font-medium text-[#24312c]">线上课程独立区</div>
                {model.onlineCourses.length === 0 ? (
                  <div className="text-sm text-[#6b756d]">没有线上课程。</div>
                ) : (
                  <div className="space-y-3">
                    {model.onlineCourses.map((course) => (
                      <div key={course.id} className="rounded-[0.9rem] border border-[#e3d9c6] bg-white px-4 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill tone="info">{course.course.course_code}</Pill>
                          <span className="font-medium text-[#24312c]">{course.course.course_name}</span>
                          <Pill tone="success">线上</Pill>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-[#5a645b]">{course.course.teacher || '无教师信息'}</div>
                        <div className="mt-1 text-xs text-[#7b6b55]">{course.course.category}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
                <div className="mb-3 text-sm font-medium text-[#24312c]">无时间安排课程</div>
                {model.floatingCourses.length === 0 ? (
                  <div className="text-sm text-[#6b756d]">没有无时间安排的课程。</div>
                ) : (
                  <div className="space-y-3">
                    {model.floatingCourses.map((course) => (
                      <div key={course.id} className="rounded-[0.9rem] border border-[#e3d9c6] bg-white px-4 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill tone="neutral">{course.course.course_code}</Pill>
                          <span className="font-medium text-[#24312c]">{course.course.course_name}</span>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-[#5a645b]">{course.course.teacher || '无教师信息'}</div>
                        <div className="mt-1 text-xs text-[#7b6b55]">暂无时间安排</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[1rem] border border-dashed border-[#d8ccb8] bg-[#fbf7ef] px-4 py-3 text-xs leading-6 text-[#6b756d]">
              周次筛选只影响当前展示，不会修改原始排课结果。你可以切换不同周次查看同一组课程的布局变化。
            </div>
          </div>
        )}
      </div>
    </Surface>
  );
}

export default AcademicTimetable;
