import React, { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import type { Course } from '../../types/models';

interface CourseSearchProps {
  courses: Course[];
  onSelectCourse: (course: Course) => void;
}

export const CourseSearch: React.FC<CourseSearchProps> = ({
  courses,
  onSelectCourse,
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Course[]>([]);
  const [showResults, setShowResults] = useState(false);

  useEffect(() => {
    if (!courses || courses.length === 0) {
      setResults([]);
      setShowResults(false);
      return;
    }
    
    if (query.length >= 1) {
      const lowerQuery = query.toLowerCase();
      const filtered = courses.filter(
        (course) =>
          (course.course_code && course.course_code.toLowerCase().includes(lowerQuery)) ||
          (course.course_name && course.course_name.toLowerCase().includes(lowerQuery)) ||
          (course.teacher && course.teacher.toLowerCase().includes(lowerQuery))
      );
      setResults(filtered.slice(0, 10));
      setShowResults(true);
    } else {
      setResults([]);
      setShowResults(false);
    }
  }, [query, courses]);

  const handleSelect = (course: Course) => {
    onSelectCourse(course);
    setQuery('');
    setShowResults(false);
  };

  const clearSearch = () => {
    setQuery('');
    setResults([]);
    setShowResults(false);
  };

  return (
    <div className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
        <input
          type="text"
          placeholder="搜索课程编码、名称或教师..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          id="course-search"
          name="course-search"
        />
        {query && (
          <button
            onClick={clearSearch}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {showResults && results.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-80 overflow-auto">
          {results.map((course) => (
            <button
              key={`${course.course_code}-${course.class_index}`}
              onClick={() => handleSelect(course)}
              className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-0"
            >
              <div className="flex justify-between items-start">
                <div>
                  <div className="font-medium text-gray-900">
                    {course.course_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    {course.course_code} · {course.class_index || 0} · {course.teacher || '待定'} · {course.credits}学分
                  </div>
                </div>
                <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                  {course.category}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {showResults && query.length >= 1 && results.length === 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-4 text-center text-gray-500">
          未找到匹配的课程
        </div>
      )}
    </div>
  );
};

export default CourseSearch;
