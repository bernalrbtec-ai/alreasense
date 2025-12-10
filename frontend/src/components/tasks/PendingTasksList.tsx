/**
 * Lista simplificada de pendências - apenas título e data de criação
 */
import { useState, useMemo } from 'react'
import { List, CheckCircle, AlertTriangle } from 'lucide-react'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Card } from '../ui/Card'

interface Task {
  id: string
  title: string
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled'
  status_display?: string
  priority: 'low' | 'medium' | 'high' | 'urgent'
  due_date?: string
  created_at: string
  is_overdue?: boolean
  department_name?: string
  assigned_to_name?: string
}

interface PendingTasksListProps {
  tasks: Task[]
  onTaskClick: (task: Task) => void
}

export default function PendingTasksList({ tasks, onTaskClick }: PendingTasksListProps) {
  const [activeTab, setActiveTab] = useState<'urgent' | 'pending'>('urgent')

  // Filtrar tarefas urgentes (atrasadas + prioridade urgente)
  const urgentTasks = useMemo(() => {
    return tasks
      .filter(task => {
        // Tarefas não concluídas que são:
        // 1. Atrasadas (is_overdue = true) OU
        // 2. Prioridade urgente
        if (task.status === 'completed' || task.status === 'cancelled') return false
        
        return task.is_overdue === true || task.priority === 'urgent'
      })
      .sort((a, b) => {
        // Ordenar: atrasadas primeiro, depois por prioridade, depois por data de criação
        if (a.is_overdue && !b.is_overdue) return -1
        if (!a.is_overdue && b.is_overdue) return 1
        
        const priorityOrder = { urgent: 0, high: 1, medium: 2, low: 3 }
        const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
        if (priorityDiff !== 0) return priorityDiff
        
        // Se mesma prioridade, ordenar por data de criação (mais antiga primeiro)
        const dateA = new Date(a.created_at).getTime()
        const dateB = new Date(b.created_at).getTime()
        return dateA - dateB
      })
  }, [tasks])

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

  // Determinar qual aba mostrar por padrão
  const defaultTab = urgentTasks.length > 0 ? 'urgent' : 'pending'
  
  // Se a aba urgente não tiver itens e estiver selecionada, mudar para pendências
  if (activeTab === 'urgent' && urgentTasks.length === 0) {
    // Não podemos usar setState diretamente aqui, então vamos usar um efeito
  }

  // Se não houver tarefas urgentes, mostrar pendências diretamente
  const displayTab = urgentTasks.length > 0 ? activeTab : 'pending'
  const currentTasks = displayTab === 'urgent' ? urgentTasks : pendingTasks

  return (
    <Card className="p-6 h-full flex flex-col">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-3">
          <List className="h-5 w-5 text-blue-600" />
          Pendências
        </h3>

        {/* Tabs */}
        {urgentTasks.length > 0 && (
          <div className="flex border-b border-gray-200">
            <button
              onClick={() => setActiveTab('urgent')}
              className={`flex-1 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === 'urgent'
                  ? 'border-red-600 text-red-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <AlertTriangle className="h-4 w-4 inline mr-1" />
              Urgente
              {urgentTasks.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs">
                  {urgentTasks.length}
                </span>
              )}
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
              {pendingTasks.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                  {pendingTasks.length}
                </span>
              )}
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto space-y-2">
        {currentTasks.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <CheckCircle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p className="text-sm font-medium">
              {displayTab === 'urgent' ? 'Nenhuma tarefa urgente' : 'Nenhuma pendência'}
            </p>
            <p className="text-xs mt-1">
              {displayTab === 'urgent' 
                ? 'Todas as tarefas estão em dia' 
                : 'Todas as tarefas estão organizadas'}
            </p>
          </div>
        ) : (
          currentTasks.map(task => {
            const isUrgent = task.is_overdue || task.priority === 'urgent'
            
            return (
              <div
                key={task.id}
                onClick={() => onTaskClick(task)}
                className={`p-3 rounded-lg border cursor-pointer hover:bg-gray-50 transition-all ${
                  isUrgent && displayTab === 'urgent'
                    ? 'border-red-300 bg-red-50 hover:border-red-400'
                    : 'border-gray-200 bg-white hover:border-blue-300'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h4 className="font-medium text-sm text-gray-900 line-clamp-2 flex-1">
                    {task.title}
                  </h4>
                  {isUrgent && displayTab === 'urgent' && (
                    <AlertTriangle className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
                  )}
                </div>
                
                {/* Informações adicionais */}
                <div className="space-y-1.5">
                  <div className="flex items-center gap-3 text-xs text-gray-600 flex-wrap">
                    {/* Departamento */}
                    {task.department_name && (
                      <span className="font-medium text-gray-700">
                        {task.department_name}
                      </span>
                    )}
                    
                    {/* Status */}
                    {task.status_display && (
                      <span className={`px-2 py-0.5 rounded ${
                        task.status === 'pending' 
                          ? 'bg-yellow-100 text-yellow-700'
                          : task.status === 'in_progress'
                          ? 'bg-blue-100 text-blue-700'
                          : task.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {task.status_display}
                      </span>
                    )}
                    
                    {/* Atribuído a */}
                    {task.assigned_to_name && (
                      <span className="text-gray-500">
                        Atribuída a: <span className="font-medium text-gray-700">{task.assigned_to_name}</span>
                      </span>
                    )}
                  </div>
                  
                  {/* Data e prioridade */}
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {task.is_overdue && (
                      <span className="text-red-600 font-medium">Atrasada</span>
                    )}
                    {task.priority === 'urgent' && !task.is_overdue && (
                      <span className="text-orange-600 font-medium">Urgente</span>
                    )}
                    <span>
                      Criada em {format(new Date(task.created_at), "dd/MM/yyyy", { locale: ptBR })}
                    </span>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </Card>
  )
}

