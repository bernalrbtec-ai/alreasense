/**
 * Visualização de calendário mensal
 */
import React from 'react'
import { Card } from '../ui/Card'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '../ui/Button'

interface Task {
  id: string
  title: string
  description?: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  due_date?: string
  task_type: 'task' | 'agenda'
}

interface CalendarMonthViewProps {
  tasks: Task[]
  currentDate: Date
  onDateChange: (date: Date) => void
  onTaskClick: (task: Task) => void
  onDateClick?: (date: Date) => void
}

export function CalendarMonthView({ tasks, currentDate, onDateChange, onTaskClick, onDateClick }: CalendarMonthViewProps) {
  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  // Primeiro dia do mês
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  
  // Dia da semana do primeiro dia (0 = domingo, 6 = sábado)
  const startDayOfWeek = firstDay.getDay()
  
  // Número de dias no mês
  const daysInMonth = lastDay.getDate()
  
  // Dias da semana
  const weekDays = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
  
  // Criar array de dias do mês (incluindo dias vazios do início)
  const days: (Date | null)[] = []
  
  // Adicionar dias vazios do início
  for (let i = 0; i < startDayOfWeek; i++) {
    days.push(null)
  }
  
  // Adicionar dias do mês
  for (let day = 1; day <= daysInMonth; day++) {
    days.push(new Date(year, month, day))
  }

  // Função para obter tarefas de um dia
  const getTasksForDay = (date: Date | null): Task[] => {
    if (!date) return []
    const dateStr = date.toISOString().split('T')[0]
    return tasks.filter(task => {
      if (!task.due_date) return false
      const taskDate = new Date(task.due_date).toISOString().split('T')[0]
      return taskDate === dateStr
    })
  }

  // Função para verificar se é hoje
  const isToday = (date: Date | null): boolean => {
    if (!date) return false
    const today = new Date()
    return date.toDateString() === today.toDateString()
  }

  // Função para verificar se a data é no passado
  const isPast = (date: Date | null): boolean => {
    if (!date) return false
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const dateToCheck = new Date(date)
    dateToCheck.setHours(0, 0, 0, 0)
    return dateToCheck < today
  }

  const handleDateClick = (date: Date | null, event: React.MouseEvent) => {
    if (!date || !onDateClick) return
    
    // Prevenir que o clique na tarefa propague para o dia
    if ((event.target as HTMLElement).closest('.task-item')) {
      return
    }

    // Não permitir criar tarefa em datas passadas
    if (isPast(date)) {
      return
    }

    onDateClick(date)
  }

  // Navegação
  const goToPreviousMonth = () => {
    const newDate = new Date(year, month - 1, 1)
    onDateChange(newDate)
  }

  const goToNextMonth = () => {
    const newDate = new Date(year, month + 1, 1)
    onDateChange(newDate)
  }

  const goToToday = () => {
    onDateChange(new Date())
  }

  const monthNames = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
  ]

  return (
    <Card className="p-6">
      {/* Header do Calendário */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={goToPreviousMonth}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-xl font-bold">
            {monthNames[month]} {year}
          </h2>
          <Button variant="outline" size="icon" onClick={goToNextMonth}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button variant="outline" onClick={goToToday}>
          Hoje
        </Button>
      </div>

      {/* Grid do Calendário */}
      <div className="grid grid-cols-7 gap-1">
        {/* Cabeçalho dos dias da semana */}
        {weekDays.map(day => (
          <div key={day} className="p-2 text-center text-sm font-semibold text-gray-600">
            {day}
          </div>
        ))}

        {/* Dias do mês */}
        {days.map((date, index) => {
          const dayTasks = getTasksForDay(date)
          const isCurrentDay = isToday(date)
          const isCurrentMonth = date && date.getMonth() === month

          const isPastDay = isPast(date)
          const canClick = date && isCurrentMonth && !isPastDay && onDateClick

          return (
            <div
              key={index}
              onClick={(e) => canClick && handleDateClick(date, e)}
              className={`min-h-[100px] border border-gray-200 p-2 ${
                !isCurrentMonth ? 'bg-gray-50' : ''
              } ${isCurrentDay ? 'bg-blue-50 border-blue-300' : ''} ${
                canClick ? 'cursor-pointer hover:bg-gray-50 transition-colors' : ''
              } ${isPastDay && isCurrentMonth ? 'opacity-60' : ''}`}
              title={isPastDay && isCurrentMonth ? 'Não é possível criar tarefas em datas passadas' : canClick ? 'Clique para criar uma tarefa' : ''}
            >
              {date && (
                <>
                  <div className={`text-sm font-medium mb-1 ${
                    isCurrentDay ? 'text-blue-600' : 'text-gray-900'
                  }`}>
                    {date.getDate()}
                  </div>
                  <div className="space-y-1">
                    {dayTasks
                      .sort((a, b) => {
                        // Pendentes/não concluídas primeiro
                        if (a.status === 'completed' && b.status !== 'completed') return 1
                        if (a.status !== 'completed' && b.status === 'completed') return -1
                        return 0
                      })
                      .slice(0, 3)
                      .map(task => (
                        <div
                          key={task.id}
                          onClick={(e) => {
                            e.stopPropagation()
                            onTaskClick(task)
                          }}
                          className={`task-item text-xs p-1 rounded cursor-pointer truncate ${
                            task.status === 'completed'
                              ? 'bg-gray-200 text-gray-600 line-through'
                              : task.priority === 'urgent'
                              ? 'bg-red-100 text-red-800'
                              : task.priority === 'high'
                              ? 'bg-orange-100 text-orange-800'
                              : task.task_type === 'agenda'
                              ? 'bg-purple-100 text-purple-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                          title={task.title}
                        >
                          {task.title}
                        </div>
                      ))}
                    {dayTasks.length > 3 && (
                      <div className="text-xs text-gray-500">
                        +{dayTasks.length - 3} mais
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}

