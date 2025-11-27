import { useState, useEffect } from 'react'
import { Plus, Calendar, Clock, User, Search, XCircle, AlertCircle, MoreVertical } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import TaskModal from '../components/tasks/TaskModal'
import { api } from '../lib/api'
import { showErrorToast } from '../lib/toastHelper'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  due_date?: string
  assigned_to?: string
  assigned_to_data?: {
    id: string
    email: string
    first_name?: string
    last_name?: string
  }
  created_by?: string
  created_by_data?: {
    id: string
    email: string
    first_name?: string
    last_name?: string
  }
  department?: string
  department_data?: {
    id: string
    name: string
  }
  related_contacts?: Array<{
    id: string
    name: string
    phone: string
  }>
  task_type: 'task' | 'agenda'
  include_in_notifications: boolean
  created_at: string
  updated_at: string
}

interface TaskStats {
  total: number
  pending: number
  in_progress: number
  completed: number
  cancelled: number
  my_assigned: number
  overdue: number
  with_due_date: number
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

export default function AgendaPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [stats, setStats] = useState<TaskStats>({
    total: 0,
    pending: 0,
    in_progress: 0,
    completed: 0,
    cancelled: 0,
    my_assigned: 0,
    overdue: 0,
    with_due_date: 0
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('active') // 'active' = exclui concluídas por padrão
  const [typeFilter, setTypeFilter] = useState<string>('all') // 'all', 'task', 'agenda'
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const [myTasks, setMyTasks] = useState(false)
  const [overdue, setOverdue] = useState(false)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [searchExpanded, setSearchExpanded] = useState(false)

  useEffect(() => {
    loadTasks()
    loadStats()
  }, [statusFilter, typeFilter, priorityFilter, myTasks, overdue, searchTerm])

  // Carregar departamentos e usuários para o modal
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

  const loadTasks = async () => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams()
      
      // Se houver busca, incluir todas as tarefas (incluindo concluídas)
      // Caso contrário, excluir concluídas por padrão (statusFilter='active')
      if (statusFilter === 'active' && !searchTerm) {
        // Quando statusFilter='active' e não há busca, excluir concluídas
        // Não adicionar filtro de status - vamos buscar todas e filtrar no frontend
      } else if (statusFilter !== 'all') {
        params.append('status', statusFilter)
      }
      // Se houver busca, não filtrar por status (incluir todas, incluindo concluídas)
      
      if (typeFilter !== 'all') {
        params.append('task_type', typeFilter)
      }
      if (priorityFilter !== 'all') {
        params.append('priority', priorityFilter)
      }
      if (myTasks) {
        params.append('my_tasks', 'true')
      }
      if (overdue) {
        params.append('overdue', 'true')
      }
      if (searchTerm) {
        params.append('search', searchTerm)
      }

      const response = await api.get(`/contacts/tasks/?${params.toString()}`)
      let tasksData = response.data.results || response.data
      
      // Se não houver busca e statusFilter for 'active', excluir concluídas
      if (statusFilter === 'active' && !searchTerm) {
        tasksData = tasksData.filter((task: Task) => task.status !== 'completed')
      }
      
      setTasks(tasksData)
    } catch (error: any) {
      console.error('Erro ao carregar tarefas:', error)
      showErrorToast('carregar', 'Tarefas')
    } finally {
      setIsLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await api.get('/contacts/tasks/stats/')
      setStats(response.data)
    } catch (error: any) {
      console.error('Erro ao carregar estatísticas:', error)
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Sem data'
    const date = new Date(dateString)
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'in_progress':
        return 'bg-blue-100 text-blue-800'
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'cancelled':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Pendente'
      case 'in_progress':
        return 'Em Andamento'
      case 'completed':
        return 'Concluída'
      case 'cancelled':
        return 'Cancelada'
      default:
        return status
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'low':
        return 'bg-green-100 text-green-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'high':
        return 'bg-orange-100 text-orange-800'
      case 'urgent':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'low':
        return 'Baixa'
      case 'medium':
        return 'Média'
      case 'high':
        return 'Alta'
      case 'urgent':
        return 'Urgente'
      default:
        return priority
    }
  }

  const isOverdue = (dueDate?: string) => {
    if (!dueDate) return false
    return new Date(dueDate) < new Date() && statusFilter !== 'completed'
  }

  const handleNewTask = () => {
    setEditingTask(null)
    setShowTaskModal(true)
  }

  const handleModalSuccess = () => {
    setShowTaskModal(false)
    setEditingTask(null)
    loadTasks()
    loadStats()
  }

