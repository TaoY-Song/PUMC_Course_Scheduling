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
import { MetricCard, Pill, SectionTitle, Surface } from '../components/workbench/atoms';
import { TimeSlotEditor } from '../components/course/TimeSlotEditor';
import { getCategoryOptions, getCategoryShortLabel } from '../lib/categories';
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

function toneClass(tone: FeedbackTone) {
  switch (tone) {
    case 'success':
      return 'border-emerald-200 bg-emerald-50 text-emerald-900';
    case 'error':
      return 'border-rose-200 bg-rose-50 text-rose-900';
    case 'warning':
      return 'border-amber-200 bg-amber-50 text-amber-900';
    default:
      return 'border-sky-200 bg-sky-50 text-sky-900';
  }
}

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
    <div className="space-y-6">
      <input
        ref={courseFileInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleCourseFile}
      />
      <input
        ref={importFileInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleSelectedImport}
      />

      <SectionTitle
        eyebrow="Course Workbench"
        title="课程编排与学分盘点"
        description="这里承接 Qt 版的课程导入、选课、时间段配置和学分统计。数据加载、类别设置和时间安排已经收口到同一条浏览器工作流。"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => courseFileInputRef.current?.click()}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-full border border-[#204537] bg-[#163228] px-4 py-2 text-sm font-medium text-[#f9f4e9] transition hover:bg-[#214739] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Upload className="h-4 w-4" />
              导入课程表
            </button>
            <button
              type="button"
              onClick={() => importFileInputRef.current?.click()}
              disabled={busy || courses.length === 0}
              className="inline-flex items-center gap-2 rounded-full border border-[#d7cbb4] bg-white px-4 py-2 text-sm font-medium text-[#34413a] transition hover:bg-[#f7efdf] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <FolderInput className="h-4 w-4" />
              导入已选课程
            </button>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="已加载课程" value={`${courses.length}`} hint="来自课程一览表的可选集合" tone="pine" />
        <MetricCard label="当前已选" value={`${selectedCourses.length}`} hint="课程、类别与时间安排均可编辑" tone="amber" />
        <MetricCard label="学分完成率" value={`${completionRate}%`} hint={`${totalCompleted.toFixed(1)} / ${totalRequired.toFixed(1)} 学分`} tone="sand" />
      </div>

      {feedback && (
        <div className={`rounded-[1.2rem] border px-4 py-3 text-sm ${toneClass(feedback.tone)}`}>
          {feedback.message}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-6">
          <Surface eyebrow="Catalog" title="课程源与筛选">
            <div className="grid gap-4 lg:grid-cols-[0.92fr_1.08fr]">
              <div className="rounded-[1.4rem] border border-[#e5d9c3] bg-white/85 p-4">
                <div className="text-sm font-semibold text-[#1a2620]">本次导入说明</div>
                <p className="mt-2 text-sm leading-7 text-[#5e695f]">
                  支持 `xlsx / xls`，列映射和警告信息由后端返回。导入新课程表时，会话中的已选课程会按后端规则重置。
                </p>
                <div className="mt-4 space-y-2 text-sm text-[#667168]">
                  <div className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 text-[#285946]" />
                    自动建立课程编码索引和班次集合
                  </div>
                  <div className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 text-[#285946]" />
                    学分统计会和已选课程实时联动
                  </div>
                  <div className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 text-[#285946]" />
                    时间段可在右侧直接增删改
                  </div>
                </div>
              </div>

              <div className="rounded-[1.4rem] border border-[#e5d9c3] bg-[linear-gradient(135deg,rgba(24,48,40,0.98),rgba(44,87,72,0.92))] p-4 text-[#f5f0e5]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[0.72rem] uppercase tracking-[0.3em] text-[#d7c6a0]">Quick Filter</div>
                    <div className="mt-2 text-lg font-semibold">筛掉噪音，保留有效课程</div>
                  </div>
                  <div className="rounded-2xl border border-white/15 bg-white/10 p-3">
                    <Search className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-4 rounded-[1.2rem] border border-white/12 bg-white/8 px-4 py-3">
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="搜索课程编码、名称、教师或类别"
                    className="w-full bg-transparent text-sm text-white outline-none placeholder:text-[#d4ded7]"
                  />
                </div>
                <div className="mt-4 flex flex-wrap gap-2 text-xs text-[#f7efdf]">
                  <Pill tone="neutral" className="border-white/10 bg-white/10 text-[#f6ecdc]">
                    共 {filteredCourses.length} 条筛选结果
                  </Pill>
                  <Pill tone="neutral" className="border-white/10 bg-white/10 text-[#f6ecdc]">
                    已选 {selectedCourses.length} 门
                  </Pill>
                </div>
              </div>
            </div>
          </Surface>

          <Surface
            eyebrow="Inventory"
            title="课程目录"
            action={
              <div className="inline-flex items-center gap-2 rounded-full border border-[#d8cdb8] bg-[#f7f0e0] px-3 py-1.5 text-xs text-[#6d5a35]">
                <Layers3 className="h-3.5 w-3.5" />
                目录视图
              </div>
            }
          >
            {loading ? (
              <div className="py-10 text-sm text-[#677268]">正在加载课程目录...</div>
            ) : (
              <div className="overflow-hidden rounded-[1.35rem] border border-[#e6dbc8] bg-white">
                <div className="max-h-[34rem] overflow-auto">
                  <table className="min-w-full border-collapse text-left">
                    <thead className="sticky top-0 z-10 bg-[#f6efdf] text-xs uppercase tracking-[0.18em] text-[#7a6d55]">
                      <tr>
                        <th className="px-4 py-3">课程</th>
                        <th className="px-4 py-3">教师 / 校区</th>
                        <th className="px-4 py-3">类别</th>
                        <th className="px-4 py-3">学分</th>
                        <th className="px-4 py-3 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCourses.map((course) => {
                        const exists = selectedCourses.some(
                          (selected) =>
                            selected.course.course_code === course.course_code
                            && selected.class_index === course.class_index,
                        );

                        return (
                          <tr
                            key={`${course.course_code}-${course.class_index}`}
                            className="border-t border-[#eee4d1] align-top transition hover:bg-[#fffaf1]"
                          >
                            <td className="px-4 py-4">
                              <div className="font-medium text-[#16211d]">{course.course_name}</div>
                              <div className="mt-1 text-sm text-[#5f6a61]">
                                {course.course_code} · 班次 {course.class_index}
                              </div>
                            </td>
                            <td className="px-4 py-4 text-sm text-[#5f6a61]">
                              <div>{course.teacher || '待定教师'}</div>
                              <div className="mt-1">{course.campus || '未标记校区'}</div>
                            </td>
                            <td className="px-4 py-4">
                              <div className="flex flex-wrap gap-2">
                                <Pill tone="neutral">{course.category}</Pill>
                                {course.is_online && <Pill tone="info">线上</Pill>}
                              </div>
                            </td>
                            <td className="px-4 py-4 text-sm font-medium text-[#26342d]">
                              {course.credits.toFixed(1)}
                            </td>
                            <td className="px-4 py-4 text-right">
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => (exists ? undefined : handleAddCourse(course))}
                                className={[
                                  'inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition',
                                  exists
                                    ? 'cursor-default border-[#d9d4c9] bg-[#f5f1e8] text-[#7b7467]'
                                    : 'border-[#1f4739] bg-[#17362d] text-[#f9f5eb] hover:bg-[#21463a]',
                                ].join(' ')}
                              >
                                {exists ? (
                                  <>
                                    <Check className="h-4 w-4" />
                                    已在篮子
                                  </>
                                ) : (
                                  <>
                                    <Sparkles className="h-4 w-4" />
                                    加入排课篮子
                                  </>
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

        <div className="space-y-6">
          <Surface
            eyebrow="Selection"
            title="已选课程"
            action={
              <button
                type="button"
                disabled={busy || selectedCourses.length === 0}
                onClick={handleClearSelectedCourses}
                className="inline-flex items-center gap-2 rounded-full border border-[#dcc6bf] bg-[#fff6f4] px-3 py-1.5 text-xs font-medium text-[#8c3c33] transition hover:bg-[#ffede9] disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Trash2 className="h-3.5 w-3.5" />
                清空全部
              </button>
            }
          >
            {selectedCourses.length === 0 ? (
              <div className="rounded-[1.3rem] border border-dashed border-[#d9cfbc] bg-[#faf4e7] px-4 py-8 text-center text-sm leading-7 text-[#6b675b]">
                还没有已选课程。先从左侧目录把课程加入排课篮子。
              </div>
            ) : (
              <div className="rounded-[1.25rem] border border-[#ebe0cb] bg-[#fcf7ee] p-2">
                <div className="max-h-[28rem] overflow-y-auto pr-1">
                  <div className="space-y-3">
                {selectedCourses.map((course) => (
                  <button
                    key={course.id}
                    type="button"
                    onClick={() => setSelectedCourseId(course.id)}
                    className={[
                      'w-full rounded-[1.3rem] border px-4 py-4 text-left transition',
                      selectedCourse?.id === course.id
                        ? 'border-[#1d4a3b] bg-[#17382e] text-[#f7f2e8] shadow-[0_20px_50px_rgba(20,34,28,0.18)]'
                        : 'border-[#e8ddca] bg-white/90 text-[#1f2b25] hover:bg-[#fffaf2]',
                    ].join(' ')}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{course.course.course_name}</div>
                        <div className="mt-1 text-xs opacity-80">
                          {course.course.course_code} · 班次 {course.class_index}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          handleRemoveCourse(course.id).catch(() => undefined);
                        }}
                        className="rounded-full border border-current/15 px-2.5 py-1 text-xs"
                      >
                        移除
                      </button>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <Pill tone={course.is_category_locked ? 'warning' : 'neutral'}>
                        {course.is_category_locked ? '类别锁定' : '类别可改'}
                      </Pill>
                      <Pill tone={course.is_online ? 'info' : 'neutral'}>
                        {course.is_online ? '线上' : '线下'}
                      </Pill>
                    </div>
                  </button>
                  ))}
                  </div>
                </div>
              </div>
            )}
          </Surface>

          <Surface eyebrow="Editing" title="课程细节与时间安排">
            {!selectedCourse ? (
              <div className="rounded-[1.2rem] border border-dashed border-[#d9cfbc] bg-[#faf4e7] px-4 py-8 text-center text-sm text-[#6b675b]">
                选择一门已选课程后，这里会展示类别、线上状态和时间段编辑。
              </div>
            ) : (
              <div className="space-y-4">
                <div className="rounded-[1.3rem] border border-[#e7ddc8] bg-white/90 p-4">
                  <div className="text-lg font-semibold text-[#1a2620]">{selectedCourse.course.course_name}</div>
                  <div className="mt-1 text-sm text-[#667269]">
                    {selectedCourse.course.course_code} · 班次 {selectedCourse.class_index} · {selectedCourse.course.teacher || '教师待定'}
                  </div>
                  <div className="mt-4 grid gap-4 sm:grid-cols-2">
                    <label className="space-y-2">
                      <div className="text-xs uppercase tracking-[0.22em] text-[#83775f]">课程类别</div>
                      <select
                        value={selectedCourse.custom_category || ''}
                        disabled={selectedCourse.is_category_locked}
                        onChange={(event) => {
                          handleCategoryChange(selectedCourse.id, event.target.value).catch(() => undefined);
                        }}
                        className="w-full rounded-2xl border border-[#d7ccb8] bg-[#fffdfa] px-3 py-2 text-sm text-[#17211d] outline-none transition focus:border-[#8e7440] focus:ring-2 focus:ring-[#dcc79f] disabled:cursor-not-allowed disabled:bg-[#f1ede4]"
                      >
                        {getCategoryOptions(
                          selectedCourse.course.category,
                          selectedCourse.custom_category,
                        ).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="space-y-2">
                      <div className="text-xs uppercase tracking-[0.22em] text-[#83775f]">状态控制</div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            handleOnlineToggle(selectedCourse.id, !selectedCourse.is_online).catch(() => undefined);
                          }}
                          className={[
                            'inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition',
                            selectedCourse.is_online
                              ? 'border-sky-200 bg-sky-50 text-sky-900'
                              : 'border-[#ddd1bd] bg-white text-[#435047]',
                          ].join(' ')}
                        >
                          {selectedCourse.is_online ? '改为线下' : '标记线上'}
                        </button>
                      <button
                        type="button"
                        onClick={() => {
                          handleLockToggle(selectedCourse.id, !selectedCourse.is_category_locked).catch(() => undefined);
                        }}
                          className="inline-flex items-center gap-2 rounded-full border border-[#ddd1bd] bg-white px-3 py-2 text-sm font-medium text-[#435047] transition hover:bg-[#f8efde]"
                        >
                          {selectedCourse.is_category_locked ? (
                            <>
                              <Lock className="h-4 w-4" />
                              解锁类别
                            </>
                          ) : (
                            <>
                              <LockKeyhole className="h-4 w-4" />
                              锁定类别
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.3rem] border border-[#e7ddc8] bg-white/90 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-[#1a2620]">时间段列表</div>
                      <div className="mt-1 text-xs text-[#707a71]">
                        当前共 {selectedCourse.time_slots.length} 个时间段。
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingTimeSlotIndex(null);
                        setTimeSlotModalOpen(true);
                      }}
                      className="inline-flex items-center gap-2 rounded-full border border-[#1f4739] bg-[#17362d] px-3 py-2 text-sm font-medium text-[#f8f4ea] transition hover:bg-[#21463a]"
                    >
                      <CalendarPlus className="h-4 w-4" />
                      新增时间段
                    </button>
                  </div>

                  <div className="mt-4 space-y-3">
                    {selectedCourse.time_slots.length === 0 ? (
                      <div className="rounded-[1.2rem] border border-dashed border-[#d9cfbc] bg-[#faf4e7] px-4 py-6 text-sm text-[#6b675b]">
                        这门课还没有时间段。可以保持为空，用于线上课程或后续补录。
                      </div>
                    ) : (
                      selectedCourse.time_slots.map((slot, index) => (
                        <div key={`${selectedCourse.id}-${index}`} className="rounded-[1.2rem] border border-[#e8ddca] bg-[#fffaf1] px-4 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="inline-flex items-center gap-2 text-sm font-medium text-[#223129]">
                                <Clock3 className="h-4 w-4 text-[#8d7440]" />
                                {formatTimeSlot(slot)}
                              </div>
                              <div className="mt-2 text-xs text-[#6d766d]">
                                {getCategoryShortLabel(selectedCourse.custom_category || selectedCourse.course.category)} · {selectedCourse.is_online ? '线上' : '线下'}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingTimeSlotIndex(index);
                                  setTimeSlotModalOpen(true);
                                }}
                                className="rounded-full border border-[#d5ccb8] bg-white px-3 py-1.5 text-xs font-medium text-[#3f4a43] transition hover:bg-[#f7efde]"
                              >
                                编辑
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  handleDeleteTimeSlot(index).catch(() => undefined);
                                }}
                                className="rounded-full border border-[#e1c9c4] bg-[#fff4f1] px-3 py-1.5 text-xs font-medium text-[#8b4038] transition hover:bg-[#ffe9e5]"
                              >
                                删除
                              </button>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            )}
          </Surface>

          <Surface eyebrow="Credit Snapshot" title="实时学分概览">
            <div className="space-y-3">
              {creditStatus.map((item) => (
                <div key={item.category} className="rounded-[1.2rem] border border-[#e8ddca] bg-white/90 px-4 py-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-[#1b2822]">{getCategoryShortLabel(item.category)}</div>
                      <div className="mt-1 text-xs text-[#6e786f]">
                        {item.completed_credits.toFixed(1)} / {item.required_credits.toFixed(1)} 学分
                      </div>
                    </div>
                    <Pill tone={item.is_completed ? 'success' : 'warning'}>
                      {item.is_completed ? '已完成' : `剩余 ${item.remaining_credits.toFixed(1)}`}
                    </Pill>
                  </div>
                </div>
              ))}
            </div>
          </Surface>
        </div>
      </div>

      <Modal
        open={timeSlotModalOpen}
        onClose={() => {
          setTimeSlotModalOpen(false);
          setEditingTimeSlotIndex(null);
        }}
        title={editingTimeSlotIndex === null ? '新增课程时间段' : '编辑课程时间段'}
        description={selectedCourse ? `${selectedCourse.course.course_name} · 班次 ${selectedCourse.class_index}` : undefined}
        widthClassName="max-w-4xl"
      >
        <TimeSlotEditor
          initialValue={editingSlot}
          onSave={handleSaveTimeSlot}
          onCancel={() => {
            setTimeSlotModalOpen(false);
            setEditingTimeSlotIndex(null);
          }}
        />
      </Modal>
    </div>
  );
}
