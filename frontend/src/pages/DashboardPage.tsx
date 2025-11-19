import { useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import TaskList from '../components/tasks/TaskList'

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const { user } = useAuthStore()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-gray-600">
          Tarefas e agenda de {user?.tenant?.name}
        </p>
      </div>

      {/* Lista de Tarefas e Calendário */}
      <TaskList />
    </div>
  )
}
