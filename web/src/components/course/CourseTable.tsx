import React from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import type { Course, SelectedCourse } from '../../types/models';

interface CourseTableProps {
  courses: Course[];
  selectedCourses: SelectedCourse[];
  onAddCourse: (course: Course, classIndex: number) => void;
  onRemoveCourse: (courseId: string) => void;
  onUpdateCategory: (courseId: string, category: string) => void;
}

const dayNames = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'];

export const CourseTable: React.FC<CourseTableProps> = ({
  courses,
  selectedCourses,
  onAddCourse,
  onRemoveCourse,
  onUpdateCategory: _onUpdateCategory,
}) => {
  const formatTimeSlots = (timeSlots: { day_of_week: number; start_period: number; end_period: number }[]) => {
    if (!timeSlots || timeSlots.length === 0) return '-';
    return timeSlots
      .map((ts) => `${dayNames[ts.day_of_week]} ${ts.start_period}-${ts.end_period}节`)
      .join(', ');
  };

  const isCourseSelected = (courseCode: string, classIndex: number) => {
    return selectedCourses.some(
      (sc) => sc.course.course_code === courseCode && sc.class_index === classIndex
    );
  };

  const getSelectedCourseId = (courseCode: string, classIndex: number) => {
    const selected = selectedCourses.find(
      (sc) => sc.course.course_code === courseCode && sc.class_index === classIndex
    );
    return selected?.id;
  };

  const columnDefs: ColDef[] = [
    {
      headerName: '课程编码',
      field: 'course_code',
      width: 120,
      sortable: true,
      filter: true,
    },
    {
      headerName: '课程名称',
      field: 'course_name',
      width: 200,
      sortable: true,
      filter: true,
    },
    {
      headerName: '班次',
      field: 'class_index',
      width: 80,
      sortable: true,
      valueFormatter: (params: { value: number }) => String(params.value || 0),
    },
    {
      headerName: '教师',
      field: 'teacher',
      width: 100,
      sortable: true,
    },
    {
      headerName: '学分',
      field: 'credits',
      width: 80,
      sortable: true,
    },
    {
      headerName: '类别',
      field: 'category',
      width: 120,
      sortable: true,
    },
    {
      headerName: '校区',
      field: 'campus',
      width: 100,
    },
    {
      headerName: '线上',
      field: 'is_online',
      width: 80,
      cellRenderer: (params: { value: boolean }) => (params.value ? '是' : '否'),
    },
    {
      headerName: '时间',
      width: 200,
      valueGetter: (params: { data: Course }) => formatTimeSlots(params.data.time_slots),
    },
    {
      headerName: '操作',
      width: 120,
      cellRenderer: (params: { data: Course }) => {
        const isSelected = isCourseSelected(params.data.course_code, params.data.class_index);
        return (
          <button
            onClick={() =>
              isSelected
                ? onRemoveCourse(getSelectedCourseId(params.data.course_code, params.data.class_index)!)
                : onAddCourse(params.data, params.data.class_index)
            }
            className={`px-3 py-1 rounded text-sm font-medium ${
              isSelected
                ? 'bg-red-100 text-red-700 hover:bg-red-200'
                : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
            }`}
          >
            {isSelected ? '移除' : '添加'}
          </button>
        );
      },
    },
  ];

  const defaultColDef = {
    resizable: true,
  };

  return (
    <div className="w-full">
      <div className="ag-theme-alpine" style={{ height: 500, width: '100%' }}>
        <AgGridReact
          rowData={courses}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          pagination={true}
          paginationPageSize={20}
          rowSelection="multiple"
          suppressRowClickSelection={true}
        />
      </div>

      <div className="mt-4 text-sm text-gray-600">
        共 {courses?.length || 0} 门课程，已选择 {selectedCourses?.length || 0} 门
      </div>
    </div>
  );
};

export default CourseTable;
