/**
 * Lista simplificada de pendências - apenas título e data de criação
 */
import { useMemo } from 'react'
import { List, CheckCircle } from 'lucide-react'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Card } from '../ui/Card'

interface Task {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  due_date?: string
  created_at: string
}

interface PendingTasksListProps {
  tasks: Task[]
  onTaskClick: (task: Task) => void
}

export default function PendingTasksList({ tasks, onTaskClick }: PendingTasksListProps) {
  // Filtrar apenas pendências (sem data agendada e não concluídas)
  const pendingTasks = useMemo(() => {
    return tasks
      .filter(task => {
        // Apenas tarefas sem data agendada e não concluídas
        return !task.due_date && 
               task.status !== 'completed' && 
               task.status !== 'cancelled'
      })
      .sort((a, b) => {
        // Ordenar da mais antiga para a mais nova
        const dateA = new Date(a.created_at).getTime()
        const dateB = new Date(b.created_at).getTime()
        return dateA - dateB
      })
  }, [tasks])

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <List className="h-5 w-5 text-blue-600" />
          Pendências
          {pendingTasks.length > 0 && (
            <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm font-medium">
              {pendingTasks.length}
            </span>
          )}
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {pendingTasks.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <CheckCircle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p className="text-sm font-medium">Nenhuma pendência</p>
            <p className="text-xs mt-1">Todas as tarefas estão organizadas</p>
          </div>
        ) : (
          pendingTasks.map(task => (
            <div
              key={task.id}
              onClick={() => onTaskClick(task)}
              className="p-3 rounded-lg border border-gray-200 bg-white cursor-pointer hover:bg-gray-50 hover:border-blue-300 transition-all"
            >
              <h4 className="font-medium text-sm text-gray-900 mb-1 line-clamp-2">
                {task.title}
              </h4>
              <p className="text-xs text-gray-500">
                Criada em {format(new Date(task.created_at), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
              </p>
            </div>
          ))
        )}
      </div>
    </Card>
  )
}

