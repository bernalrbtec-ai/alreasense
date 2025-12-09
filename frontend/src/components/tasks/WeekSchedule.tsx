/**
 * Componente para exibir compromissos da semana
 */
import React, { useMemo } from 'react'
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
  onDateClick?: (date: Date) => void
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700 border-gray-200',
  medium: 'bg-blue-100 text-blue-700 border-blue-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  urgent: 'bg-red-100 text-red-700 border-red-200',
}

const DAY_NAMES = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

export default function WeekSchedule({ tasks, onTaskClick, onDateClick }: WeekScheduleProps) {
  const now = new Date()
  // Começar do dia atual e ir até +6 dias (7 dias no total)
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)
  const weekEnd = new Date(today)
  weekEnd.setDate(today.getDate() + 6)
  const weekDays = eachDayOfInterval({ start: today, end: weekEnd })

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
            <p className="text-sm font-medium">Nenhum compromisso nos próximos 7 dias</p>
            <p className="text-xs mt-1">Suas tarefas agendadas aparecerão aqui</p>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-3">
          {weekDays.map((day, idx) => {
            const { dayName, dayNumber, isCurrentDay } = getDayLabel(day)
            const dayTasks = tasksByDay[day.getTime()] || []
            const isPastDay = isPast(day) && !isToday(day)
            const canClick = !isPastDay && onDateClick

            return (
              <div
                key={idx}
                className={`border rounded-lg p-4 ${
                  isCurrentDay
                    ? 'border-blue-500 bg-blue-50'
                    : isPastDay
                    ? 'border-gray-200 bg-gray-50 opacity-60'
                    : 'border-gray-200 bg-white'
                }`}
              >
                {/* Header do Dia */}
                <div 
                  onClick={(e) => {
                    if (canClick && !(e.target as HTMLElement).closest('.task-item')) {
                      onDateClick(day)
                    }
                  }}
                  className={`flex items-center justify-between mb-3 pb-2 border-b ${
                    isCurrentDay ? 'border-blue-200' : 'border-gray-200'
                  } ${canClick ? 'cursor-pointer' : ''}`}
                  title={isPastDay ? 'Não é possível criar tarefas em datas passadas' : canClick ? 'Clique para criar uma tarefa' : ''}
                >
                  <div className="flex items-center gap-3">
                    <div className={`text-center ${isCurrentDay ? 'text-blue-600' : 'text-gray-700'}`}>
                      <div className="text-xs font-medium text-gray-500">{dayName}</div>
                      <div className={`text-2xl font-bold ${
                        isCurrentDay ? 'text-blue-600' : 'text-gray-900'
                      }`}>
                        {dayNumber}
                      </div>
                    </div>
                    <div className="text-sm text-gray-600">
                      {format(day, "dd 'de' MMMM", { locale: ptBR })}
                    </div>
                  </div>
                  {dayTasks.length > 0 && (
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                      {dayTasks.length} {dayTasks.length === 1 ? 'compromisso' : 'compromissos'}
                    </span>
                  )}
                </div>

                {/* Lista de Tarefas */}
                <div className="space-y-2">
                  {dayTasks.length === 0 ? (
                    <div 
                      onClick={() => canClick && onDateClick(day)}
                      className={`text-center py-4 text-xs text-gray-400 ${
                        canClick ? 'cursor-pointer hover:text-gray-600' : ''
                      }`}
                    >
                      {canClick ? 'Clique para criar uma tarefa' : 'Sem tarefas'}
                    </div>
                  ) : (
                    dayTasks.map(task => {
                      const taskDate = task.due_date ? new Date(task.due_date) : null
                      const hasTime = taskDate && taskDate.getHours() !== 0 && taskDate.getMinutes() !== 0

                      return (
                        <div
                          key={task.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            onTaskClick?.(task)
                          }}
                          className={`task-item p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                            task.is_overdue
                              ? 'border-red-300 bg-red-50'
                              : task.status === 'completed'
                              ? 'border-gray-200 bg-gray-100 opacity-60'
                              : 'border-gray-200 bg-white hover:border-blue-300'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`text-xs px-2 py-0.5 rounded flex-shrink-0 ${PRIORITY_COLORS[task.priority]}`}>
                                  {task.priority_display}
                                </span>
                                {task.is_overdue && (
                                  <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                                )}
                                {task.status === 'completed' && (
                                  <CheckCircle className="h-4 w-4 text-gray-500 flex-shrink-0" />
                                )}
                              </div>
                              <h4 className={`text-sm font-medium mb-1 ${
                                task.status === 'completed'
                                  ? 'line-through text-gray-500'
                                  : 'text-gray-900'
                              }`}>
                                {task.title}
                              </h4>
                              <div className="flex items-center gap-3 text-xs text-gray-500">
                                {hasTime && taskDate && (
                                  <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    {format(taskDate, 'HH:mm', { locale: ptBR })}
                                  </span>
                                )}
                                {task.assigned_to_name && (
                                  <span className="truncate">
                                    {task.assigned_to_name}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

