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
  const totalCredits = selectedCourses.reduce((sum, c) => sum + (c.course.credits || 0), 0);
  const conflictCount = result?.conflicts?.length ?? 0;

  return (
    <Surface>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>排课摘要</h3>
        {action}
      </div>

      {/* Metrics */}
      <div className="mb-4 grid grid-cols-2 gap-2 xl:grid-cols-4">
        <MetricCard label="课程数"  value={String(selectedCourses.length)} hint="纳入排课" tone="pine"  />
        <MetricCard label="总学分"  value={score(totalCredits)}            hint="汇总"     tone="teal"  />
        <MetricCard label="综合评分" value={score(result?.score.total_score ?? 0)} hint="满分100" tone="sand"  />
        <MetricCard label="冲突数"  value={String(conflictCount)}          hint="需人工核查" tone="ink"  />
      </div>

      {/* Score breakdown */}
      {result ? (
        <div className="mb-4 grid grid-cols-3 gap-2">
          {([
            { label: '学分匹配', value: result.score.credit_match_score,  color: 'var(--accent-ui)' },
            { label: '时间质量', value: result.score.time_quality_score,   color: '#14b8a6' },
            { label: '执行 (s)', value: null, text: `${result.execution_time.toFixed(2)}s`, color: '#94a3b8' },
          ] as const).map((item) => (
            <div key={item.label} className="rounded-lg border px-3 py-3"
                 style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em]"
                 style={{ color: 'var(--text-muted)' }}>
                {item.label}
              </p>
              {'value' in item && item.value !== null ? (
                <>
                  <p className="mt-1 text-lg font-semibold tabular-nums"
                     style={{ color: 'var(--text-primary)' }}>
                    {score(item.value)}
                  </p>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-full"
                       style={{ background: 'var(--border-card)' }}>
                    <div className="h-full rounded-full"
                         style={{ width: `${Math.max(0, Math.min(100, item.value))}%`, background: item.color }} />
                  </div>
                </>
              ) : (
                <p className="mt-1 text-lg font-semibold tabular-nums"
                   style={{ color: 'var(--text-primary)' }}>
                  {item.text}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="mb-4 rounded-lg border border-dashed py-6 text-center text-xs"
             style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
          还没有排课结果。保存配置后执行一次任务。
        </div>
      )}

      {/* Conflicts */}
      {!!result?.conflicts?.length && (
        <div className="mb-4 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]"
             style={{ color: 'var(--text-muted)' }}>冲突信息</p>
          {result.conflicts.map((c, i) => (
            <div key={`${c.course1_code}-${c.course2_code}-${i}`}
                 className="flex items-start gap-2 rounded-lg border px-3 py-2.5"
                 style={{ borderColor: '#fde68a', background: '#fffbeb' }}>
              <Pill tone="warning">{c.conflict_type}</Pill>
              <div>
                <p className="text-xs font-medium" style={{ color: '#92400e' }}>
                  {c.course1_code} / {c.course2_code}
                </p>
                <p className="mt-0.5 text-xs" style={{ color: '#b45309' }}>{c.description}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Course table */}
      <div className="overflow-hidden rounded-lg border" style={{ borderColor: 'var(--border-card)' }}>
        <div className="border-b px-4 py-2.5"
             style={{ borderColor: 'var(--border-card)', background: '#f8f7f4' }}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em]"
             style={{ color: 'var(--text-muted)' }}>
            课程明细 — {selectedCourses.length} 门
          </p>
        </div>
        <div className="max-h-80 overflow-auto">
          <table className="clinical-table min-w-full">
            <thead>
              <tr>
                <th className="text-left">课程</th>
                <th className="text-left">教师</th>
                <th className="text-left">学分</th>
                <th className="text-left">类别</th>
                <th className="text-left">时间</th>
              </tr>
            </thead>
            <tbody>
              {selectedCourses.length === 0 ? (
                <tr>
                  <td className="px-4 py-5 text-xs" style={{ color: 'var(--text-muted)' }} colSpan={5}>
                    暂无课程数据。
                  </td>
                </tr>
              ) : selectedCourses.map((c) => (
                <tr key={c.id}>
                  <td>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {c.course.course_name}
                    </p>
                    <p className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {c.course.course_code}
                    </p>
                  </td>
                  <td className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {c.course.teacher || '—'}
                  </td>
                  <td className="text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                    {c.course.credits.toFixed(1)}
                  </td>
                  <td>
                    <Pill tone="neutral">{c.custom_category || c.course.category}</Pill>
                  </td>
                  <td className="max-w-[12rem] text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {formatCourseSchedule(c)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingResultPanel;
