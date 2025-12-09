import { useState, useEffect, useMemo } from 'react'
import { useAuthStore } from '../stores/authStore'
import TaskList from '../components/tasks/TaskList'
import TaskEventsBox from '../components/tasks/TaskEventsBox'
import WeekSchedule from '../components/tasks/WeekSchedule'
import TaskModal from '../components/tasks/TaskModal'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { CheckCircle, Clock, AlertCircle, Calendar, TrendingUp } from 'lucide-react'
import { isToday, isPast, isFuture } from 'date-fns'

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
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  // Carregar departamentos e usuários para o modal (mesmos endpoints do TaskList)
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [deptsRes, usersRes] = await Promise.all([
          api.get('/auth/departments/'),
          api.get('/auth/users/')
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
    // Forçar recarregamento do TaskList
    setRefreshTrigger(prev => prev + 1)
  }

  // Calcular estatísticas
  const stats = useMemo(() => {
    const total = tasks.length
    const completed = tasks.filter(t => t.status === 'completed').length
    const pending = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length
    const overdue = tasks.filter(t => t.is_overdue && t.status !== 'completed').length
    const today = tasks.filter(t => {
      if (!t.due_date || t.status === 'completed') return false
      return isToday(new Date(t.due_date))
    }).length
    const upcoming = tasks.filter(t => {
      if (!t.due_date || t.status === 'completed') return false
      const taskDate = new Date(t.due_date)
      return isFuture(taskDate) && !isToday(taskDate)
    }).length

    return {
      total,
      completed,
      pending,
      overdue,
      today,
      upcoming,
    }
  }, [tasks])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-gray-600">
          Visão geral de tarefas e compromissos de {user?.tenant?.name}
        </p>
      </div>

      {/* Cards de Estatísticas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Total de Tarefas</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-lg">
              <Calendar className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Pendentes</p>
              <p className="text-2xl font-bold text-orange-600">{stats.pending}</p>
            </div>
            <div className="p-3 bg-orange-100 rounded-lg">
              <Clock className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Atrasadas</p>
              <p className="text-2xl font-bold text-red-600">{stats.overdue}</p>
            </div>
            <div className="p-3 bg-red-100 rounded-lg">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Concluídas</p>
              <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
            </div>
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </Card>
      </div>

      {/* Compromissos da Semana */}
      <WeekSchedule tasks={tasks} onTaskClick={handleTaskClick} />

      {/* Layout: Calendário/Lista + Box de Eventos */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Calendário/Lista - Ocupa 2/3 */}
        <div className="lg:col-span-2">
          <TaskList 
            onTasksChange={setTasks} 
            onEditTaskRequest={handleEditTaskRequest}
            refreshTrigger={refreshTrigger}
            hideActions={true}
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
