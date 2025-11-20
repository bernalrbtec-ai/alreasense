import { useState, useMemo } from 'react'
import { AlertCircle, Calendar, Clock, List, CheckCircle } from 'lucide-react'
import { format, isToday, isPast, isFuture, startOfDay, endOfDay } from 'date-fns'
import { ptBR } from 'date-fns/locale'

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

interface TaskEventsBoxProps {
  tasks: Task[]
  onTaskClick: (task: Task) => void
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-blue-100 text-blue-700 border-blue-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
}

export default function TaskEventsBox({ tasks, onTaskClick }: TaskEventsBoxProps) {
  const [activeTab, setActiveTab] = useState<'events' | 'pending'>('events')

  const now = new Date()
  const todayStart = startOfDay(now)
  const todayEnd = endOfDay(now)

  // Categorizar tarefas
  const categorizedTasks = useMemo(() => {
    const overdue: Task[] = []
    const today: Task[] = []
    const upcoming: Task[] = []
    const pending: Task[] = []

    tasks.forEach(task => {
      // Pendências: tarefas sem data agendada, ordenadas por criação (mais antiga primeiro)
      if (!task.due_date && task.status !== 'completed' && task.status !== 'cancelled') {
        pending.push(task)
        return
      }

      if (!task.due_date) return

      const taskDate = new Date(task.due_date)
      
      // Atrasadas: com data e status não concluído
      if (isPast(taskDate) && !isToday(taskDate) && task.status !== 'completed' && task.status !== 'cancelled') {
        overdue.push(task)
      }
      // Do dia: hoje
      else if (isToday(taskDate) && task.status !== 'completed' && task.status !== 'cancelled') {
        today.push(task)
      }
      // Próximos: futuras
      else if (isFuture(taskDate) && task.status !== 'completed' && task.status !== 'cancelled') {
        upcoming.push(task)
      }
    })

    // Ordenar pendências por data de criação (mais antiga primeiro)
    pending.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime()
      const dateB = new Date(b.created_at).getTime()
      return dateA - dateB
    })

    // Ordenar outras por data agendada
    overdue.sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime())
    today.sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime())
    upcoming.sort((a, b) => new Date(a.due_date!).getTime() - new Date(b.due_date!).getTime())

    return { overdue, today, upcoming, pending }
  }, [tasks])

  const renderTaskItem = (task: Task) => (
    <div
      key={task.id}
      onClick={() => onTaskClick(task)}
      className={`p-2 rounded border cursor-pointer hover:bg-gray-50 transition-colors ${
        task.is_overdue ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 mb-1">
            <span className={`text-xs px-1.5 py-0.5 rounded ${PRIORITY_COLORS[task.priority]}`}>
              {task.priority_display}
            </span>
            {task.is_overdue && (
              <AlertCircle className="h-3 w-3 text-red-600 flex-shrink-0" />
            )}
          </div>
          <h4 className="font-medium text-sm text-gray-900 truncate">{task.title}</h4>
          {task.due_date && (
            <p className="text-xs text-gray-500 mt-1">
              {format(new Date(task.due_date), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
            </p>
          )}
          {!task.due_date && (
            <p className="text-xs text-gray-500 mt-1">
              Criada em {format(new Date(task.created_at), "dd/MM/yyyy", { locale: ptBR })}
            </p>
          )}
          {task.assigned_to_name && (
            <p className="text-xs text-gray-400 mt-0.5">{task.assigned_to_name}</p>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm h-full flex flex-col">
      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab('events')}
          className={`flex-1 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'events'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Calendar className="h-4 w-4 inline mr-1" />
          Eventos
        </button>
        <button
          onClick={() => setActiveTab('pending')}
          className={`flex-1 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'pending'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <List className="h-4 w-4 inline mr-1" />
          Pendências
          {categorizedTasks.pending.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
              {categorizedTasks.pending.length}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {activeTab === 'events' ? (
          <>
            {/* Atrasados */}
            {categorizedTasks.overdue.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <h3 className="text-sm font-semibold text-red-600">
                    Atrasados ({categorizedTasks.overdue.length})
                  </h3>
                </div>
                <div className="space-y-2">
                  {categorizedTasks.overdue.map(renderTaskItem)}
                </div>
              </div>
            )}

            {/* Do Dia */}
            {categorizedTasks.today.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="h-4 w-4 text-blue-600" />
                  <h3 className="text-sm font-semibold text-blue-600">
                    Do Dia ({categorizedTasks.today.length})
                  </h3>
                </div>
                <div className="space-y-2">
                  {categorizedTasks.today.map(renderTaskItem)}
                </div>
              </div>
            )}

            {/* Próximos Eventos */}
            {categorizedTasks.upcoming.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="h-4 w-4 text-green-600" />
                  <h3 className="text-sm font-semibold text-green-600">
                    Próximos ({categorizedTasks.upcoming.length})
                  </h3>
                </div>
                <div className="space-y-2">
                  {categorizedTasks.upcoming.slice(0, 10).map(renderTaskItem)}
                  {categorizedTasks.upcoming.length > 10 && (
                    <p className="text-xs text-gray-500 text-center py-2">
                      +{categorizedTasks.upcoming.length - 10} mais
                    </p>
                  )}
                </div>
              </div>
            )}

            {categorizedTasks.overdue.length === 0 &&
             categorizedTasks.today.length === 0 &&
             categorizedTasks.upcoming.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <Calendar className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                <p className="text-sm">Nenhum evento agendado</p>
              </div>
            )}
          </>
        ) : (
          <>
            {/* Pendências */}
            {categorizedTasks.pending.length > 0 ? (
              <div className="space-y-2">
                {categorizedTasks.pending.map(renderTaskItem)}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <CheckCircle className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                <p className="text-sm">Nenhuma pendência</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

