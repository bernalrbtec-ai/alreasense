/**
 * Visualização de calendário semanal
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
}

interface CalendarWeekViewProps {
  tasks: Task[]
  currentDate: Date
  onDateChange: (date: Date) => void
  onTaskClick: (task: Task) => void
}

export function CalendarWeekView({ tasks, currentDate, onDateChange, onTaskClick }: CalendarWeekViewProps) {
  // Obter início da semana (domingo)
  const startOfWeek = new Date(currentDate)
  const day = startOfWeek.getDay()
  startOfWeek.setDate(startOfWeek.getDate() - day)
  startOfWeek.setHours(0, 0, 0, 0)

  // Criar array com os 7 dias da semana
  const weekDays: Date[] = []
  for (let i = 0; i < 7; i++) {
    const date = new Date(startOfWeek)
    date.setDate(startOfWeek.getDate() + i)
    weekDays.push(date)
  }

  // Função para obter tarefas de um dia
  const getTasksForDay = (date: Date): Task[] => {
    const dateStr = date.toISOString().split('T')[0]
    return tasks.filter(task => {
      if (!task.due_date) return false
      const taskDate = new Date(task.due_date).toISOString().split('T')[0]
      return taskDate === dateStr
    })
  }

  // Função para verificar se é hoje
  const isToday = (date: Date): boolean => {
    const today = new Date()
    return date.toDateString() === today.toDateString()
  }

  // Navegação
  const goToPreviousWeek = () => {
    const newDate = new Date(startOfWeek)
    newDate.setDate(newDate.getDate() - 7)
    onDateChange(newDate)
  }

  const goToNextWeek = () => {
    const newDate = new Date(startOfWeek)
    newDate.setDate(newDate.getDate() + 7)
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
    return `${weekDayNames[date.getDay()]}, ${date.getDate()} de ${monthNames[date.getMonth()]}`
  }

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={goToPreviousWeek}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <h2 className="text-xl font-bold">
            {formatDate(weekDays[0])} - {formatDate(weekDays[6])}
          </h2>
          <Button variant="outline" size="icon" onClick={goToNextWeek}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button variant="outline" onClick={goToToday}>
          Hoje
        </Button>
      </div>

      {/* Grid da Semana */}
      <div className="grid grid-cols-7 gap-4">
        {weekDays.map((date, index) => {
          const dayTasks = getTasksForDay(date)
          const isCurrentDay = isToday(date)

          return (
            <div key={index} className="border border-gray-200 rounded-lg p-3">
              <div className={`text-center mb-3 ${isCurrentDay ? 'text-blue-600 font-bold' : 'text-gray-700'}`}>
                <div className="text-sm font-medium">{weekDayNames[date.getDay()]}</div>
                <div className={`text-2xl ${isCurrentDay ? 'text-blue-600' : 'text-gray-900'}`}>
                  {date.getDate()}
                </div>
              </div>
              
              <div className="space-y-2">
                {dayTasks
                  .sort((a, b) => {
                    // Pendentes/não concluídas primeiro
                    if (a.status === 'completed' && b.status !== 'completed') return 1
                    if (a.status !== 'completed' && b.status === 'completed') return -1
                    // Ordenar por hora se tiver
                    if (a.due_date && b.due_date) {
                      return new Date(a.due_date).getTime() - new Date(b.due_date).getTime()
                    }
                    return 0
                  })
                  .map(task => {
                    const taskDate = task.due_date ? new Date(task.due_date) : null
                    const timeStr = taskDate ? taskDate.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : null

                    return (
                      <div
                        key={task.id}
                        onClick={() => onTaskClick(task)}
                        className={`p-2 rounded cursor-pointer text-sm ${
                          task.status === 'completed'
                            ? 'bg-gray-200 text-gray-600 line-through'
                            : task.priority === 'urgent'
                            ? 'bg-red-100 text-red-800 border-l-4 border-red-500'
                            : task.priority === 'high'
                            ? 'bg-orange-100 text-orange-800 border-l-4 border-orange-500'
                            : task.task_type === 'agenda'
                            ? 'bg-purple-100 text-purple-800 border-l-4 border-purple-500'
                            : 'bg-blue-100 text-blue-800 border-l-4 border-blue-500'
                        }`}
                      >
                        {timeStr && (
                          <div className="flex items-center gap-1 text-xs mb-1">
                            <Clock className="h-3 w-3" />
                            <span>{timeStr}</span>
                          </div>
                        )}
                        <div className="font-medium truncate" title={task.title}>
                          {task.title}
                        </div>
                      </div>
                    )
                  })}
                {dayTasks.length === 0 && (
                  <div className="text-xs text-gray-400 text-center py-4">
                    Sem tarefas
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

