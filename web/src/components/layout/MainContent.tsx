import { ReactNode } from 'react'

interface MainContentProps {
  children: ReactNode
  title: string
}

export function MainContent({ children, title }: MainContentProps) {
  return (
    <main className="flex-1 p-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">{title}</h2>
        {children}
      </div>
    </main>
  )
}
