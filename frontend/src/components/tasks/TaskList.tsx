import { useState, useEffect } from 'react'
import { Plus, CheckCircle, Clock, AlertCircle, XCircle, Calendar, List, Filter, User, Users, Edit } from 'lucide-react'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast } from '../../lib/toastHelper'
import { Button } from '../ui/Button'
import LoadingSpinner from '../ui/LoadingSpinner'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, isToday, addMonths, subMonths } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import TaskModal from './TaskModal'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  status_display: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  priority_display: string
  due_date?: string
  assigned_to?: string
  assigned_to_name?: string
  created_by_name?: string
  department_name: string
  related_contacts: Array<{ id: string; name: string; phone: string }>
  created_at: string
  is_overdue: boolean
  has_contacts: boolean
  can_edit: boolean
  can_delete: boolean
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

interface TaskListProps {
  departmentId?: string
  contactId?: string
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-blue-100 text-blue-700 border-blue-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  completed: 'bg-green-100 text-green-700 border-green-200',
  cancelled: 'bg-gray-100 text-gray-700 border-gray-200',
}

export default function TaskList({ departmentId, contactId }: TaskListProps) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [filters, setFilters] = useState({
    status: '',
    department: departmentId || '',
    assigned_to: '',
    my_tasks: false,
    created_by_me: false,
    overdue: false,
  })

  useEffect(() => {
    fetchTasks()
    fetchDepartments()
    fetchUsers()
  }, [filters, departmentId, contactId])

  const fetchTasks = async () => {
    try {
      setLoading(true)
      const params: Record<string, string> = {}
      
      if (filters.status) params.status = filters.status
      if (filters.department) params.department = filters.department
      if (filters.assigned_to) params.assigned_to = filters.assigned_to
      if (filters.my_tasks) params.my_tasks = 'true'
      if (filters.created_by_me) params.created_by_me = 'true'
      if (filters.overdue) params.overdue = 'true'
      if (contactId) params.contact_id = contactId

      const response = await api.get('/contacts/tasks/', { params })
      setTasks(response.data.results || response.data)
    } catch (error: any) {
      console.error('Erro ao buscar tarefas:', error)
      showErrorToast('Erro ao carregar tarefas')
    } finally {
      setLoading(false)
    }
  }

  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/')
      setDepartments(response.data.results || response.data)
    } catch (error) {
      console.error('Erro ao buscar departamentos:', error)
    }
  }

  const fetchUsers = async () => {
    try {
      const response = await api.get('/auth/users/')
      setUsers(response.data.results || response.data)
    } catch (error) {
      console.error('Erro ao buscar usuários:', error)
    }
  }

  const handleComplete = async (taskId: string) => {
    try {
      await api.post(`/contacts/tasks/${taskId}/complete/`)
      showSuccessToast('Tarefa marcada como concluída')
      fetchTasks()
    } catch (error: any) {
      console.error('Erro ao concluir tarefa:', error)
      showErrorToast(error.response?.data?.detail || 'Erro ao concluir tarefa')
    }
  }

  const handleDelete = async (taskId: string) => {
    if (!confirm('Tem certeza que deseja excluir esta tarefa?')) {
      return
    }

    try {
      await api.delete(`/contacts/tasks/${taskId}/`)
      showSuccessToast('Tarefa excluída com sucesso')
      fetchTasks()
    } catch (error: any) {
      console.error('Erro ao excluir tarefa:', error)
      showErrorToast(error.response?.data?.detail || 'Erro ao excluir tarefa')
    }
  }

  const handleEdit = (task: Task) => {
    setEditingTask(task)
    setShowTaskModal(true)
  }

  const handleCreate = () => {
    setEditingTask(null)
    setShowTaskModal(true)
  }

  const handleModalSuccess = () => {
    setShowTaskModal(false)
    setEditingTask(null)
    fetchTasks()
  }

  // Calendário
  const monthStart = startOfMonth(currentMonth)
  const monthEnd = endOfMonth(currentMonth)
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd })
  
  // Adicionar dias do início da semana antes do mês
  const firstDayOfWeek = monthStart.getDay()
  const daysBeforeMonth = Array.from({ length: firstDayOfWeek }, (_, i) => {
    const date = new Date(monthStart)
    date.setDate(date.getDate() - (firstDayOfWeek - i))
    return date
  })
  
  // Adicionar dias do fim da semana após o mês
  const lastDayOfWeek = monthEnd.getDay()
  const daysAfterMonth = Array.from({ length: 6 - lastDayOfWeek }, (_, i) => {
    const date = new Date(monthEnd)
    date.setDate(date.getDate() + (i + 1))
    return date
  })
  
  const allDays = [...daysBeforeMonth, ...daysInMonth, ...daysAfterMonth]
  
  const getTasksForDate = (date: Date) => {
    return tasks.filter(task => {
      if (!task.due_date) return false
      const taskDate = new Date(task.due_date)
      return isSameDay(taskDate, date)
    })
  }

  if (loading && tasks.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Tarefas e Agenda</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleCreate}>
            <Plus className="h-4 w-4 mr-1" />
            Nova Tarefa
          </Button>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Status</label>
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              <option value="pending">Pendente</option>
              <option value="in_progress">Em Andamento</option>
              <option value="completed">Concluída</option>
              <option value="cancelled">Cancelada</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Departamento</label>
            <select
              value={filters.department}
              onChange={(e) => setFilters({ ...filters, department: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              {departments.map(dept => (
                <option key={dept.id} value={dept.id}>{dept.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Atribuída Para</label>
            <select
              value={filters.assigned_to}
              onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              {users.map(user => (
                <option key={user.id} value={user.id}>
                  {user.first_name && user.last_name 
                    ? `${user.first_name} ${user.last_name}`
                    : user.email}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={filters.my_tasks}
              onChange={(e) => setFilters({ ...filters, my_tasks: e.target.checked })}
              className="rounded border-gray-300"
            />
            <span>Minhas tarefas atribuídas</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={filters.created_by_me}
              onChange={(e) => setFilters({ ...filters, created_by_me: e.target.checked })}
              className="rounded border-gray-300"
            />
            <span>Tarefas que criei</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={filters.overdue}
              onChange={(e) => setFilters({ ...filters, overdue: e.target.checked })}
              className="rounded border-gray-300"
            />
            <span>Atrasadas</span>
          </label>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setViewMode('list')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            viewMode === 'list'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <List className="h-4 w-4 inline mr-2" />
          Lista
        </button>
        <button
          onClick={() => setViewMode('calendar')}
          className={`px-4 py-2 font-medium text-sm border-b-2 transition-colors ${
            viewMode === 'calendar'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Calendar className="h-4 w-4 inline mr-2" />
          Calendário
        </button>
      </div>

      {/* Conteúdo */}
      {viewMode === 'list' ? (
        <div className="space-y-2">
          {tasks.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Clock className="h-12 w-12 mx-auto mb-2 text-gray-400" />
              <p>Nenhuma tarefa encontrada</p>
            </div>
          ) : (
            tasks.map(task => (
              <div
                key={task.id}
                className={`border rounded-lg p-4 ${
                  task.is_overdue && task.status !== 'completed'
                    ? 'border-red-300 bg-red-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[task.status]}`}>
                        {task.status_display}
                      </span>
                      <span className={`text-xs px-2 py-1 rounded ${PRIORITY_COLORS[task.priority]}`}>
                        {task.priority_display}
                      </span>
                      {task.is_overdue && task.status !== 'completed' && (
                        <span className="text-xs px-2 py-1 rounded bg-red-100 text-red-700 border border-red-200">
                          <AlertCircle className="h-3 w-3 inline mr-1" />
                          Atrasada
                        </span>
                      )}
                    </div>
                    <h4 className="font-medium text-gray-900 mb-1">{task.title}</h4>
                    {task.description && (
                      <p className="text-sm text-gray-600 mb-2">{task.description}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
                      {task.due_date && (
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {format(new Date(task.due_date), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
                        </span>
                      )}
                      {task.assigned_to_name && (
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {task.assigned_to_name}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Users className="h-3 w-3" />
                        {task.department_name}
                      </span>
                      {task.has_contacts && (
                        <span className="text-blue-600">
                          {task.related_contacts.length} contato(s) relacionado(s)
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 ml-4">
                    {task.status !== 'completed' && (
                      <button
                        onClick={() => handleComplete(task.id)}
                        className="p-2 text-green-600 hover:bg-green-50 rounded transition-colors"
                        title="Concluir"
                      >
                        <CheckCircle className="h-4 w-4" />
                      </button>
                    )}
                    {task.can_edit && (
                      <button
                        onClick={() => handleEdit(task)}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        title="Editar"
                      >
                        <Edit className="h-4 w-4" />
                      </button>
                    )}
                    {task.can_delete && (
                      <button
                        onClick={() => handleDelete(task.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Excluir"
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Navegação do calendário */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
              className="p-2 hover:bg-gray-100 rounded transition-colors"
            >
              ←
            </button>
            <h4 className="font-semibold text-gray-900">
              {format(currentMonth, 'MMMM yyyy', { locale: ptBR })}
            </h4>
            <button
              onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
              className="p-2 hover:bg-gray-100 rounded transition-colors"
            >
              →
            </button>
          </div>

          {/* Calendário */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Dias da semana */}
            <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-200">
              {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map(day => (
                <div key={day} className="p-2 text-center text-xs font-medium text-gray-700">
                  {day}
                </div>
              ))}
            </div>

            {/* Dias do mês */}
            <div className="grid grid-cols-7">
              {allDays.map((day, idx) => {
                const dayTasks = getTasksForDate(day)
                const isCurrentMonth = isSameMonth(day, currentMonth)
                const isCurrentDay = isToday(day)

                return (
                  <div
                    key={idx}
                    className={`min-h-[100px] border border-gray-100 p-1 ${
                      isCurrentMonth ? 'bg-white' : 'bg-gray-50'
                    } ${isCurrentDay ? 'bg-blue-50' : ''}`}
                  >
                    <div className={`text-xs mb-1 ${isCurrentMonth ? 'text-gray-900' : 'text-gray-400'} ${isCurrentDay ? 'font-bold text-blue-600' : ''}`}>
                      {format(day, 'd')}
                    </div>
                    <div className="space-y-1">
                      {dayTasks.slice(0, 3).map(task => (
                        <div
                          key={task.id}
                          className={`text-xs p-1 rounded truncate cursor-pointer ${
                            task.is_overdue && task.status !== 'completed'
                              ? 'bg-red-100 text-red-700 border border-red-200'
                              : task.status === 'completed'
                              ? 'bg-green-100 text-green-700 border border-green-200'
                              : 'bg-blue-100 text-blue-700 border border-blue-200'
                          }`}
                          title={task.title}
                          onClick={() => handleEdit(task)}
                        >
                          {task.title}
                        </div>
                      ))}
                      {dayTasks.length > 3 && (
                        <div className="text-xs text-gray-500 px-1">
                          +{dayTasks.length - 3} mais
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Modal de Tarefa */}
      {showTaskModal && (
        <TaskModal
          isOpen={showTaskModal}
          onClose={() => {
            setShowTaskModal(false)
            setEditingTask(null)
          }}
          onSuccess={handleModalSuccess}
          task={editingTask}
          initialDepartmentId={departmentId}
          initialContactId={contactId}
          departments={departments}
          users={users}
        />
      )}
    </div>
  )
}