  const filteredTasks = tasks.filter(task => {
    // Se houver busca, incluir todas as tarefas (incluindo concluídas)
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase()
      return (
        task.title.toLowerCase().includes(searchLower) ||
        task.description?.toLowerCase().includes(searchLower) ||
        task.assigned_to_data?.email.toLowerCase().includes(searchLower)
      )
    }
    // Se não houver busca e statusFilter for 'active', já foi filtrado no loadTasks
    // Mas vamos garantir aqui também para segurança
    if (statusFilter === 'active' && task.status === 'completed') {
      return false
    }
    return true
  })

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agenda e Tarefas</h1>
          <p className="text-sm text-gray-500 mt-1">Gerencie seus compromissos e pendências</p>
        </div>
        <Button onClick={handleNewTask}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Tarefa
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500">Total</div>
          <div className="text-2xl font-bold">{stats.total}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Pendentes</div>
          <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Em Andamento</div>
          <div className="text-2xl font-bold text-blue-600">{stats.in_progress}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Concluídas</div>
          <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Canceladas</div>
          <div className="text-2xl font-bold text-gray-600">{stats.cancelled}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Minhas</div>
          <div className="text-2xl font-bold">{stats.my_assigned}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Atrasadas</div>
          <div className="text-2xl font-bold text-red-600">{stats.overdue}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Com Data</div>
          <div className="text-2xl font-bold">{stats.with_due_date}</div>
        </Card>
      </div>

      {/* Filtros */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Ícone de lupa - quando não expandido */}
          {!searchExpanded && (
            <button
              onClick={() => setSearchExpanded(true)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="Buscar tarefas"
            >
              <Search className="h-5 w-5 text-gray-600" />
            </button>
          )}
          
          {/* Campo de busca - quando expandido */}
          {searchExpanded && (
            <div className="flex-1 min-w-[200px] flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar tarefas..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                  autoFocus
                />
              </div>
              <button
                onClick={() => {
                  setSearchExpanded(false)
                  setSearchTerm('')
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                title="Fechar busca"
              >
                <XCircle className="h-5 w-5 text-gray-600" />
              </button>
            </div>
          )}
          
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="active">Ativas (sem concluídas)</option>
            <option value="all">Todos os Status</option>
            <option value="pending">Pendente</option>
            <option value="in_progress">Em Andamento</option>
            <option value="completed">Concluída</option>
            <option value="cancelled">Cancelada</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">Todas</option>
            <option value="task">Tarefas</option>
            <option value="agenda">Agenda</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500"
          >
            <option value="all">Todas as Prioridades</option>
            <option value="low">Baixa</option>
            <option value="medium">Média</option>
            <option value="high">Alta</option>
            <option value="urgent">Urgente</option>
          </select>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={myTasks}
              onChange={(e) => setMyTasks(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span className="text-sm">Minhas Tarefas</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={overdue}
              onChange={(e) => setOverdue(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span className="text-sm">Atrasadas</span>
          </label>
        </div>
      </Card>

      {/* Lista de Tarefas */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      ) : filteredTasks.length === 0 ? (
        <Card className="p-12 text-center">
          <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">Nenhuma tarefa encontrada</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {filteredTasks.map((task) => (
            <Card key={task.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-lg">{task.title}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(task.status)}`}>
                      {getStatusLabel(task.status)}
                    </span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getPriorityColor(task.priority)}`}>
                      {getPriorityLabel(task.priority)}
                    </span>
                    {task.task_type === 'agenda' && (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                        Agenda
                      </span>
                    )}
                    {isOverdue(task.due_date) && (
                      <span className="px-2 py-1 rounded text-xs font-medium bg-red-100 text-red-800 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        Atrasada
                      </span>
                    )}
                  </div>
                  
                  {task.description && (
                    <p className="text-gray-600 text-sm mb-3">{task.description}</p>
                  )}

                  <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                    {task.due_date && (
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        <span>{formatDate(task.due_date)}</span>
                      </div>
                    )}
                    {task.assigned_to_data && (
                      <div className="flex items-center gap-1">
                        <User className="h-4 w-4" />
                        <span>{task.assigned_to_data.first_name || task.assigned_to_data.email}</span>
                      </div>
                    )}
                    {task.department_data && (
                      <div className="flex items-center gap-1">
                        <span>🏢 {task.department_data.name}</span>
                      </div>
                    )}
                    {task.related_contacts && task.related_contacts.length > 0 && (
                      <div className="flex items-center gap-1">
                        <span>👤 {task.related_contacts.length} contato(s)</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="relative">
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingTask(task)
                      setShowTaskModal(true)
                    }}
                    title="Editar tarefa"
                  >
                    <MoreVertical className="h-5 w-5" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
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
          task={editingTask ? {
            ...editingTask,
            department: editingTask.department || '',
            related_contacts: editingTask.related_contacts || []
          } : undefined}
          departments={departments}
          users={users}
        />
      )}
    </div>
  )
}

