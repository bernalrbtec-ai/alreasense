import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import TaskList from '../components/tasks/TaskList'
import TaskEventsBox from '../components/tasks/TaskEventsBox'
import TaskModal from '../components/tasks/TaskModal'
import { api } from '../lib/api'

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
  department?: string
  assigned_to?: string
  related_contacts?: any[]
}

interface Department {
  id: string
  name: string
}

interface User {
  id: string
  email: string
  first_name?: string
  last_name?: string
}

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [tasks, setTasks] = useState<Task[]>([])
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])

  // Carregar departamentos e usuários para o modal
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [deptsRes, usersRes] = await Promise.all([
          api.get('/chat/departments/'),
          api.get('/chat/users/')
        ])
        setDepartments(deptsRes.data.results || deptsRes.data || [])
        setUsers(usersRes.data.results || usersRes.data || [])
      } catch (error) {
        console.error('Erro ao carregar dados:', error)
      }
    }
    fetchData()
  }, [])

  const handleTaskClick = async (task: Task) => {
    // Buscar tarefa completa da API para garantir que temos todos os dados necessários
    try {
      const response = await api.get(`/contacts/tasks/${task.id}/`)
      const fullTask = response.data
      setEditingTask(fullTask)
      setShowTaskModal(true)
    } catch (error: any) {
      console.error('Erro ao buscar tarefa completa:', error)
      // Se falhar, tentar usar a tarefa que temos (pode não ter todos os campos)
      setEditingTask(task)
      setShowTaskModal(true)
    }
  }

  const handleEditTaskRequest = (task: Task) => {
    // Chamado pelo TaskList quando precisa editar
    setEditingTask(task)
    setShowTaskModal(true)
  }

  const handleModalSuccess = async () => {
    setShowTaskModal(false)
    setEditingTask(null)
    // Recarregar tarefas será feito pelo TaskList através do onTasksChange
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
          <TaskList 
            onTasksChange={setTasks} 
            onEditTaskRequest={handleEditTaskRequest}
          />
        </div>

        {/* Box de Eventos - Ocupa 1/3 */}
        <div className="lg:col-span-1">
          <div className="sticky top-4" style={{ maxHeight: 'calc(100vh - 2rem)' }}>
            <TaskEventsBox tasks={tasks} onTaskClick={handleTaskClick} />
          </div>
        </div>
      </div>

      {/* Modal de Tarefa (compartilhado entre TaskList e TaskEventsBox) */}
      {showTaskModal && editingTask && (
        <TaskModal
          isOpen={showTaskModal}
          onClose={() => {
            setShowTaskModal(false)
            setEditingTask(null)
          }}
          onSuccess={handleModalSuccess}
          task={editingTask}
          departments={departments}
          users={users}
        />
      )}
    </div>
  )
}
