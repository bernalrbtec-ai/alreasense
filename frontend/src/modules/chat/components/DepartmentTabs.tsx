/**
 * Tabs de departamentos - Estilo WhatsApp Web
 */
import React, { useEffect, useMemo } from 'react';
import { Inbox, User, Users, CircleDot } from 'lucide-react';
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
    if (activeDepartment && activeDepartment.id !== 'inbox' && activeDepartment.id !== 'my_conversations' && activeDepartment.id !== 'groups') {
      const isAllowed = filteredDepartments.some(dept => dept.id === activeDepartment.id);
      if (!isAllowed) {
        setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
      }
    }
  }, [filteredDepartments, activeDepartment, setActiveDepartment]);
  
  // ✅ NOVO: Calcular contador de novas conversas (pendentes) para Inbox e departamentos
  // status pode vir undefined da API; tratamos com ?? para evitar inconsistência
  const getPendingCount = (deptId: string | null) => {
    const notGroup = (conv: typeof conversations[0]) => conv.conversation_type !== 'group';
    if (deptId === 'inbox') {
      return conversations.filter(conv =>
        notGroup(conv) &&
        (conv.status ?? 'pending') === 'pending' &&
        (!conv.department || conv.department === null)
      ).length;
    }
    const dept = filteredDepartments.find(d => d.id === deptId);
    if (dept?.pending_count !== undefined && dept.pending_count !== null) {
      return dept.pending_count;
    }
    return conversations.filter(conv =>
      notGroup(conv) &&
      (conv.status ?? 'pending') === 'pending' &&
      (typeof conv.department === 'string' ? conv.department === deptId : conv.department?.id === deptId)
    ).length;
  };

  // ✅ Contador de minhas conversas (atribuídas ao usuário, excluir grupos - aba Grupos)
  const getMyConversationsCount = () => {
    const { user } = useAuthStore.getState();
    if (!user) return 0;
    return conversations.filter(conv =>
      conv.conversation_type !== 'group' &&
      conv.assigned_to === user.id &&
      (conv.status ?? 'open') === 'open'
    ).length;
  };

  // ✅ PERFORMANCE: Evitar recalcular os mesmos contadores várias vezes por render
  const pendingInboxCount = useMemo(() => getPendingCount('inbox'), [conversations]);
  const myConversationsCount = useMemo(() => getMyConversationsCount(), [conversations, user?.id]);

  const waitingCount = useMemo(() => {
    if (!waitingForResponseMode) return 0;
    const incoming = (c: typeof conversations[0]) => c.last_message?.direction === 'incoming';
    // Quando ainda não há tab ativa, excluir grupos (evita flash de contagem com grupos)
    if (!activeDepartment) return conversations.filter((c) => c.conversation_type !== 'group' && incoming(c)).length;
    // Aba Grupos: só grupos com última mensagem do cliente
    if (activeDepartment?.id === 'groups') {
      return conversations.filter((c) => c.conversation_type === 'group' && incoming(c)).length;
    }
    if (activeDepartment?.id === 'inbox') {
      return conversations.filter((c) => {
        const deptId = typeof c.department === 'string' ? c.department : c.department?.id ?? null;
        return !deptId && (c.status ?? 'pending') === 'pending' && incoming(c);
      }).length;
    }
    if (activeDepartment?.id === 'my_conversations') {
      if (!user) return 0;
      return conversations.filter((c) => c.assigned_to === user.id && (c.status ?? 'open') === 'open' && incoming(c)).length;
    }
    const deptId = activeDepartment?.id;
    return conversations.filter((c) => {
      const cDeptId = typeof c.department === 'string' ? c.department : c.department?.id;
      return cDeptId === deptId && (c.status ?? 'open') !== 'closed' && incoming(c);
    }).length;
  }, [waitingForResponseMode, conversations, activeDepartment, user?.id]);

  // Buscar departamentos só na montagem e a cada 30s (não ao trocar de aba — evita 7–10s de atraso)
  useEffect(() => {
    const fetchDepartments = async () => {
      try {
        const response = await api.get('/auth/departments/');
        const depts = response.data.results || response.data;
        let filteredDepts = depts;
        if (!can_access_all_departments && departmentIds) {
          filteredDepts = depts.filter((d: Department) => departmentIds.includes(d.id));
        }
        setDepartments(filteredDepts);
        const current = useChatStore.getState().activeDepartment;
        if (!current) {
          setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department);
        }
      } catch (error) {
        console.error('Erro ao carregar departamentos:', error);
      }
    };

    fetchDepartments();
    const interval = setInterval(fetchDepartments, 30000);
    return () => clearInterval(interval);
  }, [can_access_all_departments, departmentIds, setDepartments, setActiveDepartment]);

  return (
    <div className="flex-shrink-0 flex items-center justify-between gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 sm:py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 overflow-x-auto scrollbar-hide">
      <div className="flex items-center gap-1 sm:gap-1.5 overflow-x-auto scrollbar-hide">
        {/* Tab Inbox - Responsivo */}
        <button
          type="button"
          aria-label={pendingInboxCount > 0 ? `Inbox, ${pendingInboxCount} pendentes` : 'Inbox'}
          aria-current={activeDepartment?.id === 'inbox' ? 'true' : undefined}
          onClick={() => setActiveDepartment({ id: 'inbox', name: 'Inbox', color: '#ea580c' } as Department)}
          className={`
            flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === 'inbox'
              ? 'bg-[#ea580c] text-white'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
            }
          `}
        >
          <Inbox className="w-3.5 h-3.5 sm:w-4 sm:h-4" aria-hidden />
          <span className="hidden sm:inline">
            Inbox
            {pendingInboxCount > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
                {pendingInboxCount}
              </span>
            )}
          </span>
          {pendingInboxCount > 0 && (
            <span className="sm:hidden px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
              {pendingInboxCount}
            </span>
          )}
        </button>

        {/* Tab Minhas Conversas */}
        <button
          type="button"
          aria-label={myConversationsCount > 0 ? `Minhas Conversas, ${myConversationsCount} abertas` : 'Minhas Conversas'}
          aria-current={activeDepartment?.id === 'my_conversations' ? 'true' : undefined}
          onClick={() => setActiveDepartment({ id: 'my_conversations', name: 'Minhas Conversas', color: '#3b82f6' } as Department)}
          className={`
            flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === 'my_conversations'
              ? 'bg-[#3b82f6] text-white'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
            }
          `}
        >
          <User className="w-3.5 h-3.5 sm:w-4 sm:h-4" aria-hidden />
          <span className="hidden sm:inline">
            Minhas Conversas
            {myConversationsCount > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
                {myConversationsCount}
              </span>
            )}
          </span>
          {myConversationsCount > 0 && (
            <span className="sm:hidden px-1.5 py-0.5 rounded-full bg-white/20 text-xs font-semibold">
              {myConversationsCount}
            </span>
          )}
        </button>

        {/* Tab Grupos */}
        <button
          type="button"
          aria-label="Grupos"
          aria-current={activeDepartment?.id === 'groups' ? 'true' : undefined}
          onClick={() => setActiveDepartment({ id: 'groups', name: 'Grupos', color: '#8b5cf6' } as Department)}
          className={`
            flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all whitespace-nowrap flex-shrink-0
            ${activeDepartment?.id === 'groups'
              ? 'bg-[#8b5cf6] text-white'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95'
            }
          `}
          title="Grupos"
        >
          <Users className="w-3.5 h-3.5 sm:w-4 sm:h-4" aria-hidden />
          <span className="hidden sm:inline">Grupos</span>
        </button>

        {/* Tabs Departamentos - Responsivo */}
        {filteredDepartments.map((dept) => {
          const pendingCount = getPendingCount(dept.id);
          return (
            <button
              type="button"
              key={dept.id}
              aria-label={pendingCount > 0 ? `${dept.name}, ${pendingCount} pendentes` : dept.name}
              aria-current={activeDepartment?.id === dept.id ? 'true' : undefined}
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
          <CircleDot className="w-5 h-5" aria-hidden />
          {waitingForResponseMode && waitingCount > 0 && (
            <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-green-500" aria-hidden />
          )}
        </button>
        <NotificationToggle />
      </div>
    </div>
  );
}
