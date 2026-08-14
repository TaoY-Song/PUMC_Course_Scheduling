import { ChangeEvent, useEffect, useRef, useState } from 'react';
import {
  CalendarPlus,
  Check,
  Clock3,
  FolderInput,
  Layers3,
  Lock,
  LockKeyhole,
  Search,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react';
import { Modal } from '../components/workbench/Modal';
import { MetricCard, Pill, Surface } from '../components/workbench/atoms';
import { TimeSlotEditor } from '../components/course/TimeSlotEditor';
import { getCategoryOptions, getCategoryShortLabel, isCategoryUnset } from '../lib/categories';
import {
  addSelectedCourse,
  addTimeSlot,
  clearSelectedCourses,
  deleteTimeSlot,
  getCourses,
  getCreditStatus,
  getSelectedCourses,
  importSelectedCourses,
  loadCourses,
  patchSelectedCourse,
  removeSelectedCourse,
  updateTimeSlot,
} from '../lib/workbenchApi';
import { formatTimeSlot } from '../lib/time';
import type { Course, CreditRequirement, SelectedCourse, TimeSlot } from '../types/models';

type FeedbackTone = 'success' | 'error' | 'warning' | 'info';


export function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourses, setSelectedCourses] = useState<SelectedCourse[]>([]);
  const [creditStatus, setCreditStatus] = useState<CreditRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);
  const [timeSlotModalOpen, setTimeSlotModalOpen] = useState(false);
  const [editingTimeSlotIndex, setEditingTimeSlotIndex] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);

  const courseFileInputRef = useRef<HTMLInputElement | null>(null);
  const importFileInputRef = useRef<HTMLInputElement | null>(null);

  const selectedCourse =
    selectedCourses.find((course) => course.id === selectedCourseId)
    ?? selectedCourses[0]
    ?? null;

  const totalRequired = creditStatus.reduce((sum, item) => sum + item.required_credits, 0);
  const totalCompleted = creditStatus.reduce((sum, item) => sum + item.completed_credits, 0);
  const completionRate = totalRequired > 0 ? Math.round((totalCompleted / totalRequired) * 100) : 0;
  // 类别为 nan 的课程不计入任何学分要求，排课时会被静默丢弃。
  const unsetCategoryCourses = selectedCourses.filter((course) =>
    isCategoryUnset(course.custom_category),
  );

  const filteredCourses = courses.filter((course) => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return true;
    }

    return (
      course.course_code.toLowerCase().includes(query)
      || course.course_name.toLowerCase().includes(query)
      || (course.teacher ?? '').toLowerCase().includes(query)
      || (course.category ?? '').toLowerCase().includes(query)
    );
  });

  const refreshSelectedAndCredits = async (nextSelectedCourseId?: string | null) => {
    const [selected, credits] = await Promise.all([
      getSelectedCourses(),
      getCreditStatus(),
    ]);
    setSelectedCourses(selected);
    setCreditStatus(credits);

    if (nextSelectedCourseId && selected.some((course) => course.id === nextSelectedCourseId)) {
      setSelectedCourseId(nextSelectedCourseId);
      return;
    }

    setSelectedCourseId((current) => {
      if (current && selected.some((course) => course.id === current)) {
        return current;
      }
      return selected[0]?.id ?? null;
    });
  };

  const bootstrap = async () => {
    setLoading(true);
    try {
      const [loadedCourses, selected, credits] = await Promise.all([
        getCourses(),
        getSelectedCourses(),
        getCreditStatus(),
      ]);
      setCourses(loadedCourses);
      setSelectedCourses(selected);
      setCreditStatus(credits);
      setSelectedCourseId(selected[0]?.id ?? null);
      setFeedback(null);
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '工作台初始化失败',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    bootstrap().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!selectedCourseId && selectedCourses[0]) {
      setSelectedCourseId(selectedCourses[0].id);
    }
  }, [selectedCourseId, selectedCourses]);

  const handleCourseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setBusy(true);
    try {
      const result = await loadCourses(file);
      setCourses(result.courses);
      await refreshSelectedAndCredits(null);
      setFeedback({
        tone: result.warnings.length > 0 ? 'warning' : 'success',
        message: result.warnings.length > 0
          ? `${result.message}，但有 ${result.warnings.length} 条列映射警告。`
          : result.message,
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '课程表导入失败',
      });
    } finally {
      event.target.value = '';
      setBusy(false);
    }
  };

  const handleSelectedImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setBusy(true);
    try {
      await importSelectedCourses(file);
      await refreshSelectedAndCredits(null);
      setFeedback({
        tone: 'success',
        message: `已从 ${file.name} 恢复已选课程。`,
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '已选课程导入失败',
      });
    } finally {
      event.target.value = '';
      setBusy(false);
    }
  };

  const handleAddCourse = async (course: Course) => {
    setBusy(true);
    try {
      const selected = await addSelectedCourse(course.course_code, course.class_index);
      await refreshSelectedAndCredits(selected.id);
      setFeedback({
        tone: 'success',
        message: `已加入 ${course.course_name}（班次 ${course.class_index}）。`,
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '添加课程失败',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveCourse = async (courseId: string) => {
    setBusy(true);
    try {
      await removeSelectedCourse(courseId);
      await refreshSelectedAndCredits(null);
      setFeedback({
        tone: 'info',
        message: '已从当前选课篮子移除课程。',
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '移除课程失败',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleClearSelectedCourses = async () => {
    if (!selectedCourses.length || !window.confirm('确定清空当前所有已选课程吗？')) {
      return;
    }

    setBusy(true);
    try {
      await clearSelectedCourses();
      await refreshSelectedAndCredits(null);
      setFeedback({
        tone: 'warning',
        message: '已清空当前选课篮子。',
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '清空课程失败',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleCategoryChange = async (courseId: string, category: string) => {
    try {
      await patchSelectedCourse(courseId, { custom_category: category });
      await refreshSelectedAndCredits(courseId);
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '课程类别更新失败',
      });
    }
  };

  const handleOnlineToggle = async (courseId: string, nextValue: boolean) => {
    try {
      await patchSelectedCourse(courseId, { is_online: nextValue });
      await refreshSelectedAndCredits(courseId);
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '线上状态更新失败',
      });
    }
  };

  const handleLockToggle = async (courseId: string, nextValue: boolean) => {
    try {
      await patchSelectedCourse(courseId, { is_category_locked: nextValue });
      await refreshSelectedAndCredits(courseId);
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '类别锁定状态更新失败',
      });
    }
  };

  const handleSaveTimeSlot = async (timeSlot: TimeSlot) => {
    if (!selectedCourse) {
      return;
    }

    setBusy(true);
    try {
      if (editingTimeSlotIndex === null) {
        await addTimeSlot(selectedCourse.id, timeSlot);
      } else {
        await updateTimeSlot(selectedCourse.id, editingTimeSlotIndex, timeSlot);
      }

      await refreshSelectedAndCredits(selectedCourse.id);
      setFeedback({
        tone: 'success',
        message: editingTimeSlotIndex === null ? '时间段已添加。' : '时间段已更新。',
      });
      setTimeSlotModalOpen(false);
      setEditingTimeSlotIndex(null);
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '时间段保存失败',
      });
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteTimeSlot = async (timeSlotIndex: number) => {
    if (!selectedCourse) {
      return;
    }

    setBusy(true);
    try {
      await deleteTimeSlot(selectedCourse.id, timeSlotIndex);
      await refreshSelectedAndCredits(selectedCourse.id);
      setFeedback({
        tone: 'info',
        message: '时间段已删除。',
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '删除时间段失败',
      });
    } finally {
      setBusy(false);
    }
  };

  const editingSlot =
    selectedCourse && editingTimeSlotIndex !== null
      ? selectedCourse.time_slots[editingTimeSlotIndex]
      : undefined;

  return (
    <div className="space-y-5">
      <input ref={courseFileInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleCourseFile} />
      <input ref={importFileInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleSelectedImport} />

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em]" style={{ color: 'var(--text-muted)' }}>
            Course Workbench
          </p>
          <h2 className="mt-0.5 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>课程工作台</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => courseFileInputRef.current?.click()} disabled={busy} className="btn-primary">
            <Upload className="h-3.5 w-3.5" />
            导入课程表
          </button>
          <button type="button" onClick={() => importFileInputRef.current?.click()}
                  disabled={busy || courses.length === 0} className="btn-ghost">
            <FolderInput className="h-3.5 w-3.5" />
            导入已选
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="已加载课程" value={String(courses.length)} hint="可选集合" tone="pine" />
        <MetricCard label="已选" value={String(selectedCourses.length)} hint="类别与时间可编辑" tone="teal" />
        <MetricCard
          label="学分完成率"
          value={`${completionRate}%`}
          hint={`${totalCompleted.toFixed(1)} / ${totalRequired.toFixed(1)} 学分`}
          tone="sand"
        />
      </div>

      {/* 未设置类别的课程会在排课时被忽略，必须在进排课页前就告知 */}
      {unsetCategoryCourses.length > 0 && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: '#fca5a5', background: '#fff5f5', color: '#991b1b' }}
        >
          <span className="font-medium">
            {unsetCategoryCourses.length} 门已选课程尚未设置类别
          </span>
          <span>— 这些课程不计入学分统计，排课时会被忽略。请在“课程细节”逐门选定类别。</span>
          <span className="font-mono text-[11px] opacity-80">
            {unsetCategoryCourses.map((course) => course.course.course_code).join('、')}
          </span>
        </div>
      )}

      {/* Feedback */}
      {feedback && (
        <div
          role={feedback.tone === 'error' ? 'alert' : 'status'}
          aria-live="polite"
          className="flex items-start gap-2 rounded-lg border px-4 py-3 text-sm"
          style={
            feedback.tone === 'error'
              ? { borderColor: '#fca5a5', background: '#fff5f5', color: '#991b1b' }
              : feedback.tone === 'success'
                ? { borderColor: '#99f6e4', background: '#f0fdfb', color: '#0f766e' }
                : { borderColor: 'var(--border-base)', background: '#fffbf0', color: '#92400e' }
          }
        >
          {feedback.message}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="py-12 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
          初始化工作台…
        </div>
      )}

      {!loading && (
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          {/* ── Left: catalog ── */}
          <div className="min-w-0 space-y-4">
            <Surface className="min-w-0">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>课程目录</h3>
                <span className="tag tag-gray shrink-0">CATALOG</span>
              </div>

              {/* Search */}
              <div className="mb-3 flex items-center gap-2 rounded-lg border px-3 py-2"
                   style={{ borderColor: 'var(--border-card)', background: 'var(--bg-sidebar)' }}>
                <Search className="h-4 w-4 shrink-0" style={{ color: 'var(--text-on-dark-muted)' }} />
                <input
                  aria-label="搜索课程"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索编码、名称、教师或类别"
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:opacity-50"
                />
                <span className="shrink-0 rounded-md px-1.5 py-0.5 text-[10px]"
                      style={{ background: 'rgba(255,255,255,0.15)', color: 'var(--text-on-dark-muted)' }}>
                  {filteredCourses.length}
                </span>
              </div>

              {courses.length === 0 ? (
                <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed py-10 text-center"
                     style={{ borderColor: 'var(--border-base)' }}>
                  <Layers3 className="h-8 w-8 opacity-30" style={{ color: 'var(--text-muted)' }} />
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    尚未导入课程表。点击"导入课程表"开始。
                  </p>
                </div>
              ) : filteredCourses.length === 0 ? (
                <div className="py-8 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                  没有匹配的课程，请缩短关键词或清空搜索。
                </div>
              ) : (
                <div className="min-w-0 overflow-hidden rounded-lg border" style={{ borderColor: 'var(--border-card)' }}>
                  <div className="max-h-[32rem] overflow-auto">
                    <table className="clinical-table min-w-full">
                      <thead>
                        <tr>
                          <th className="text-left">课程</th>
                          <th className="text-left">教师 / 校区</th>
                          <th className="text-left">类别</th>
                          <th className="text-left">学分</th>
                          <th className="text-right">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCourses.map((course) => {
                          const exists = selectedCourses.some(
                            (s) =>
                              s.course.course_code === course.course_code &&
                              s.class_index === course.class_index,
                          );
                          return (
                            <tr key={`${course.course_code}-${course.class_index}`}>
                              <td>
                                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                  {course.course_name}
                                </p>
                                <p className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                  {course.course_code} · 班次 {course.class_index}
                                </p>
                              </td>
                              <td className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                <p>{course.teacher || '待定'}</p>
                                <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                                  {course.campus || '—'}
                                </p>
                              </td>
                              <td>
                                <div className="flex flex-wrap gap-1">
                                  <Pill tone="neutral">{course.category}</Pill>
                                  {course.is_online && <Pill tone="info">线上</Pill>}
                                </div>
                              </td>
                              <td className="text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                                {course.credits.toFixed(1)}
                              </td>
                              <td className="text-right">
                                <button
                                  type="button"
                                  disabled={busy || exists}
                                  onClick={() => {
                                    if (!exists) { handleAddCourse(course).catch(() => undefined); }
                                  }}
                                  className={exists ? 'btn-ghost opacity-50' : 'btn-primary'}
                                >
                                  {exists ? (
                                    <><Check className="h-3.5 w-3.5" />已选</>
                                  ) : (
                                    <><Sparkles className="h-3.5 w-3.5" />加入</>
                                  )}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Surface>
          </div>

          {/* ── Right: selection + editing + credits ── */}
          <div className="min-w-0 space-y-4">
            {/* Selected list */}
            <Surface className="min-w-0">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>已选课程</h3>
                <button
                  type="button"
                  disabled={busy || selectedCourses.length === 0}
                  onClick={() => { handleClearSelectedCourses().catch(() => undefined); }}
                  className="btn-ghost text-rose-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  清空
                </button>
              </div>
              {selectedCourses.length === 0 ? (
                <div className="rounded-lg border border-dashed py-8 text-center text-xs"
                     style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
                  还没有已选课程。从左侧目录加入。
                </div>
              ) : (
                <div className="max-h-64 space-y-1.5 overflow-y-auto">
                  {selectedCourses.map((c) => {
                    const active = selectedCourse?.id === c.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setSelectedCourseId(c.id)}
                        className="w-full rounded-lg border px-3 py-2.5 text-left transition"
                        style={
                          active
                            ? { borderColor: 'var(--accent-ui)', background: 'var(--bg-sidebar)', color: 'var(--text-on-dark)' }
                            : {
                                borderColor: 'var(--border-subtle)',
                                background: 'var(--bg-card)',
                                color: 'var(--text-primary)',
                              }
                        }
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium">{c.course.course_name}</p>
                            <p className="mt-0.5 font-mono text-[11px] opacity-70">
                              {c.course.course_code} · 班次 {c.class_index}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRemoveCourse(c.id).catch(() => undefined);
                            }}
                            className="shrink-0 rounded-md border px-1.5 py-0.5 text-[11px] opacity-70 hover:opacity-100"
                            style={{ borderColor: 'currentColor' }}
                          >
                            移除
                          </button>
                        </div>
                        <div className="mt-1 flex gap-1">
                          <Pill tone={c.is_category_locked ? 'warning' : 'neutral'}>
                            {c.is_category_locked ? '锁定' : '可改'}
                          </Pill>
                          <Pill tone={c.is_online ? 'info' : 'neutral'}>
                            {c.is_online ? '线上' : '线下'}
                          </Pill>
                          {isCategoryUnset(c.custom_category) && (
                            <Pill tone="danger">类别待设置</Pill>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </Surface>

            {/* Course editor */}
            <Surface className="min-w-0">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>课程细节</h3>
                <span className="tag tag-gray shrink-0">EDIT</span>
              </div>
              {!selectedCourse ? (
                <div className="rounded-lg border border-dashed py-8 text-center text-xs"
                     style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
                  选择已选课程后在此编辑时间段与类别。
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="min-w-0 rounded-lg border px-3 py-3"
                       style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
                    <p className="truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {selectedCourse.course.course_name}
                    </p>
                    <p className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                      {selectedCourse.course.course_code} · 班次 {selectedCourse.class_index} ·{' '}
                      {selectedCourse.course.teacher || '教师待定'}
                    </p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <label>
                        <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.15em]"
                              style={{ color: 'var(--text-muted)' }}>类别</span>
                        <select
                          value={selectedCourse.custom_category || ''}
                          disabled={selectedCourse.is_category_locked}
                          aria-label="课程类别"
                          onChange={(e) => {
                            handleCategoryChange(selectedCourse.id, e.target.value).catch(() => undefined);
                          }}
                          className="input-base"
                          style={isCategoryUnset(selectedCourse.custom_category)
                            ? { borderColor: '#fca5a5', background: '#fff5f5' }
                            : undefined}
                        >
                          {isCategoryUnset(selectedCourse.custom_category) && (
                            <option value="" disabled>
                              请选择类别（未设置将被排课忽略）
                            </option>
                          )}
                          {getCategoryOptions(
                            selectedCourse.course.category,
                            selectedCourse.custom_category,
                          ).map((o) => (
                            <option key={o} value={o}>{o}</option>
                          ))}
                        </select>
                      </label>
                      <div>
                        <span className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.15em]"
                              style={{ color: 'var(--text-muted)' }}>状态</span>
                        <div className="flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => {
                              handleOnlineToggle(selectedCourse.id, !selectedCourse.is_online).catch(
                                () => undefined,
                              );
                            }}
                          >
                            {selectedCourse.is_online ? '改为线下' : '标记线上'}
                          </button>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => {
                              handleLockToggle(
                                selectedCourse.id,
                                !selectedCourse.is_category_locked,
                              ).catch(() => undefined);
                            }}
                          >
                            {selectedCourse.is_category_locked ? (
                              <><Lock className="h-3.5 w-3.5" />解锁</>
                            ) : (
                              <><LockKeyhole className="h-3.5 w-3.5" />锁定</>
                            )}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Time slots */}
                  <div className="min-w-0 rounded-lg border px-3 py-3"
                       style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
                    <div className="flex items-center justify-between gap-2 pb-2">
                      <p className="min-w-0 truncate text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
                        时间段 · {selectedCourse.time_slots.length} 条
                      </p>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => { setEditingTimeSlotIndex(null); setTimeSlotModalOpen(true); }}
                      >
                        <CalendarPlus className="h-3.5 w-3.5" />
                        新增
                      </button>
                    </div>
                    {selectedCourse.time_slots.length === 0 ? (
                      <div className="rounded border border-dashed py-4 text-center text-[11px]"
                           style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
                        暂无时间段（线上课程可留空）。
                      </div>
                    ) : (
                      <div className="mt-1 space-y-1">
                        {selectedCourse.time_slots.map((slot, index) => (
                          <div
                            key={`${selectedCourse.id}-${index}`}
                            className="flex items-center justify-between gap-2 rounded-md px-2 py-2"
                            style={{ background: '#faf9f6' }}
                          >
                            <div className="flex items-center gap-1.5">
                              <Clock3 className="h-3.5 w-3.5 shrink-0" style={{ color: 'var(--accent-ui)' }} />
                              <span className="text-xs" style={{ color: 'var(--text-primary)' }}>
                                {formatTimeSlot(slot)}
                              </span>
                            </div>
                            <div className="flex gap-1">
                              <button
                                type="button"
                                className="btn-ghost px-2 py-1 text-[11px]"
                                onClick={() => {
                                  setEditingTimeSlotIndex(index);
                                  setTimeSlotModalOpen(true);
                                }}
                              >
                                编辑
                              </button>
                              <button
                                type="button"
                                className="btn-ghost px-2 py-1 text-[11px] text-rose-600"
                                onClick={() => { handleDeleteTimeSlot(index).catch(() => undefined); }}
                              >
                                删除
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Surface>

            {/* Credit snapshot */}
            <Surface className="min-w-0">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>学分概览</h3>
                <span className="tag tag-gray shrink-0">CREDITS</span>
              </div>
              {creditStatus.length === 0 ? (
                <div className="py-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
                  暂无学分要求。
                </div>
              ) : (
                <div className="space-y-1.5">
                  {creditStatus.map((item) => (
                    <div
                      key={item.category}
                      className="flex min-w-0 items-center justify-between gap-2 rounded-lg border px-3 py-2"
                      style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                          {getCategoryShortLabel(item.category)}
                        </p>
                        <p className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                          {item.completed_credits.toFixed(1)} / {item.required_credits.toFixed(1)}
                        </p>
                      </div>
                      <Pill tone={item.is_completed ? 'success' : 'warning'}>
                        {item.is_completed ? '完成' : `余 ${item.remaining_credits.toFixed(1)}`}
                      </Pill>
                    </div>
                  ))}
                </div>
              )}
            </Surface>
          </div>
        </div>
      )}

      <Modal
        open={timeSlotModalOpen}
        onClose={() => { setTimeSlotModalOpen(false); setEditingTimeSlotIndex(null); }}
        title={editingTimeSlotIndex === null ? '新增课程时间段' : '编辑课程时间段'}
        description={selectedCourse ? `${selectedCourse.course.course_name} · 班次 ${selectedCourse.class_index}` : undefined}
        widthClassName="max-w-4xl"
      >
        <TimeSlotEditor
          initialValue={editingSlot}
          onSave={handleSaveTimeSlot}
          onCancel={() => { setTimeSlotModalOpen(false); setEditingTimeSlotIndex(null); }}
        />
      </Modal>
    </div>
  );
}
