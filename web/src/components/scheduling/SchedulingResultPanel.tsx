import type { ReactNode } from 'react';
import { formatCourseSchedule } from '../../lib/timetable';
import type { ScheduleResult, SelectedCourse } from '../../types/models';
import { MetricCard, Pill, Surface } from '../workbench/atoms';

interface SchedulingResultPanelProps {
  result: ScheduleResult | null;
  courses: SelectedCourse[];
  action?: ReactNode;
}

function score(value: number): string {
  return Number.isFinite(value) ? value.toFixed(1) : '0.0';
}

export function SchedulingResultPanel({ result, courses, action }: SchedulingResultPanelProps) {
  const selectedCourses = result?.selected_courses?.length ? result.selected_courses : courses;
  const totalCredits = selectedCourses.reduce((sum, course) => sum + (course.course.credits || 0), 0);
  const conflictCount = result?.conflicts?.length ?? 0;

  return (
    <Surface eyebrow="结果" title="排课摘要与明细" action={action}>
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="课程数" value={String(selectedCourses.length)} hint="当前纳入排课的课程数量" tone="pine" />
          <MetricCard label="总学分" value={score(totalCredits)} hint="按当前结果汇总" tone="amber" />
          <MetricCard label="总评分" value={score(result?.score.total_score ?? 0)} hint="综合评价分" tone="sand" />
          <MetricCard label="冲突数" value={String(conflictCount)} hint="结果返回的冲突信息" tone="ink" />
        </div>

        {result ? (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
              <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">学分匹配</div>
              <div className="mt-2 text-2xl font-semibold text-[#213028]">{score(result.score.credit_match_score)}</div>
              <div className="mt-3 h-2 rounded-full bg-[#e6dccb]">
                <div
                  className="h-2 rounded-full bg-emerald-500"
                  style={{ width: `${Math.max(0, Math.min(100, result.score.credit_match_score))}%` }}
                />
              </div>
            </div>
            <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
              <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">时间质量</div>
              <div className="mt-2 text-2xl font-semibold text-[#213028]">{score(result.score.time_quality_score)}</div>
              <div className="mt-3 h-2 rounded-full bg-[#e6dccb]">
                <div
                  className="h-2 rounded-full bg-[#7d6a4c]"
                  style={{ width: `${Math.max(0, Math.min(100, result.score.time_quality_score))}%` }}
                />
              </div>
            </div>
            <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
              <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">执行时间</div>
              <div className="mt-2 text-2xl font-semibold text-[#213028]">{result.execution_time.toFixed(2)}s</div>
              <div className="mt-2 text-sm text-[#6d756d]">{result.timestamp}</div>
            </div>
          </div>
        ) : (
          <div className="rounded-[1rem] border border-dashed border-[#d8ccb8] bg-[#fbf7ef] px-4 py-6 text-sm text-[#6b756d]">
            还没有排课结果。先保存配置并执行一次任务。
          </div>
        )}

        {result?.conflicts?.length ? (
          <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
            <div className="mb-3 text-sm font-medium text-[#24312c]">冲突信息</div>
            <div className="space-y-2">
              {result.conflicts.map((conflict, index) => (
                <div
                  key={`${conflict.course1_code}-${conflict.course2_code}-${index}`}
                  className="rounded-[0.9rem] border border-amber-200 bg-amber-50 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone="warning">{conflict.conflict_type}</Pill>
                    <span className="text-sm font-medium text-[#3f3524]">
                      {conflict.course1_code} / {conflict.course2_code}
                    </span>
                  </div>
                  <div className="mt-2 text-sm leading-6 text-[#6f5d39]">{conflict.description}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="rounded-[1rem] border border-[#e1d6c2] bg-white">
          <div className="border-b border-[#eadfcb] px-4 py-3 text-sm font-medium text-[#24312c]">课程明细</div>
          <div className="max-h-[28rem] overflow-auto">
            <table className="min-w-full divide-y divide-[#eee4d0]">
              <thead className="sticky top-0 z-10 bg-[#fbf7ef]">
                <tr className="text-left text-xs font-semibold uppercase tracking-[0.24em] text-[#7b6b55]">
                  <th className="px-4 py-3">课程</th>
                  <th className="px-4 py-3">教师</th>
                  <th className="px-4 py-3">学分</th>
                  <th className="px-4 py-3">类别</th>
                  <th className="px-4 py-3">校区</th>
                  <th className="px-4 py-3">时间安排</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1e8d7] bg-white">
                {selectedCourses.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-sm text-[#6d756d]" colSpan={6}>
                      当前没有课程。
                    </td>
                  </tr>
                ) : (
                  selectedCourses.map((course) => (
                    <tr key={course.id} className="align-top">
                      <td className="px-4 py-4">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <Pill tone="neutral">{course.course.course_code}</Pill>
                            {course.is_online || course.course.is_online ? <Pill tone="info">线上</Pill> : null}
                          </div>
                          <div className="font-medium text-[#24312c]">{course.course.course_name}</div>
                          <div className="text-xs text-[#768077]">{course.course.department}</div>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-sm text-[#445047]">{course.course.teacher || '-'}</td>
                      <td className="px-4 py-4 text-sm text-[#445047]">{course.course.credits.toFixed(1)}</td>
                      <td className="px-4 py-4 text-sm text-[#445047]">
                        {course.custom_category || course.course.category}
                      </td>
                      <td className="px-4 py-4 text-sm text-[#445047]">{course.course.campus || '-'}</td>
                      <td className="px-4 py-4 text-sm leading-6 text-[#445047]">
                        {formatCourseSchedule(course)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingResultPanel;
