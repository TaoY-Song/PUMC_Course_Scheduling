import { useState, useEffect } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { MainContent } from './components/layout/MainContent';
import { healthCheck } from './api/client';
import { FileUpload } from './components/common/FileUpload';
import { Button } from './components/common/Button';
import { CourseTable } from './components/course/CourseTable';
import { CourseSearch } from './components/course/CourseSearch';
import { ConfigPanel } from './components/scheduling/ConfigPanel';
import { ControlPanel } from './components/scheduling/ControlPanel';
import { ProgressDisplay } from './components/scheduling/ProgressDisplay';
import { ResultPanel } from './components/scheduling/ResultPanel';
import { CreditSettings } from './components/credit/CreditSettings';
import { useCourses, useCredits, useImportExport } from './hooks/useApi';
import { useScheduling } from './hooks/useScheduling';
import type { SelectedCourse } from './types/models';

function App() {
  const [activeTab, setActiveTab] = useState('courses');
  const [health, setHealth] = useState<{ status: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initDone, setInitDone] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<{success: boolean; message: string; warnings: string[]} | null>(null);

  const [selectedCourse, setSelectedCourse] = useState<SelectedCourse | null>(null);

  const {
    courses,
    selectedCourses,
    loadCourses,
    fetchSelectedCourses,
    addCourse,
    removeCourse,
  } = useCourses();

  const {
    fetchCreditStatus,
  } = useCredits();

  const {
    config,
    progress,
    lastResult,
    fetchConfig,
    saveConfig,
    execute,
    cancel,
  } = useScheduling();

  const { importSelectedCourses, exportSelectedCourses, isExporting, isImporting } = useImportExport();

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await healthCheck();
        setHealth(data);
      } catch (err) {
        setError('无法连接到后端服务');
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
  }, []);

  useEffect(() => {
    if (health && !initDone) {
      setInitDone(true);
      Promise.all([
        fetchConfig(),
        fetchSelectedCourses(),
        fetchCreditStatus()
      ]).catch(console.error);
    }
  }, [health, initDone]);

  const handleFileUpload = async (file: File) => {
    setUploadFeedback(null);
    try {
      const response = await loadCourses(file);
      
      const feedback = {
        success: response?.success ?? true,
        message: response?.message ?? '加载成功',
        warnings: response?.warnings ?? []
      };
      setUploadFeedback(feedback);
      
      await fetchCreditStatus();
    } catch (err) {
      setUploadFeedback({
        success: false,
        message: err instanceof Error ? err.message : '上传失败，请重试',
        warnings: []
      });
    }
  };

  const handleImport = async (file: File) => {
    console.log('[App] Import started:', file.name);
    try {
      const result = await importSelectedCourses(file);
      console.log('[App] Import result:', result);
      try {
        await fetchSelectedCourses();
      } catch (e) {
        console.error('[App] fetchSelectedCourses error:', e);
      }
      try {
        await fetchCreditStatus();
      } catch (e) {
        console.error('[App] fetchCreditStatus error:', e);
      }
      alert('导入成功！');
    } catch (err) {
      console.error('[App] Import error:', err);
      alert('导入失败: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  };

  const handleExportSelected = async () => {
    const timestamp = new Date().toISOString().slice(0, 10);
    const fileName = `selected_courses_${timestamp}.xlsx`;
    try {
      await exportSelectedCourses(fileName);
      alert(`导出成功！\n文件已保存为: ${fileName}\n位置: 项目根目录`);
    } catch (error) {
      alert('导出失败，请重试');
    }
  };

  const handleExecuteScheduling = async () => {
    await execute();
    await fetchCreditStatus();
  };

  const getTabTitle = (tab: string) => {
    const titles: Record<string, string> = {
      courses: '课程管理',
      scheduling: '智能排课',
      export: '导入导出',
      settings: '系统设置',
    };
    return titles[tab] || '未知页面';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">正在连接服务...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center p-8 bg-white rounded-lg shadow-md max-w-md">
          <h1 className="text-2xl font-bold text-red-600 mb-4">连接失败</h1>
          <p className="text-gray-600">{error}</p>
          <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-700">
            <p className="font-medium">请确保后端服务已启动:</p>
            <code className="block mt-2 bg-gray-800 text-white px-3 py-2 rounded">
              python start_web.py
            </code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />

      <div className="flex flex-1">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <MainContent title={getTabTitle(activeTab)}>
          {activeTab === 'courses' && (
            <div className="space-y-6">
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      console.log('[App] File selected directly:', file.name);
                      handleFileUpload(file);
                    }
                  }}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  id="course-excel-file"
                  name="course-excel-file"
                />
                <p className="mt-4 text-sm text-gray-600">点击上方按钮选择Excel文件</p>
              </div>

              {uploadFeedback && (
                <div className={`p-4 rounded-lg ${uploadFeedback.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className="flex items-center">
                    {uploadFeedback.success ? (
                      <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 text-red-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                    <span className={uploadFeedback.success ? 'text-green-800' : 'text-red-800'}>
                      {uploadFeedback.message}
                    </span>
                  </div>
                  {uploadFeedback.warnings.length > 0 && (
                    <div className="mt-2 text-sm text-amber-700">
                      <div className="font-medium">⚠️ 警告:</div>
                      <ul className="list-disc list-inside mt-1">
                        {uploadFeedback.warnings.map((warn, idx) => (
                          <li key={idx}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <CourseSearch
                    courses={courses}
                    onSelectCourse={async (course) => {
                      const exists = selectedCourses.some(
                        (sc) => sc.course.course_code === course.course_code &&
                               sc.class_index === course.class_index
                      );
                      if (exists) {
                        alert(`课程 ${course.course_name} (班次${course.class_index}) 已存在于已选列表中`);
                        return;
                      }
                      await addCourse(course.course_code, course.class_index || 0);
                      await fetchSelectedCourses();
                      await fetchCreditStatus();
                    }}
                  />

                  <CourseTable
                    courses={courses}
                    selectedCourses={selectedCourses}
                    onAddCourse={async (course, classIndex) => {
                      const exists = selectedCourses.some(
                        (sc) => sc.course.course_code === course.course_code &&
                               sc.class_index === classIndex
                      );
                      if (exists) {
                        alert(`课程 ${course.course_name} (班次${classIndex}) 已存在于已选列表中`);
                        return;
                      }
                      await addCourse(course.course_code, classIndex);
                      await fetchSelectedCourses();
                      await fetchCreditStatus();
                    }}
                    onRemoveCourse={async (courseId) => {
                      console.log('[App] Remove course:', courseId);
                      await removeCourse(courseId);
                      await fetchSelectedCourses();
                      await fetchCreditStatus();
                    }}
                    onUpdateCategory={() => Promise.resolve()}
                  />
                </div>

                <div className="space-y-4">
                  <div className="bg-white rounded-lg shadow p-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-4">已选课程</h3>
                    {!selectedCourses || selectedCourses.length === 0 ? (
                      <p className="text-gray-500 text-sm">暂无已选课程</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedCourses.map((sc) => (
                          <div
                            key={sc.id}
                            className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                              selectedCourse?.id === sc.id
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                            onClick={() => setSelectedCourse(sc)}
                          >
                            <div className="flex justify-between items-start">
                              <div>
                                <p className="font-medium text-gray-900">
                                  {sc.course.course_name}
                                </p>
                                <p className="text-sm text-gray-500">
                                  {sc.course.course_code}
                                </p>
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeCourse(sc.id);
                                  fetchSelectedCourses();
                                  fetchCreditStatus();
                                }}
                                className="text-red-500 hover:text-red-700 text-sm"
                              >
                                移除
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {selectedCourse && (
                    <div className="bg-white rounded-lg shadow p-6">
                      <h3 className="text-lg font-medium text-gray-900 mb-4">时间段管理</h3>
                      <p className="text-gray-500">课程: {selectedCourse.course.course_name}</p>
                      <p className="text-sm text-gray-400 mt-2">时间段编辑功能开发中...</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'scheduling' && (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
              <div className="lg:col-span-1 space-y-6">
                <ConfigPanel
                  config={config}
                  onChange={saveConfig}
                />
                <ControlPanel
                  status={progress.status}
                  selectedCount={selectedCourses?.length || 0}
                  onStart={handleExecuteScheduling}
                  onCancel={cancel}
                  onReset={() => {}}
                />
              </div>

              <div className="lg:col-span-3 space-y-6">
                <ProgressDisplay progress={progress} />
                <ResultPanel
                  result={lastResult}
                />
              </div>
            </div>
          )}

          {activeTab === 'export' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">导入已选课程</h3>
                  <FileUpload
                    onFileSelect={handleImport}
                    accept=".xlsx,.xls"
                    label={isImporting ? "导入中..." : "选择Excel文件"}
                    description="点击或拖拽文件到此处上传"
                  />
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">导出已选课程</h3>
                  <p className="text-gray-600 mb-4">将当前已选课程导出为Excel文件</p>
                  <Button
                    variant="primary"
                    onClick={handleExportSelected}
                    disabled={isExporting || !selectedCourses || selectedCourses.length === 0}
                  >
                    {isExporting ? '导出中...' : '导出已选课程'}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'settings' && (
            <div className="space-y-6">
              <CreditSettings onSave={fetchCreditStatus} />
            </div>
          )}
        </MainContent>
      </div>
    </div>
  );
}

export default App;
