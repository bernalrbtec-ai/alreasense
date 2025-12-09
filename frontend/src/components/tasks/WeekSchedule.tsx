/**
 * Componente para exibir compromissos da semana
 */
import { useMemo } from 'react'
import { format, startOfWeek, endOfWeek, eachDayOfInterval, isToday, isPast, isFuture, isSameDay } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Calendar, Clock, AlertCircle, CheckCircle } from 'lucide-react'
import { Card } from '../ui/Card'

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
  is_overdue: boolean
}

interface WeekScheduleProps {
  tasks: Task[]
  onTaskClick?: (task: Task) => void
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-blue-100 text-blue-700 border-blue-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
}

const DAY_NAMES = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

export default function WeekSchedule({ tasks, onTaskClick }: WeekScheduleProps) {
  const now = new Date()
  const weekStart = startOfWeek(now, { locale: ptBR })
  const weekEnd = endOfWeek(now, { locale: ptBR })
  const weekDays = eachDayOfInterval({ start: weekStart, end: weekEnd })

  // Filtrar tarefas da semana (não concluídas)
  const weekTasks = useMemo(() => {
    return tasks.filter(task => {
      if (!task.due_date) return false
      if (task.status === 'completed' || task.status === 'cancelled') return false
      
      const taskDate = new Date(task.due_date)
      return taskDate >= weekStart && taskDate <= weekEnd
    })
  }, [tasks, weekStart, weekEnd])

  // Agrupar tarefas por dia
  const tasksByDay = useMemo(() => {
    const grouped: Record<number, Task[]> = {}
    
    weekDays.forEach(day => {
      const dayKey = day.getTime()
      grouped[dayKey] = weekTasks.filter(task => {
        if (!task.due_date) return false
        return isSameDay(new Date(task.due_date), day)
      })
      
      // Ordenar por horário (se tiver) ou por prioridade
      grouped[dayKey].sort((a, b) => {
        if (a.due_date && b.due_date) {
          const timeA = new Date(a.due_date).getTime()
          const timeB = new Date(b.due_date).getTime()
          return timeA - timeB
        }
        const priorityOrder = { urgent: 0, high: 1, medium: 2, low: 3 }
        return priorityOrder[a.priority] - priorityOrder[b.priority]
      })
    })
    
    return grouped
  }, [weekTasks, weekDays])

  const getDayLabel = (day: Date) => {
    const dayName = DAY_NAMES[day.getDay()]
    const dayNumber = format(day, 'd')
    const isCurrentDay = isToday(day)
    
    return { dayName, dayNumber, isCurrentDay }
  }

  const totalTasks = weekTasks.length
  const overdueTasks = weekTasks.filter(t => t.is_overdue).length
  const todayTasks = weekTasks.filter(t => {
    if (!t.due_date) return false
    return isToday(new Date(t.due_date))
  }).length

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="mb-6 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Calendar className="h-5 w-5 text-blue-600" />
            Compromissos da Semana
          </h3>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            {overdueTasks > 0 && (
              <span className="flex items-center gap-1 text-red-600">
                <AlertCircle className="h-4 w-4" />
                {overdueTasks} atrasado{overdueTasks > 1 ? 's' : ''}
              </span>
            )}
            {todayTasks > 0 && (
              <span className="flex items-center gap-1 text-blue-600">
                <Clock className="h-4 w-4" />
                {todayTasks} hoje
              </span>
            )}
            <span className="text-gray-500">
              {totalTasks} total
            </span>
          </div>
        </div>
        <p className="text-sm text-gray-500">
          {format(weekStart, "dd 'de' MMMM", { locale: ptBR })} até {format(weekEnd, "dd 'de' MMMM", { locale: ptBR })}
        </p>
      </div>

      {totalTasks === 0 ? (
        <div className="text-center py-12 text-gray-500 flex-1 flex items-center justify-center">
          <div>
            <Calendar className="h-16 w-16 mx-auto mb-4 text-gray-300" />
            <p className="text-sm font-medium">Nenhum compromisso esta semana</p>
            <p className="text-xs mt-1">Suas tarefas agendadas aparecerão aqui</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          {weekDays.map((day, idx) => {
            const { dayName, dayNumber, isCurrentDay } = getDayLabel(day)
            const dayTasks = tasksByDay[day.getTime()] || []
            const isPastDay = isPast(day) && !isToday(day)

            return (
              <div
                key={idx}
                className={`border rounded-lg p-3 min-h-[200px] ${
                  isCurrentDay
                    ? 'border-blue-500 bg-blue-50'
                    : isPastDay
                    ? 'border-gray-200 bg-gray-50 opacity-60'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <div className={`text-center mb-3 pb-2 border-b ${
                  isCurrentDay ? 'border-blue-200' : 'border-gray-200'
                }`}>
                  <div className="text-xs font-medium text-gray-500 mb-1">{dayName}</div>
                  <div className={`text-xl font-bold ${
                    isCurrentDay ? 'text-blue-600' : 'text-gray-900'
                  }`}>
                    {dayNumber}
                  </div>
                </div>

                <div className="space-y-2">
                  {dayTasks.length === 0 ? (
                    <div className="text-center py-4">
                      <p className="text-xs text-gray-400">Sem tarefas</p>
                    </div>
                  ) : (
                    dayTasks.map(task => {
                      const taskDate = task.due_date ? new Date(task.due_date) : null
                      const hasTime = taskDate && taskDate.getHours() !== 0 && taskDate.getMinutes() !== 0

                      return (
                        <div
                          key={task.id}
                          onClick={() => onTaskClick?.(task)}
                          className={`p-2 rounded border cursor-pointer transition-all hover:shadow-sm ${
                            task.is_overdue
                              ? 'border-red-300 bg-red-50'
                              : task.status === 'completed'
                              ? 'border-gray-200 bg-gray-100 opacity-60'
                              : 'border-gray-200 bg-white hover:border-blue-300'
                          }`}
                        >
                          <div className="flex items-start gap-1.5 mb-1">
                            <span className={`text-xs px-1.5 py-0.5 rounded flex-shrink-0 ${PRIORITY_COLORS[task.priority]}`}>
                              {task.priority_display}
                            </span>
                            {task.is_overdue && (
                              <AlertCircle className="h-3 w-3 text-red-600 flex-shrink-0 mt-0.5" />
                            )}
                            {task.status === 'completed' && (
                              <CheckCircle className="h-3 w-3 text-gray-500 flex-shrink-0 mt-0.5" />
                            )}
                          </div>
                          <h4 className={`text-xs font-medium mb-1 line-clamp-2 ${
                            task.status === 'completed'
                              ? 'line-through text-gray-500'
                              : 'text-gray-900'
                          }`}>
                            {task.title}
                          </h4>
                          {hasTime && taskDate && (
                            <p className="text-xs text-gray-500 flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {format(taskDate, 'HH:mm', { locale: ptBR })}
                            </p>
                          )}
                          {task.assigned_to_name && (
                            <p className="text-xs text-gray-400 mt-1 truncate">
                              {task.assigned_to_name}
                            </p>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
          </div>
        </div>
      )}
    </Card>
  )
}

