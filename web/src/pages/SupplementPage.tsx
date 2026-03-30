import { type ChangeEvent, useMemo, useRef, useState } from 'react';
import {
  Download,
  FileSearch,
  FlaskConical,
  RefreshCcw,
  ScrollText,
  Upload,
} from 'lucide-react';
import { MetricCard, Pill, SectionTitle, Surface } from '../components/workbench/atoms';
import { buildArtifactDownloadUrl, runSupplementTest } from '../lib/workbenchApi';
import type { SupplementRunData } from '../types/api';

type FeedbackTone = 'success' | 'error' | 'info';

function feedbackClass(tone: FeedbackTone) {
  switch (tone) {
    case 'success':
      return 'border-emerald-200 bg-emerald-50 text-emerald-900';
    case 'error':
      return 'border-rose-200 bg-rose-50 text-rose-900';
    default:
      return 'border-sky-200 bg-sky-50 text-sky-900';
  }
}

export function SupplementPage() {
  const scheduleInputRef = useRef<HTMLInputElement | null>(null);
  const courseInputRef = useRef<HTMLInputElement | null>(null);

  const [scheduleFile, setScheduleFile] = useState<File | null>(null);
  const [courseFile, setCourseFile] = useState<File | null>(null);
  const [result, setResult] = useState<SupplementRunData | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: FeedbackTone; message: string } | null>(null);

  const outputUrl = useMemo(
    () => (result?.output_file_name ? buildArtifactDownloadUrl(result.output_file_name) : null),
    [result?.output_file_name],
  );
  const logUrl = useMemo(
    () => (result?.log_file_name ? buildArtifactDownloadUrl(result.log_file_name) : null),
    [result?.log_file_name],
  );

  const stats = result?.stats ?? {};
  const addedCount = Number(stats.successfully_added ?? result?.added_courses.length ?? 0);
  const failedCount = Number(stats.failed_to_add ?? result?.failed_courses.length ?? 0);
  const missingCount = Number(stats.missing_courses ?? 0);

  const handleSchedulePick = (event: ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0] ?? null;
    setScheduleFile(next);
    setFeedback(null);
    event.target.value = '';
  };

  const handleCoursePick = (event: ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0] ?? null;
    setCourseFile(next);
    setFeedback(null);
    event.target.value = '';
  };

  const handleRun = async () => {
    if (!scheduleFile) {
      setFeedback({ tone: 'error', message: '请先上传排课结果 Excel。' });
      return;
    }

    setBusy(true);
    setFeedback(null);

    try {
      const response = await runSupplementTest(scheduleFile, courseFile ?? undefined);
      setResult(response.data ?? null);

      if (!response.success) {
        throw new Error(response.message || '补充测试失败');
      }

      setFeedback({
        tone: 'success',
        message: response.message || '补充测试完成，可直接下载日志和补充后的结果文件。',
      });
    } catch (error) {
      setFeedback({
        tone: 'error',
        message: error instanceof Error ? error.message : '补充测试失败',
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <input
        ref={scheduleInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleSchedulePick}
      />
      <input
        ref={courseInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleCoursePick}
      />

      <SectionTitle
        eyebrow="Phase 3"
        title="课程补充测试工作区"
        description="这里直接调用 scripts/course_supplement_test.py。上传排课结果后即可运行；如果不上传备选课程表，默认复用当前工作台已加载的课程一览表。"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="neutral">脚本直连</Pill>
            <Pill tone="info">{courseFile ? '使用上传课程源' : '默认复用当前课程源'}</Pill>
          </div>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="课程源"
          value={courseFile ? '已覆盖' : '当前会话'}
          hint={courseFile?.name || '未上传新课程表时，默认沿用课程工作台中的课程一览表'}
          tone="ink"
        />
        <MetricCard
          label="成功补入"
          value={String(addedCount)}
          hint={missingCount > 0 ? `候选缺失课程 ${missingCount} 门` : '等待运行脚本'}
          tone="pine"
        />
        <MetricCard
          label="输出工件"
          value={result?.output_file_name ? '已生成' : '未生成'}
          hint={result?.output_file_name || '运行后会生成 Excel 和日志文件'}
          tone="amber"
        />
      </div>

      {feedback ? (
        <div className={`rounded-[1.2rem] border px-4 py-3 text-sm ${feedbackClass(feedback.tone)}`}>
          {feedback.message}
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[0.96fr_1.04fr]">
        <Surface eyebrow="Input" title="文件准备与执行">
          <div className="space-y-4">
            <div className="rounded-[1.25rem] border border-[#e6dbc7] bg-[#fcf7ee] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#1a2620]">排课结果文件</div>
                  <div className="mt-1 text-xs text-[#6a746c]">必传，建议直接使用智能排课页导出的结果 Excel。</div>
                </div>
                <button
                  type="button"
                  onClick={() => scheduleInputRef.current?.click()}
                  className="inline-flex items-center gap-2 rounded-full border border-[#1f4739] bg-[#17362d] px-4 py-2 text-sm font-medium text-[#f9f4ea] transition hover:bg-[#21463a]"
                >
                  <Upload className="h-4 w-4" />
                  选择结果文件
                </button>
              </div>
              <div className="mt-3 break-all rounded-2xl border border-[#eadfcb] bg-white px-4 py-3 text-sm leading-6 text-[#435047]">
                {scheduleFile?.name || '尚未选择排课结果文件'}
              </div>
            </div>

            <div className="rounded-[1.25rem] border border-[#e6dbc7] bg-[#fcf7ee] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#1a2620]">备选课程表</div>
                  <div className="mt-1 text-xs text-[#6a746c]">可选。为空时默认复用课程工作台最近一次导入的课程一览表。</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => courseInputRef.current?.click()}
                    className="inline-flex items-center gap-2 rounded-full border border-[#d7ccb8] bg-white px-4 py-2 text-sm font-medium text-[#223129] transition hover:bg-[#f7efdf]"
                  >
                    <FileSearch className="h-4 w-4" />
                    上传备选表
                  </button>
                  {courseFile ? (
                    <button
                      type="button"
                      onClick={() => setCourseFile(null)}
                      className="inline-flex items-center gap-2 rounded-full border border-[#e1c9c4] bg-[#fff4f1] px-4 py-2 text-sm font-medium text-[#8b4038] transition hover:bg-[#ffe9e5]"
                    >
                      <RefreshCcw className="h-4 w-4" />
                      恢复会话源
                    </button>
                  ) : null}
                </div>
              </div>
              <div className="mt-3 break-all rounded-2xl border border-[#eadfcb] bg-white px-4 py-3 text-sm leading-6 text-[#435047]">
                {courseFile?.name || '未上传时默认使用当前课程工作台中的课程一览表'}
              </div>
            </div>

            <div className="rounded-[1.25rem] border border-[#d9d1bf] bg-[linear-gradient(135deg,rgba(20,48,39,0.98),rgba(44,84,69,0.92))] p-5 text-[#f7f1e5]">
              <div className="text-[0.72rem] uppercase tracking-[0.3em] text-[#d6c59f]">Run Script</div>
              <div className="mt-3 text-lg font-semibold">直接执行补充测试脚本</div>
              <p className="mt-2 text-sm leading-7 text-[#dce6dc]">
                结果会生成在 Web 导出目录里，页面直接给出下载入口，不需要你再找绝对路径。
              </p>
              <button
                type="button"
                onClick={() => {
                  void handleRun();
                }}
                disabled={busy || !scheduleFile}
                className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-5 py-3 text-sm font-medium text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <FlaskConical className="h-4 w-4" />
                {busy ? '脚本运行中...' : '开始补充测试'}
              </button>
            </div>
          </div>
        </Surface>

        <Surface eyebrow="Result" title="补充结果与下载">
          {result ? (
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard label="成功补入" value={String(addedCount)} hint="新增进入结果文件的课程数量" tone="pine" />
                <MetricCard label="无法补入" value={String(failedCount)} hint="脚本已给出失败原因" tone="sand" />
                <MetricCard
                  label="课程源"
                  value={result.course_list_source_type === 'uploaded' ? '上传文件' : '当前会话'}
                  hint={result.course_list_source || '未记录来源'}
                  tone="amber"
                />
              </div>

              <div className="flex flex-wrap gap-2">
                {outputUrl ? (
                  <a
                    href={outputUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-full border border-[#1f4739] bg-[#17362d] px-4 py-2 text-sm font-medium text-[#f9f4ea] transition hover:bg-[#21463a]"
                  >
                    <Download className="h-4 w-4" />
                    下载补充后结果
                  </a>
                ) : null}
                {logUrl ? (
                  <a
                    href={logUrl}
                    download
                    className="inline-flex items-center gap-2 rounded-full border border-[#d7ccb8] bg-white px-4 py-2 text-sm font-medium text-[#223129] transition hover:bg-[#f7efdf]"
                  >
                    <ScrollText className="h-4 w-4" />
                    下载运行日志
                  </a>
                ) : null}
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
                  <div className="mb-3 text-sm font-medium text-[#24312c]">成功补入课程</div>
                  <div className="max-h-[24rem] space-y-3 overflow-y-auto pr-1">
                    {result.added_courses.length === 0 ? (
                      <div className="text-sm text-[#6b756d]">这次没有补入新的课程。</div>
                    ) : (
                      result.added_courses.map((course) => (
                        <div key={`${course.code}-${course.name}`} className="rounded-[0.9rem] border border-[#e3d9c6] bg-white px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Pill tone="success">{course.code}</Pill>
                            <span className="font-medium text-[#24312c]">{course.name}</span>
                            <Pill tone={course.is_online ? 'info' : 'neutral'}>
                              {course.is_online ? '线上' : '线下'}
                            </Pill>
                          </div>
                          <div className="mt-2 text-sm text-[#5a645b]">
                            {course.category} · {course.credits.toFixed(1)} 学分
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
                  <div className="mb-3 text-sm font-medium text-[#24312c]">未补入课程与原因</div>
                  <div className="max-h-[24rem] space-y-3 overflow-y-auto pr-1">
                    {result.failed_courses.length === 0 ? (
                      <div className="text-sm text-[#6b756d]">没有未补入课程。</div>
                    ) : (
                      result.failed_courses.map((course) => (
                        <div key={`${course.code}-${course.name}`} className="rounded-[0.9rem] border border-[#ead5cf] bg-white px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Pill tone="warning">{course.code}</Pill>
                            <span className="font-medium text-[#24312c]">{course.name}</span>
                          </div>
                          <div className="mt-2 space-y-1 text-sm text-[#6f5d39]">
                            {course.reasons.map((reason, index) => (
                              <div key={`${course.code}-${index}`}>{reason}</div>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-[1.2rem] border border-dashed border-[#d9cfbc] bg-[#faf4e7] px-4 py-8 text-sm leading-7 text-[#6b675b]">
              这里会展示补入成功课程、失败原因以及两个下载入口。先上传排课结果，再运行补充测试。
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}

export default SupplementPage;
