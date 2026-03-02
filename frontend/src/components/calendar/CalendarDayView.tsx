/**
 * Visualização de calendário diário
 */
import { Card } from '../ui/Card'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '../ui/Button'
import { Clock } from 'lucide-react'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  due_date?: string
  task_type: 'task' | 'agenda'
  assigned_to_data?: {
    id: string
    email: string
    first_name?: string
    last_name?: string
  }
  department_data?: {
    id: string
    name: string
  }
}

interface CalendarDayViewProps {
  tasks: Task[]
  currentDate: Date
  onDateChange: (date: Date) => void
  onTaskClick: (task: Task) => void
  onDateClick?: (date: Date) => void
}

export function CalendarDayView({ tasks, currentDate, onDateChange, onTaskClick, onDateClick }: CalendarDayViewProps) {
  // Obter tarefas do dia
  const dateStr = currentDate.toISOString().split('T')[0]
  const dayTasks = tasks
    .filter(task => {
      if (!task.due_date) return false
      const taskDate = new Date(task.due_date).toISOString().split('T')[0]
      return taskDate === dateStr
    })
    .sort((a, b) => {
      // Pendentes/não concluídas primeiro
      if (a.status === 'completed' && b.status !== 'completed') return 1
      if (a.status !== 'completed' && b.status === 'completed') return -1
      // Ordenar por hora
      if (a.due_date && b.due_date) {
        return new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
      }
      return 0
    })

  // Função para verificar se é hoje
  const isToday = (date: Date): boolean => {
    const today = new Date()
    return date.toDateString() === today.toDateString()
  }

  // Função para verificar se a data é no passado
  const isPast = (date: Date): boolean => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const dateToCheck = new Date(date)
    dateToCheck.setHours(0, 0, 0, 0)
    return dateToCheck < today
  }

  const handleDateClick = () => {
    if (!onDateClick) return

    // Não permitir criar tarefa em datas passadas
    if (isPast(currentDate)) {
      return
    }

    onDateClick(currentDate)
  }

  // Navegação
  const goToPreviousDay = () => {
    const newDate = new Date(currentDate)
    newDate.setDate(newDate.getDate() - 1)
    onDateChange(newDate)
  }

  const goToNextDay = () => {
    const newDate = new Date(currentDate)
    newDate.setDate(newDate.getDate() + 1)
    onDateChange(newDate)
  }

  const goToToday = () => {
    onDateChange(new Date())
  }

  const weekDayNames = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']
  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ]

  const formatDate = (date: Date) => {
    return `${weekDayNames[date.getDay()]}, ${date.getDate()} de ${monthNames[date.getMonth()]} de ${date.getFullYear()}`
  }

  // Agrupar tarefas por hora
  const tasksByHour: Record<number, Task[]> = {}
  dayTasks.forEach(task => {
    if (task.due_date) {
      const hour = new Date(task.due_date).getHours()
      if (!tasksByHour[hour]) {
        tasksByHour[hour] = []
      }
      tasksByHour[hour].push(task)
    } else {
      // Tarefas sem hora específica vão para o início
      if (!tasksByHour[0]) {
        tasksByHour[0] = []
      }
      tasksByHour[0].push(task)
    }
  })

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={goToPreviousDay}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h2 className={`text-xl font-bold ${isToday(currentDate) ? 'text-blue-600' : ''}`}>
            {formatDate(currentDate)}
          </h2>
          <Button variant="outline" size="icon" onClick={goToNextDay}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button variant="outline" onClick={goToToday}>
          Hoje
        </Button>
      </div>

      {/* Lista de Tarefas por Hora */}
      <div className="space-y-4">
        {Object.keys(tasksByHour).length === 0 ? (
          <div 
            onClick={handleDateClick}
            className={`text-center py-12 text-gray-500 dark:text-gray-400 ${
              onDateClick && !isPast(currentDate) 
                ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors' 
                : ''
            }`}
            title={onDateClick && !isPast(currentDate) ? 'Clique para criar uma tarefa' : ''}
          >
            <Clock className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
            <p>Nenhuma tarefa agendada para este dia</p>
            {onDateClick && !isPast(currentDate) && (
              <p className="text-sm text-blue-600 mt-2">Clique aqui para criar uma tarefa</p>
            )}
          </div>
        ) : (
          Object.keys(tasksByHour)
            .sort((a, b) => Number(a) - Number(b))
            .map(hour => {
              const hourTasks = tasksByHour[Number(hour)]
              const hourLabel = hour === 0 ? 'Sem hora específica' : `${String(hour).padStart(2, '0')}:00`

              return (
                <div key={hour} className="border-l-4 border-blue-500 pl-4">
                  <div className="font-semibold text-gray-700 dark:text-gray-300 mb-2">{hourLabel}</div>
                  <div className="space-y-2">
                    {hourTasks.map(task => {
                      const taskDate = task.due_date ? new Date(task.due_date) : null
                      const timeStr = taskDate ? taskDate.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : null

                      return (
                        <div
                          key={task.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            onTaskClick(task)
                          }}
                          className={`task-item p-3 rounded-lg cursor-pointer transition-shadow hover:shadow-md ${
                            task.status === 'completed'
                              ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 line-through'
                              : task.priority === 'urgent'
                              ? 'bg-red-50 border border-red-200'
                              : task.priority === 'high'
                              ? 'bg-orange-50 border border-orange-200'
                              : task.task_type === 'agenda'
                              ? 'bg-purple-50 border border-purple-200'
                              : 'bg-blue-50 border border-blue-200'
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                {timeStr && (
                                  <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {timeStr}
                                  </span>
                                )}
                                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                  task.status === 'completed'
                                    ? 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                                    : task.priority === 'urgent'
                                    ? 'bg-red-200 text-red-800'
                                    : task.priority === 'high'
                                    ? 'bg-orange-200 text-orange-800'
                                    : 'bg-blue-200 text-blue-800'
                                }`}>
                                  {task.task_type === 'agenda' ? 'Agenda' : task.priority === 'urgent' ? 'Urgente' : task.priority === 'high' ? 'Alta' : 'Normal'}
                                </span>
                              </div>
                              <h3 className="font-semibold text-gray-900 dark:text-gray-100">{task.title}</h3>
                              {task.description && (
                                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">{task.description}</p>
                              )}
                              <div className="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400">
                                {task.assigned_to_data && (
                                  <span>👤 {task.assigned_to_data.first_name || task.assigned_to_data.email}</span>
                                )}
                                {task.department_data && (
                                  <span>🏢 {task.department_data.name}</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })
        )}
      </div>
    </Card>
  )
}

