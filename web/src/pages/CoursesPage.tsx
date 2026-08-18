import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarPlus,
  Check,
  Clock3,
  CornerDownLeft,
  FolderInput,
  Layers3,
  Lock,
  LockKeyhole,
  MapPin,
  Search,
  Sparkles,
  Trash2,
  Upload,
  Wifi,
  X,
} from 'lucide-react';
import { Modal } from '../components/workbench/Modal';
import { MetricCard, Pill, Surface } from '../components/workbench/atoms';
import { TimeSlotEditor } from '../components/course/TimeSlotEditor';
import { getCategoryOptions, getCategoryShortLabel, isCategoryUnset } from '../lib/categories';
import { fuzzySearch, splitHighlight, type FuzzyField } from '../lib/fuzzySearch';
import {
  addSelectedCourse,
  addTimeSlot,
  clearSelectedCourses,
  deleteTimeSlot,
  describeApiError,
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
  // 搜索预览下拉：聚焦且有输入时展开，支持 ↑↓ 选中、Enter 加入、Esc 关闭
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(0);

  const searchInputRef = useRef<HTMLInputElement | null>(null);

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

  // 搜索字段权重：编码/课名是用户的主要检索入口，教师次之，
  // 类别最弱——否则搜「选修」会把上百门同类别课程一起顶到前面。
  const courseFields = (course: Course): FuzzyField[] => [
    { key: 'code', value: course.course_code, weight: 1.2 },
    { key: 'name', value: course.course_name, weight: 1.5 },
    { key: 'teacher', value: course.teacher ?? '', weight: 0.8 },
    { key: 'category', value: course.category ?? '', weight: 0.4 },
  ];

  const matches = useMemo(
    () => fuzzySearch(courses, search, courseFields),
    [courses, search],
  );
  const filteredCourses = useMemo(() => matches.map((match) => match.item), [matches]);
  const highlightFor = useMemo(() => {
    const map = new Map<string, Record<string, number[]>>();
    for (const match of matches) {
      map.set(`${match.item.course_code}-${match.item.class_index}`, match.highlights);
    }
    return map;
  }, [matches]);
  const previewMatches = useMemo(() => matches, [matches]);

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
        // 只报条数等于没报：用户不知道是哪一列缺了，也就无从预料后果。
        message: result.warnings.length > 0
          ? `${result.message}。列映射提示：${result.warnings.join('；')}`
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
        message: describeApiError(error, '添加课程失败'),
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
      const updatedCourse = await patchSelectedCourse(courseId, { is_online: nextValue });
      setSelectedCourses((current) => current.map((course) => (
        course.id === courseId ? updatedCourse : course
      )));
      setSelectedCourseId(courseId);
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

  const handleSaveTimeSlot = async (
    timeSlot: TimeSlot,
    options: { exceptionOf: number | null },
  ) => {
    if (!selectedCourse) {
      return;
    }

    setBusy(true);
    try {
      if (editingTimeSlotIndex === null) {
        await addTimeSlot(selectedCourse.id, timeSlot);

        // 例外周：把这几周从常规时间段里扣掉。
        // 一门课同一周不会既在上午又在晚上；不扣会让两个时段
        // 同时占着同一周，冲突检测会误报。
        // 先加例外再扣常规：若后一步失败，用户看到的是“多了一段”
        // （可见、可手改），而不是“周次悉数丢失”。
        if (options.exceptionOf !== null) {
          const base = selectedCourse.time_slots[options.exceptionOf];
          if (base) {
            const exceptionWeeks = new Set(timeSlot.weeks);
            const remaining = base.weeks.filter((week) => !exceptionWeeks.has(week));
            if (remaining.length > 0) {
              await updateTimeSlot(selectedCourse.id, options.exceptionOf, {
                ...base,
                weeks: remaining,
              });
            } else {
              // 常规段被整段替换，直接删掉，不留一个空周次的死段
              await deleteTimeSlot(selectedCourse.id, options.exceptionOf);
            }
          }
        }
      } else {
        await updateTimeSlot(selectedCourse.id, editingTimeSlotIndex, timeSlot);
      }

      await refreshSelectedAndCredits(selectedCourse.id);
      setFeedback({
        tone: 'success',
        message:
          editingTimeSlotIndex !== null
            ? '时间段已更新。'
            : options.exceptionOf !== null
              ? '例外周已添加，常规时间段已自动扣除这几周。'
              : '时间段已添加。',
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
          style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger-text)' }}
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
          className="feedback-banner flex items-start gap-2 rounded-lg border px-4 py-3 text-sm"
          style={
            feedback.tone === 'error'
              ? { borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger-text)' }
              : feedback.tone === 'success'
                ? { borderColor: 'var(--success-border)', background: 'var(--success-bg)', color: 'var(--success-text)' }
                : { borderColor: 'var(--warning-border)', background: 'var(--warning-bg)', color: 'var(--warning-text)' }
          }
        >
          {feedback.message}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-5" aria-label="正在初始化课程工作台" aria-busy="true">
          <div className="grid gap-3 sm:grid-cols-3">
            {Array.from({ length: 3 }, (_, index) => (
              <div key={index} className="skeleton h-24 rounded-xl" />
            ))}
          </div>
          <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
            <div className="skeleton h-[32rem] rounded-2xl" />
            <div className="space-y-4">
              <div className="skeleton h-48 rounded-2xl" />
              <div className="skeleton h-64 rounded-2xl" />
            </div>
          </div>
          <span className="sr-only">初始化工作台…</span>
        </div>
      )}

      {!loading && (
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          {/* ── Left: catalog ── */}
          <div className="min-w-0 space-y-4 xl:min-h-0 xl:self-stretch xl:[contain:size]">
            <Surface className="h-full min-w-0 xl:[&>div]:flex xl:[&>div]:h-full xl:[&>div]:min-h-0 xl:[&>div]:flex-col">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="min-w-0 truncate text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>课程目录</h3>
                <span className="tag tag-gray shrink-0">CATALOG</span>
              </div>

              {/* Search — 亮底浅色输入，光标与占位文字必须可见 */}
              <div className="relative mb-3">
                <div
                  className="flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors"
                  style={{
                    borderColor: previewOpen ? 'var(--accent-ui)' : 'var(--border-base)',
                    background: 'var(--bg-card)',
                  }}
                >
                  <Search className="h-4 w-4 shrink-0" style={{ color: 'var(--text-muted)' }} />
                  <input
                    ref={searchInputRef}
                    aria-label="搜索课程"
                    role="combobox"
                    aria-expanded={previewOpen}
                    aria-controls="course-search-preview"
                    aria-autocomplete="list"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPreviewOpen(e.target.value.trim().length > 0);
                      setPreviewIndex(0);
                    }}
                    onFocus={() => setPreviewOpen(search.trim().length > 0)}
                    // 用 blur 延迟关闭，否则点击下拉项时 blur 先触发、点击丢失
                    onBlur={() => window.setTimeout(() => setPreviewOpen(false), 120)}
                    onKeyDown={(e) => {
                      if (!previewOpen || previewMatches.length === 0) {
                        if (e.key === 'Escape') setSearch('');
                        return;
                      }
                      if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        setPreviewIndex((i) => (i + 1) % previewMatches.length);
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        setPreviewIndex((i) => (i - 1 + previewMatches.length) % previewMatches.length);
                      } else if (e.key === 'Enter') {
                        e.preventDefault();
                        const target = previewMatches[previewIndex]?.item;
                        if (target) {
                          const already = selectedCourses.some(
                            (s) =>
                              s.course.course_code === target.course_code
                              && s.class_index === target.class_index,
                          );
                          if (!already) {
                            handleAddCourse(target).catch(() => undefined);
                          }
                        }
                      } else if (e.key === 'Escape') {
                        e.preventDefault();
                        setPreviewOpen(false);
                      }
                    }}
                    placeholder="搜索编码、名称、教师或类别（支持多关键词，空格分隔）"
                    className="w-full bg-transparent text-sm outline-none"
                    style={{ color: 'var(--text-primary)', caretColor: 'var(--accent-ui)' }}
                  />
                  {search && (
                    <button
                      type="button"
                      onClick={() => {
                        setSearch('');
                        setPreviewOpen(false);
                        searchInputRef.current?.focus();
                      }}
                      aria-label="清除搜索"
                      className="shrink-0 rounded p-0.5 transition-opacity hover:opacity-100"
                      style={{ color: 'var(--text-muted)', opacity: 0.6 }}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <span
                    className="shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium"
                    style={{ background: 'var(--bg-base)', color: 'var(--text-muted)' }}
                  >
                    {filteredCourses.length}
                  </span>
                </div>

                {/* 实时预览：命中片段高亮，Enter 直接加入 */}
                {previewOpen && previewMatches.length > 0 && (
                  <div
                    id="course-search-preview"
                    role="listbox"
                    className="absolute left-0 right-0 top-full z-20 mt-1 max-h-[18rem] overflow-y-auto overscroll-contain rounded-lg border shadow-lg"
                    style={{ borderColor: 'var(--border-card)', background: 'var(--bg-card)' }}
                  >
                    {previewMatches.map((match, index) => {
                      const course = match.item;
                      const key = `${course.course_code}-${course.class_index}`;
                      const active = index === previewIndex;
                      const already = selectedCourses.some(
                        (s) =>
                          s.course.course_code === course.course_code
                          && s.class_index === course.class_index,
                      );
                      const renderHighlighted = (value: string, field: string) =>
                        splitHighlight(value, match.highlights[field]).map((segment, i) =>
                          segment.hit ? (
                            <mark
                              key={i}
                              style={{
                                background: 'var(--accent-light)',
                                color: 'var(--accent-dark)',
                                borderRadius: '2px',
                                padding: '0 1px',
                              }}
                            >
                              {segment.text}
                            </mark>
                          ) : (
                            <span key={i}>{segment.text}</span>
                          ),
                        );

                      return (
                        <button
                          key={key}
                          type="button"
                          role="option"
                          aria-selected={active}
                          disabled={already}
                          onMouseEnter={() => setPreviewIndex(index)}
                          onClick={() => {
                            if (!already) {
                              handleAddCourse(course).catch(() => undefined);
                            }
                          }}
                          className="flex w-full items-center justify-between gap-3 border-b px-3 py-2 text-left last:border-b-0 transition-colors"
                          style={{
                            borderColor: 'var(--border-subtle)',
                            background: active ? 'var(--bg-base)' : 'transparent',
                            opacity: already ? 0.5 : 1,
                            cursor: already ? 'not-allowed' : 'pointer',
                          }}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm" style={{ color: 'var(--text-primary)' }}>
                              {renderHighlighted(course.course_name, 'name')}
                            </p>
                            <p
                              className="mt-0.5 truncate font-mono text-[11px]"
                              style={{ color: 'var(--text-muted)' }}
                            >
                              {renderHighlighted(course.course_code, 'code')}
                              {' · 班次 '}
                              {course.class_index}
                              {course.teacher ? ' · ' : ''}
                              {course.teacher ? renderHighlighted(course.teacher, 'teacher') : null}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                              {course.credits} 分
                            </span>
                            {already ? (
                              <Pill tone="neutral">已选</Pill>
                            ) : active ? (
                              <span
                                className="flex items-center gap-1 text-[10px]"
                                style={{ color: 'var(--accent-ui)' }}
                              >
                                <CornerDownLeft className="h-3 w-3" />
                                加入
                              </span>
                            ) : null}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
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
                <div
                  className="min-w-0 overflow-hidden rounded-lg border xl:flex xl:min-h-0 xl:flex-1 xl:flex-col"
                  style={{ borderColor: 'var(--border-card)' }}
                >
                  <div className="max-h-[32rem] overflow-auto xl:min-h-0 xl:flex-1 xl:max-h-none">
                    <table className="clinical-table min-w-full">
                      <thead>
                        <tr>
                          <th className="text-left">课程</th>
                          <th className="hidden text-left sm:table-cell">教师 / 校区</th>
                          <th className="hidden text-left sm:table-cell">类别</th>
                          <th className="whitespace-nowrap text-left">学分</th>
                          <th className="whitespace-nowrap text-right">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCourses.map((course) => {
                          const exists = selectedCourses.some(
                            (s) =>
                              s.course.course_code === course.course_code &&
                              s.class_index === course.class_index,
                          );
                          // 让表格里的命中片段与预览下拉保持一致的高亮
                          const rowHighlights =
                            highlightFor.get(`${course.course_code}-${course.class_index}`) ?? {};
                          const mark = (value: string, field: string) =>
                            splitHighlight(value, rowHighlights[field]).map((segment, i) =>
                              segment.hit ? (
                                <mark
                                  key={i}
                                  style={{
                                    background: 'var(--accent-light)',
                                    color: 'var(--accent-dark)',
                                    borderRadius: '2px',
                                    padding: '0 1px',
                                  }}
                                >
                                  {segment.text}
                                </mark>
                              ) : (
                                <span key={i}>{segment.text}</span>
                              ),
                            );
                          return (
                            <tr
                              key={`${course.course_code}-${course.class_index}`}
                              className="course-row"
                              data-course-category={course.category}
                            >
                              <td>
                                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                                  {mark(course.course_name, 'name')}
                                </p>
                                <p className="mt-0.5 font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
                                  {mark(course.course_code, 'code')} · 班次 {course.class_index}
                                </p>
                                <p className="mt-1 text-[11px] leading-5 sm:hidden" style={{ color: 'var(--text-muted)' }}>
                                  {course.teacher ? mark(course.teacher, 'teacher') : '待定'}
                                  {' · '}{course.campus || '校区待定'}{' · '}{course.category}
                                </p>
                              </td>
                              <td className="hidden text-sm sm:table-cell" style={{ color: 'var(--text-secondary)' }}>
                                <p>{course.teacher ? mark(course.teacher, 'teacher') : '待定'}</p>
                                <p className="mt-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>
                                  {course.campus || '—'}
                                </p>
                              </td>
                              <td className="hidden sm:table-cell">
                                <div className="flex flex-wrap gap-1">
                                  <Pill tone="neutral">{course.category}</Pill>
                                  {course.is_online && <Pill tone="info">线上</Pill>}
                                </div>
                              </td>
                              <td className="whitespace-nowrap text-sm tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                                {course.credits.toFixed(1)}
                              </td>
                              <td className="whitespace-nowrap text-right">
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
                      <div
                        key={c.id}
                        className="w-full rounded-lg border px-3 py-2.5 transition"
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
                          <button
                            type="button"
                            aria-pressed={active}
                            onClick={() => setSelectedCourseId(c.id)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <p className="truncate text-sm font-medium">{c.course.course_name}</p>
                            <p className="mt-0.5 font-mono text-[11px] opacity-70">
                              {c.course.course_code} · 班次 {c.class_index}
                            </p>
                            <div className="mt-1 flex gap-1">
                              <Pill tone={c.is_category_locked ? 'warning' : 'neutral'}>
                                {c.is_category_locked ? '锁定' : '可改'}
                              </Pill>
                              <Pill
                                tone={c.is_online ? 'info' : 'warning'}
                                className="font-semibold"
                              >
                                {c.is_online ? (
                                  <><Wifi className="h-3 w-3" />线上</>
                                ) : (
                                  <><MapPin className="h-3 w-3" />线下</>
                                )}
                              </Pill>
                              {isCategoryUnset(c.custom_category) && (
                                <Pill tone="danger">类别待设置</Pill>
                              )}
                            </div>
                          </button>
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
                      </div>
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
                            ? { borderColor: 'var(--danger-border)', background: 'var(--danger-bg)' }
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
                          <Pill
                            tone={selectedCourse.is_online ? 'info' : 'warning'}
                            className="px-2.5 py-1 font-semibold"
                          >
                            {selectedCourse.is_online ? (
                              <><Wifi className="h-3.5 w-3.5" />当前线上</>
                            ) : (
                              <><MapPin className="h-3.5 w-3.5" />当前线下</>
                            )}
                          </Pill>
                          <button
                            type="button"
                            className="btn-ghost"
                            onClick={() => {
                              handleOnlineToggle(selectedCourse.id, !selectedCourse.is_online).catch(
                                () => undefined,
                              );
                            }}
                          >
                            {selectedCourse.is_online ? '切换为线下' : '切换为线上'}
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
                            style={{ background: 'var(--bg-subtle)' }}
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
          siblingSlots={selectedCourse?.time_slots ?? []}
          editingIndex={editingTimeSlotIndex}
          onSave={handleSaveTimeSlot}
          onCancel={() => { setTimeSlotModalOpen(false); setEditingTimeSlotIndex(null); }}
        />
      </Modal>
    </div>
  );
}
