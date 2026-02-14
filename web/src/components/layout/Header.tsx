import { GraduationCap } from 'lucide-react'

export function Header() {
  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <GraduationCap className="h-8 w-8 text-blue-600 mr-3" />
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                PUMC智能排课系统
              </h1>
              <p className="text-xs text-gray-500">Web版本 v1.0</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-600">
              当前模式: <span className="text-green-600 font-medium">Web版</span>
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
