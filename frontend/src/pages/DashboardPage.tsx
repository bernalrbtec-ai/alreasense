import { useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import TaskList from '../components/tasks/TaskList'
import TaskEventsBox from '../components/tasks/TaskEventsBox'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  status_display: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  priority_display: string
  due_date?: string
  assigned_to_name?: string
  department_name: string
  created_at: string
  is_overdue: boolean
  can_edit: boolean
}

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [tasks, setTasks] = useState<Task[]>([])

  const handleTaskClick = (task: Task) => {
    // Scroll para o calendário e destacar a tarefa
    // Por enquanto, apenas log
    console.log('Task clicked:', task)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-gray-600">
          Tarefas e agenda de {user?.tenant?.name}
        </p>
      </div>

      {/* Layout: Calendário/Lista + Box de Eventos */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calendário/Lista - Ocupa 2/3 */}
        <div className="lg:col-span-2">
          <TaskList onTasksChange={setTasks} />
        </div>

        {/* Box de Eventos - Ocupa 1/3 */}
        <div className="lg:col-span-1">
          <div className="sticky top-4" style={{ maxHeight: 'calc(100vh - 2rem)' }}>
            <TaskEventsBox tasks={tasks} onTaskClick={handleTaskClick} />
          </div>
        </div>
      </div>
    </div>
  )
}
