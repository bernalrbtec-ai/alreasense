import { useState, useEffect, useMemo } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../modules/chat/store/chatStore'
import PendingTasksList from '../components/tasks/PendingTasksList'
import WeekSchedule from '../components/tasks/WeekSchedule'
import TaskModal from '../components/tasks/TaskModal'
import { api } from '../lib/api'
import { Card } from '../components/ui/Card'
import { Clock, AlertCircle, MessageSquare } from 'lucide-react'
import { useTenantSocket } from '../modules/chat/hooks/useTenantSocket'

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
  department?: string
  assigned_to?: string
  related_contacts?: any[]
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

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const { user } = useAuthStore()
  // ✅ CORREÇÃO: Usar hook do store para atualização em tempo real
  const conversations = useChatStore((state) => state.conversations)
  const [tasks, setTasks] = useState<Task[]>([])
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const [unreadMessages, setUnreadMessages] = useState(0)
  const [openConversations, setOpenConversations] = useState(0)
  const [selectedDateForTask, setSelectedDateForTask] = useState<Date | null>(null)

  // WebSocket para atualização em tempo real
  useTenantSocket()
  
  // ✅ CORREÇÃO: Atualizar estatísticas quando conversations mudar (via WebSocket)
  // ✅ SEGURANÇA: conversations já vem filtrado por tenant do backend (linha 282 de views.py)
  // O backend SEMPRE filtra por tenant=user.tenant, garantindo isolamento multi-tenant
  useEffect(() => {
    // Contar apenas pendências em andamento (status 'pending') - EXCLUIR open e closed
    // Todas as conversas aqui são do tenant atual (garantido pelo backend)
    const pendingConvs = conversations.filter((conv: any) => 
      conv.status === 'pending'
    )
    setOpenConversations(pendingConvs.length)

    // Somar mensagens não lidas
    // Todas as mensagens não lidas são do tenant atual (garantido pelo backend)
    const totalUnread = conversations.reduce((sum: number, conv: any) => {
      return sum + (conv.unread_count || 0)
    }, 0)
    setUnreadMessages(totalUnread)
  }, [conversations])

  // Carregar departamentos e usuários para o modal (mesmos endpoints do TaskList)
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

  const handleTaskClick = async (task: Task) => {
    // Buscar tarefa completa da API para garantir que temos todos os dados necessários
    try {
      const response = await api.get(`/contacts/tasks/${task.id}/`)
      const fullTask = response.data
      setEditingTask(fullTask)
      setShowTaskModal(true)
    } catch (error: any) {
      console.error('Erro ao buscar tarefa completa:', error)
      // Se falhar, tentar usar a tarefa que temos (pode não ter todos os campos)
      setEditingTask(task)
      setShowTaskModal(true)
    }
  }

  const handleModalSuccess = async () => {
    setShowTaskModal(false)
    setEditingTask(null)
    // Recarregar tarefas
    setRefreshTrigger(prev => prev + 1)
  }

  // Carregar tarefas
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        // Buscar todas as tarefas (sem filtro de status para pegar todas)
        // O backend já filtra por tenant e departamentos do usuário
        const response = await api.get('/contacts/tasks/')
        const fetchedTasks = response.data.results || response.data || []
        setTasks(fetchedTasks)
      } catch (error: any) {
        console.error('Erro ao carregar tarefas:', error)
        // Se houver erro, definir array vazio para não quebrar a interface
        setTasks([])
      }
    }
    fetchTasks()
  }, [refreshTrigger])

  // Buscar estatísticas do chat
  // ✅ SEGURANÇA: Backend SEMPRE filtra por tenant (views.py linha 282: queryset.filter(tenant=user.tenant))
  // Isso garante que apenas conversas do tenant atual são retornadas
  const fetchChatStats = async () => {
    try {
      // Buscar todas as conversas para contar abertas e mensagens não lidas
      // O backend filtra automaticamente por tenant do usuário autenticado
      const conversationsRes = await api.get('/chat/conversations/', {
        params: {
          page_size: 1000 // Buscar todas para contar
        }
      })
      const fetchedConversations = conversationsRes.data.results || conversationsRes.data || []
      
      // ✅ CORREÇÃO: Atualizar store com conversas buscadas (para sincronizar com API)
      // ✅ SEGURANÇA: fetchedConversations já contém apenas conversas do tenant atual
      const { setConversations } = useChatStore.getState()
      setConversations(fetchedConversations)
      
      // As estatísticas serão atualizadas automaticamente pelo useEffect que escuta o store
    } catch (error) {
      console.error('Erro ao buscar estatísticas do chat:', error)
    }
  }

  // Carregar estatísticas do chat ao montar (polling inicial)
  // Depois disso, as estatísticas são atualizadas em tempo real via WebSocket (useEffect acima)
  useEffect(() => {
    fetchChatStats()
    // Manter polling como fallback (a cada 30 segundos) caso WebSocket falhe
    const interval = setInterval(fetchChatStats, 30000)
    return () => clearInterval(interval)
  }, [])

  // Calcular estatísticas de tarefas
  const stats = useMemo(() => {
    const pending = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length
    const overdue = tasks.filter(t => t.is_overdue && t.status !== 'completed').length
    const inProgress = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress').length

    return {
      pending,
      overdue,
      inProgress,
    }
  }, [tasks])

  const handleDateClick = (date: Date) => {
    setEditingTask(null)
    setSelectedDateForTask(date)
    setShowTaskModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-gray-600">
          Visão geral de tarefas e compromissos de {user?.tenant?.name}
        </p>
      </div>

      {/* Cards de Estatísticas */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Pendentes (tarefas/agenda) */}
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Pendentes</p>
              <p className="text-2xl font-bold text-orange-600">{stats.pending}</p>
            </div>
            <div className="p-3 bg-orange-100 rounded-lg">
              <Clock className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </Card>

        {/* 2. Atrasadas (tarefas/agenda) */}
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Atrasadas</p>
              <p className="text-2xl font-bold text-red-600">{stats.overdue}</p>
            </div>
            <div className="p-3 bg-red-100 rounded-lg">
              <AlertCircle className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </Card>

        {/* 3. Pendências em Andamento (tarefas/agenda) */}
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Pendências em Andamento</p>
              <p className="text-2xl font-bold text-purple-600">{stats.inProgress}</p>
            </div>
            <div className="p-3 bg-purple-100 rounded-lg">
              <Clock className="h-6 w-6 text-purple-600" />
            </div>
          </div>
        </Card>

        {/* 4. Novas Mensagens (conversas) */}
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600 mb-1">Novas Mensagens</p>
              <p className={`text-2xl font-bold ${unreadMessages > 0 ? 'text-blue-600' : 'text-gray-600'}`}>
                {unreadMessages > 0 ? unreadMessages : '0'}
              </p>
              {unreadMessages === 0 && (
                <p className="text-xs text-gray-400 mt-1">Nenhuma nova</p>
              )}
            </div>
            <div className="p-3 bg-blue-100 rounded-lg">
              <MessageSquare className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </Card>
      </div>

      {/* Layout: Compromissos da Semana + Pendências lado a lado */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Compromissos da Semana */}
        <div className="h-[600px]">
          <WeekSchedule 
            tasks={tasks} 
            onTaskClick={handleTaskClick}
            onDateClick={handleDateClick}
          />
        </div>

        {/* Pendências */}
        <div className="h-[600px]">
          <PendingTasksList tasks={tasks} onTaskClick={handleTaskClick} />
        </div>
      </div>

      {/* Modal de Tarefa */}
      {showTaskModal && (
        <TaskModal
          isOpen={showTaskModal}
          onClose={() => {
            setShowTaskModal(false)
            setEditingTask(null)
            setSelectedDateForTask(null)
          }}
          onSuccess={handleModalSuccess}
          task={editingTask ? {
            ...editingTask,
            department: editingTask.department || '',
            related_contacts: editingTask.related_contacts || []
          } : undefined}
          initialDate={selectedDateForTask || undefined}
          departments={departments}
          users={users}
        />
      )}
    </div>
  )
}
