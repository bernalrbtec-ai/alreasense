/**
 * Tabs de departamentos - Estilo WhatsApp Web
 */
import React, { useEffect, useMemo } from 'react';
import { Inbox, User, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Department } from '../types';
import { usePermissions } from '@/hooks/usePermissions';
import { NotificationToggle } from './NotificationToggle';
import { useAuthStore } from '@/stores/authStore';

export function DepartmentTabs() {
  const { departments, activeDepartment, setDepartments, setActiveDepartment, conversations, waitingForResponseMode, setWaitingForResponseMode } = useChatStore();
  const { user } = useAuthStore();
  const { can_access_all_departments, departmentIds } = usePermissions();
  
  // ✅ FIX: Filtrar departamentos sempre baseado nas permissões do usuário
  // Isso garante que mesmo se departamentos forem adicionados via WebSocket ou outras fontes,
  // apenas os permitidos serão exibidos
  const filteredDepartments = useMemo(() => {
    if (can_access_all_departments) {
      return departments;
    }
    if (!departmentIds || departmentIds.length === 0) {
      return [];
    }
    return departments.filter((dept) => departmentIds.includes(dept.id));
  }, [departments, can_access_all_departments, departmentIds]);
  
  // ✅ FIX: Limpar activeDepartment se não estiver mais na lista de departamentos permitidos
  // ✅ CORREÇÃO: Não limpar se for 'my_conversations' (tab especial)
  useEffect(() => {
    if (activeDepartment && activeDepartment.id !== 'inbox' && activeDepartment.id !== 'my_conversations') {
      const isAllowed = filteredDepartments.some(dept => dept.id === activeDepartment.id);
      if (!isAllowed) {
        console.log('🔒 [DEPARTMENTS] Departamento ativo não permitido, mudando para Inbox');
        setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
      }
    }
  }, [filteredDepartments, activeDepartment, setActiveDepartment]);
  
  // ✅ NOVO: Calcular contador de novas conversas (pendentes) para Inbox e departamentos
  const getPendingCount = (deptId: string | null) => {
    if (deptId === 'inbox') {
      // Inbox: conversas pendentes SEM departamento
      const inboxCount = conversations.filter(conv => 
        conv.status === 'pending' && 
        (!conv.department || conv.department === null)
      ).length;
      return inboxCount;
    } else {
      // ✅ MELHORIA: Usar pending_count do backend se disponível, senão calcular do frontend
      const dept = filteredDepartments.find(d => d.id === deptId);
      if (dept?.pending_count !== undefined && dept.pending_count !== null) {
        return dept.pending_count;
      }
      
      // Fallback: calcular do frontend
      return conversations.filter(conv => 
        conv.status === 'pending' && 
        (typeof conv.department === 'string' ? conv.department === deptId : conv.department?.id === deptId)
      ).length;
    }
  };

  // ✅ Contador de minhas conversas (atribuídas ao usuário, com ou sem departamento)
  const getMyConversationsCount = () => {
    const { user } = useAuthStore.getState();
    if (!user) return 0;
    
    return conversations.filter(conv => 
      conv.assigned_to === user.id && 
      conv.status === 'open'
    ).length;
  };

  const waitingCount = useMemo(() => {
    if (!waitingForResponseMode) return 0;
    const incoming = (c: typeof conversations[0]) => c.last_message?.direction === 'incoming';
    if (!activeDepartment) return conversations.filter(incoming).length;
    if (activeDepartment.id === 'inbox') {
      return conversations.filter((c) => {
        const deptId = typeof c.department === 'string' ? c.department : c.department?.id ?? null;
        return !deptId && c.status === 'pending' && incoming(c);
      }).length;
    }
    if (activeDepartment.id === 'my_conversations') {
      if (!user) return 0;
      return conversations.filter((c) => c.assigned_to === user.id && c.status === 'open' && incoming(c)).length;
    }
    return conversations.filter((c) => {
      const deptId = typeof c.department === 'string' ? c.department : c.department?.id;
      return deptId === activeDepartment.id && c.status !== 'closed' && incoming(c);
    }).length;
  }, [waitingForResponseMode, conversations, activeDepartment, user?.id]);

  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        const response = await api.get('/auth/departments/');
        const depts = response.data.results || response.data;
        
        // ✅ DEBUG: Log para verificar se pending_count está vindo do backend
        console.log('📊 [DEPARTMENTS] Departamentos recebidos:', depts.map((d: Department) => ({
          id: d.id,
          name: d.name,
          pending_count: d.pending_count
        })));
        
        let filteredDepts = depts;
        if (!can_access_all_departments && departmentIds) {
          filteredDepts = depts.filter((d: Department) => departmentIds.includes(d.id));
        }
        
        setDepartments(filteredDepts);
        
        // Se não tem departamento ativo, selecionar Inbox
        if (!activeDepartment) {
          setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
        }
      } catch (error) {
        console.error('Erro ao carregar departamentos:', error);
      }
    };

    fetchDepartments();
    
    // ✅ NOVO: Refetch departamentos a cada 30 segundos para atualizar contadores
    const interval = setInterval(fetchDepartments, 30000);
    
    return () => clearInterval(interval);
  }, [can_access_all_departments, departmentIds, setDepartments, setActiveDepartment, activeDepartment]);

  return (
    <div className="flex-shrink-0 flex items-center justify-between gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 sm:py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 overflow-x-auto scrollbar-hide">
      <div className="flex items-center gap-1 sm:gap-1.5 overflow-x-auto scrollbar-hide">
        {/* Tab Inbox - Responsivo */}
        <button
          onClick={() => setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department)}
          className={`
            flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === 'inbox'
              ? 'bg-[#ea580c] text-white'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
            }
          `}
        >
          <Inbox className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          <span className="hidden sm:inline">
            Inbox
            {getPendingCount('inbox') > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
                {getPendingCount('inbox')}
              </span>
            )}
          </span>
          {getPendingCount('inbox') > 0 && (
            <span className="sm:hidden px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
              {getPendingCount('inbox')}
            </span>
          )}
        </button>

        {/* Tab Minhas Conversas */}
        <button
          onClick={() => setActiveDepartment({ id: 'my_conversations', name: 'Minhas Conversas', color: '#3b82f6' } as Department)}
          className={`
            flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === 'my_conversations'
              ? 'bg-[#3b82f6] text-white'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
            }
          `}
        >
          <User className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          <span className="hidden sm:inline">
            Minhas Conversas
            {getMyConversationsCount() > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
                {getMyConversationsCount()}
              </span>
            )}
          </span>
          {getMyConversationsCount() > 0 && (
            <span className="sm:hidden px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
              {getMyConversationsCount()}
            </span>
          )}
        </button>

        {/* Tabs Departamentos - Responsivo */}
        {filteredDepartments.map((dept) => {
          const pendingCount = getPendingCount(dept.id);
          return (
            <button
              key={dept.id}
              onClick={() => setActiveDepartment(dept)}
              className={`
                flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
                ${activeDepartment?.id === dept.id
                  ? 'bg-[#00a884] text-white'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
                }
              `}
            >
              <span className="hidden sm:inline">
                {dept.name}
                {pendingCount > 0 && (
                  <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs font-semibold ${
                    activeDepartment?.id === dept.id ? 'bg-white/20' : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                  }`}>
                    {pendingCount}
                  </span>
                )}
              </span>
              <span className="sm:hidden">{dept.name}</span>
              {pendingCount > 0 && (
                <span className={`sm:hidden px-1.5 py-0.5 rounded-full text-xs font-semibold ${
                  activeDepartment?.id === dept.id ? 'bg-white/20' : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                }`}>
                  {pendingCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Aguardando Resposta + Notificações */}
      <div className="flex-shrink-0 ml-auto flex items-center gap-0.5">
        <button
          type="button"
          role="switch"
          aria-checked={waitingForResponseMode}
          aria-label="Filtrar por conversas aguardando resposta"
          title={waitingForResponseMode
            ? `Aguardando Resposta (${waitingCount} aguardando) - Clique para desativar`
            : 'Mostrar só conversas em que o cliente respondeu por último, ordenadas pela mais antiga no topo'}
          onClick={() => setWaitingForResponseMode(!waitingForResponseMode)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              setWaitingForResponseMode(!waitingForResponseMode);
            }
          }}
          className={`
            relative min-h-[44px] min-w-[44px] p-2 rounded-full transition-colors flex items-center justify-center
            ${waitingForResponseMode
              ? 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/40 hover:bg-green-200 dark:hover:bg-green-900/60'
              : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}
          `}
        >
          <Clock className="w-5 h-5" aria-hidden />
          {waitingForResponseMode && waitingCount > 0 && (
            <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-green-500" aria-hidden />
          )}
        </button>
        <NotificationToggle />
      </div>
    </div>
  );
}
