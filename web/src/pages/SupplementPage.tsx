import { type ChangeEvent, useMemo, useRef, useState } from 'react';
import {
  Download,
  FileSearch,
  FlaskConical,
  RefreshCcw,
  Upload,
} from 'lucide-react';
import { MetricCard, Pill, Surface } from '../components/workbench/atoms';
import { buildArtifactDownloadUrl, runSupplementTest } from '../lib/workbenchApi';
import type { SupplementRunData } from '../types/api';

type FeedbackTone = 'success' | 'error' | 'info';

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
  const stats = result?.stats ?? {};
  const addedCount = Number(stats.successfully_added ?? result?.added_courses.length ?? 0);
  const failedCount = Number(stats.failed_to_add ?? result?.failed_courses.length ?? 0);
  const missingCount = Number(stats.missing_courses ?? 0);

  const handleSchedulePick = (event: ChangeEvent<HTMLInputElement>) => {
    setScheduleFile(event.target.files?.[0] ?? null);
    setFeedback(null);
    event.target.value = '';
  };

  const handleCoursePick = (event: ChangeEvent<HTMLInputElement>) => {
    setCourseFile(event.target.files?.[0] ?? null);
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
      if (!response.success) throw new Error(response.message || '补充测试失败');
      setFeedback({ tone: 'success', message: response.message || '补充测试完成。' });
    } catch (error) {
      setFeedback({ tone: 'error', message: error instanceof Error ? error.message : '补充测试失败' });
    } finally {
      setBusy(false);
    }
  };

  const fileCard = (
    label: string,
    required: boolean,
    file: File | null,
    onPick: () => void,
    onClear?: () => void,
  ) => (
    <div className="rounded-lg border px-4 py-3"
         style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{label}</p>
            <span className={required ? 'tag tag-red' : 'tag tag-gray'}>{required ? '必选' : '可选'}</span>
          </div>
          <p className="mt-1 truncate font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
            {file?.name || (required ? '尚未选择文件' : '不上传则使用本次会话已导入的课程表')}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onPick} className={required ? 'btn-primary' : 'btn-ghost'}>
            {required ? <Upload className="h-3.5 w-3.5" /> : <FileSearch className="h-3.5 w-3.5" />}
            选择
          </button>
          {file && onClear && (
            <button type="button" onClick={onClear} className="btn-ghost">
              <RefreshCcw className="h-3.5 w-3.5" />
              清除
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-5">
      <input ref={scheduleInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleSchedulePick} />
      <input ref={courseInputRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={handleCoursePick} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em]" style={{ color: 'var(--text-muted)' }}>
            Supplement Lab
          </p>
          <h2 className="mt-0.5 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>补充测试</h2>
        </div>
        <div className="flex gap-2">
          <Pill tone="neutral">脚本直连</Pill>
          <Pill tone={courseFile ? 'info' : 'neutral'}>{courseFile ? '上传课程源' : '会话课程源'}</Pill>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="课程源" value={courseFile ? '已覆盖' : '当前会话'} hint={courseFile?.name || '使用工作台课程'} tone="ink" />
        <MetricCard label="成功补入" value={String(addedCount)} hint={missingCount ? `候选缺失 ${missingCount} 门` : '等待运行'} tone="pine" />
        <MetricCard label="输出工件" value={result?.output_file_name ? '已生成' : '未生成'} hint="Excel + 日志" tone="teal" />
      </div>

      {feedback && (
        <div
          role={feedback.tone === 'error' ? 'alert' : 'status'}
          aria-live="polite"
          className="rounded-lg border px-4 py-3 text-sm"
          style={feedback.tone === 'error'
            ? { borderColor: '#fca5a5', background: '#fff5f5', color: '#991b1b' }
            : { borderColor: '#99f6e4', background: '#f0fdfb', color: '#0f766e' }}
        >
          {feedback.message}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <Surface>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>文件与执行</h3>
            <span className="tag tag-gray">INPUT</span>
          </div>
          <div className="space-y-3">
            {fileCard('排课结果 Excel', true, scheduleFile, () => scheduleInputRef.current?.click())}
            <p className="-mt-1 px-1 text-[11px]" style={{ color: 'var(--text-muted)' }}>
              「排课」页导出的 xlsx，记录已排喗的课程与占用的时间段。
            </p>
            {fileCard('原始课程一览表', false, courseFile, () => courseInputRef.current?.click(), () => setCourseFile(null))}
            <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border-card)', background: 'var(--bg-sidebar)' }}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--text-on-dark-muted)' }}>
                Run Script
              </p>
              <p className="mt-1 text-sm font-medium text-white">执行补充测试并生成工件</p>
              <button
                type="button"
                onClick={() => { void handleRun(); }}
                disabled={busy || !scheduleFile}
                className="btn-primary mt-4 w-full justify-center"
              >
                <FlaskConical className="h-4 w-4" />
                {busy ? '运行中…' : '开始补充测试'}
              </button>
            </div>
          </div>
        </Surface>

        <Surface>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>运行结果</h3>
            <div className="flex gap-2">
              {outputUrl && (
                <a href={outputUrl} download className="btn-primary"><Download className="h-3.5 w-3.5" />结果 Excel</a>
              )}

            </div>
          </div>

          {!result ? (
            <div className="rounded-lg border border-dashed py-12 text-center text-xs"
                 style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
              上传排课结果并运行后，此处显示补入课程与失败原因。
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-2">
                <MetricCard label="成功" value={String(addedCount)} hint="补入课程" tone="pine" />
                <MetricCard label="失败" value={String(failedCount)} hint="未补入" tone="sand" />
                <MetricCard label="来源" value={result.course_list_source_type === 'uploaded' ? '上传文件' : '当前会话'} hint="课程源" tone="ink" />
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                <ResultList
                  title="成功补入"
                  empty="本次没有补入新课程。"
                  items={result.added_courses.map((course) => ({
                    key: `${course.code}-${course.name}`,
                    code: course.code,
                    title: course.name,
                    detail: `${course.category} · ${course.credits.toFixed(1)} 学分 · ${course.is_online ? '线上' : '线下'}`,
                    tone: 'success' as const,
                  }))}
                />
                <ResultList
                  title="未补入"
                  empty="没有未补入课程。"
                  items={result.failed_courses.map((course) => ({
                    key: `${course.code}-${course.name}`,
                    code: course.code,
                    title: course.name,
                    detail: course.reasons.join('；'),
                    tone: 'warning' as const,
                  }))}
                />
              </div>
            </div>
          )}
        </Surface>
      </div>
    </div>
  );
}

interface ResultListProps {
  title: string;
  empty: string;
  items: Array<{ key: string; code: string; title: string; detail: string; tone: 'success' | 'warning' }>;
}

function ResultList({ title, empty, items }: ResultListProps) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: 'var(--border-subtle)', background: '#faf9f6' }}>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--text-muted)' }}>{title}</p>
      {items.length === 0 ? (
        <p className="py-4 text-center text-xs" style={{ color: 'var(--text-muted)' }}>{empty}</p>
      ) : (
        <div className="max-h-72 space-y-1.5 overflow-y-auto">
          {items.map((item) => (
            <div key={item.key} className="rounded-md border bg-white px-3 py-2" style={{ borderColor: 'var(--border-subtle)' }}>
              <div className="flex items-center gap-2">
                <Pill tone={item.tone}>{item.code}</Pill>
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{item.title}</span>
              </div>
              <p className="mt-1 text-[11px] leading-5" style={{ color: 'var(--text-secondary)' }}>{item.detail}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default SupplementPage;
