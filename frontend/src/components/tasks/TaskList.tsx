import { useState, useEffect, useRef } from 'react'
import { Plus, CheckCircle, Clock, AlertCircle, XCircle, Calendar, List, Filter, User, Users, Edit, X, Search } from 'lucide-react'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast } from '../../lib/toastHelper'
import { Button } from '../ui/Button'
import LoadingSpinner from '../ui/LoadingSpinner'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, isToday, addMonths, subMonths } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import TaskModal from './TaskModal'
import TaskSearchModal from './TaskSearchModal'

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
  onTasksChange?: (tasks: Task[]) => void
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

export default function TaskList({ departmentId, contactId, onTasksChange }: TaskListProps) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('calendar')
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(undefined)
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)
  const [showDayMenu, setShowDayMenu] = useState(false)
  const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 })
  const menuRef = useRef<HTMLDivElement>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [filters, setFilters] = useState({
    status: '',
    department: departmentId || '',
    assigned_to: '',
    my_tasks: false,
    created_by_me: false,
    overdue: false,
    search: '',
  })
  const [showSearchModal, setShowSearchModal] = useState(false)

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
      if (filters.search) params.search = filters.search
      if (contactId) params.contact_id = contactId

      const response = await api.get('/contacts/tasks/', { params })
      const fetchedTasks = response.data.results || response.data
      setTasks(fetchedTasks)
      // Notificar componente pai sobre mudanças nas tarefas
      if (onTasksChange) {
        onTasksChange(fetchedTasks)
      }
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

  const handleCreate = (date?: Date) => {
    setEditingTask(null)
    setSelectedDate(date)
    setShowDayMenu(false)
    setShowTaskModal(true)
  }

  const handleDayClick = (day: Date, event: React.MouseEvent) => {
    // Verificar se o dia não é no passado
    const now = new Date()
    const dayStart = new Date(day)
    dayStart.setHours(0, 0, 0, 0)
    const nowStart = new Date(now)
    nowStart.setHours(0, 0, 0, 0)
    
    if (dayStart < nowStart) {
      showErrorToast('Não é possível criar tarefas em datas passadas')
      return
    }
    
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
    const scrollX = window.scrollX || window.pageXOffset
    const scrollY = window.scrollY || window.pageYOffset
    
    setSelectedDay(day)
    // Posicionar menu no centro do dia, considerando scroll
    setMenuPosition({
      x: rect.left + rect.width / 2 + scrollX,
      y: rect.top + rect.height / 2 + scrollY
    })
    setShowDayMenu(true)
  }

  const handleModalSuccess = () => {
    setShowTaskModal(false)
    setEditingTask(null)
    setSelectedDate(undefined)
    fetchTasks()
  }

  // Fechar menu ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowDayMenu(false)
      }
    }

    if (showDayMenu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [showDayMenu])

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
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setShowSearchModal(true)}
            title="Pesquisar e filtrar tarefas"
          >
            <Search className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleCreate}>
            <Plus className="h-4 w-4 mr-1" />
            Nova Tarefa
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
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

                // Verificar se o dia é no passado
                const now = new Date()
                const dayStart = new Date(day)
                dayStart.setHours(0, 0, 0, 0)
                const nowStart = new Date(now)
                nowStart.setHours(0, 0, 0, 0)
                const isPast = dayStart < nowStart

                return (
                  <div
                    key={idx}
                    className={`min-h-[100px] border border-gray-100 p-1 ${
                      isCurrentMonth ? 'bg-white' : 'bg-gray-50'
                    } ${isCurrentDay ? 'bg-blue-50' : ''} ${
                      isPast && isCurrentMonth ? 'opacity-50 cursor-not-allowed' : ''
                    } ${
                      isCurrentMonth && !isPast ? 'hover:bg-gray-50 cursor-pointer' : ''
                    } transition-colors relative group`}
                    onClick={(e) => {
                      if (isCurrentMonth && !isPast) {
                        handleDayClick(day, e)
                      } else if (isPast && isCurrentMonth) {
                        showErrorToast('Não é possível criar tarefas em datas passadas')
                      }
                    }}
                    title={
                      isPast && isCurrentMonth 
                        ? 'Não é possível criar tarefas em datas passadas'
                        : isCurrentMonth 
                        ? 'Clique para ver opções do dia' 
                        : ''
                    }
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
                          onClick={(e) => {
                            e.stopPropagation()
                            handleEdit(task)
                          }}
                        >
                          {task.title}
                        </div>
                      ))}
                      {dayTasks.length > 3 && (
                        <div 
                          className="text-xs text-gray-500 px-1 cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation()
                            // Mostrar todas as tarefas do dia
                            setViewMode('list')
                            setFilters({ ...filters, has_due_date: true })
                            setCurrentMonth(day)
                          }}
                        >
                          +{dayTasks.length - 3} mais
                        </div>
                      )}
                      {isCurrentMonth && dayTasks.length === 0 && (
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                          <Plus className="h-5 w-5 text-gray-400" />
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

      {/* Menu de Dia */}
      {showDayMenu && selectedDay && (
        <div
          ref={menuRef}
          className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-xl p-2 min-w-[200px] max-w-[300px]"
          style={{
            left: `${menuPosition.x}px`,
            top: `${menuPosition.y}px`,
            transform: 'translate(-50%, -50%)'
          }}
        >
          <div className="flex items-center justify-between mb-2 pb-2 border-b">
            <span className="text-sm font-semibold text-gray-900">
              {format(selectedDay, "dd/MM/yyyy", { locale: ptBR })}
            </span>
            <button
              onClick={() => setShowDayMenu(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          
          <div className="space-y-1">
            <button
              onClick={() => {
                // Validar se o dia não é no passado
                const now = new Date()
                const dayStart = new Date(selectedDay)
                dayStart.setHours(0, 0, 0, 0)
                const nowStart = new Date(now)
                nowStart.setHours(0, 0, 0, 0)
                
                if (dayStart < nowStart) {
                  showErrorToast('Não é possível criar tarefas em datas passadas')
                  return
                }
                
                handleCreate(selectedDay)
              }}
              className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-blue-50 rounded flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              Nova Tarefa
            </button>
            
            {getTasksForDate(selectedDay).length > 0 && (
              <>
                <div className="border-t my-1"></div>
                <div className="text-xs text-gray-500 px-2 py-1">
                  Tarefas do dia ({getTasksForDate(selectedDay).length})
                </div>
                {getTasksForDate(selectedDay).map(task => (
                  <button
                    key={task.id}
                    onClick={() => {
                      handleEdit(task)
                      setShowDayMenu(false)
                    }}
                    className={`w-full text-left px-3 py-2 text-sm rounded flex items-center justify-between group ${
                      task.can_edit 
                        ? 'text-gray-700 hover:bg-gray-50' 
                        : 'text-gray-400 cursor-not-allowed'
                    }`}
                    disabled={!task.can_edit}
                    title={!task.can_edit ? 'Você não tem permissão para editar esta tarefa' : ''}
                  >
                    <div className="flex-1 truncate">
                      <div className="font-medium truncate">{task.title}</div>
                      <div className="text-xs text-gray-500">
                        {task.status_display} • {task.priority_display}
                      </div>
                    </div>
                    {task.can_edit && (
                      <Edit className="h-3 w-3 text-gray-400 group-hover:text-blue-600 ml-2 flex-shrink-0" />
                    )}
                  </button>
                ))}
              </>
            )}
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
            setSelectedDate(undefined)
          }}
          onSuccess={handleModalSuccess}
          task={editingTask}
          initialDepartmentId={departmentId}
          initialContactId={contactId}
          initialDate={selectedDate}
          departments={departments}
          users={users}
        />
      )}
    </div>
  )
}

