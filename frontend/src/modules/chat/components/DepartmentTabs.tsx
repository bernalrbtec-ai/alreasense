/**
 * Tabs de departamentos - Estilo WhatsApp Web
 */
import React, { useEffect, useMemo } from 'react';
import { Inbox } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Department } from '../types';
import { usePermissions } from '@/hooks/usePermissions';
import { NotificationToggle } from './NotificationToggle';

export function DepartmentTabs() {
  const { departments, activeDepartment, setDepartments, setActiveDepartment, conversations } = useChatStore();
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
  useEffect(() => {
    if (activeDepartment && activeDepartment.id !== 'inbox') {
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
    <div className="flex-shrink-0 flex items-center justify-between gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 sm:py-2 bg-white border-b border-gray-200 overflow-x-auto scrollbar-hide">
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

      {/* Botão de Notificações */}
      <div className="flex-shrink-0 ml-auto">
        <NotificationToggle />
      </div>
    </div>
  );
}
