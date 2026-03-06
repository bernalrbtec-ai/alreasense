/**
 * Lista de conversas - Estilo WhatsApp Web
 * ✅ PERFORMANCE: Componente otimizado com memoização
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, Plus, User, Eye, CircleDot } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { shallow } from 'zustand/shallow';
import { Conversation } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { upsertConversation } from '../store/conversationUpdater';
import { getDisplayName } from '../utils/phoneFormatter';
import { NewConversationModal } from './NewConversationModal';
import { useAuthStore } from '@/stores/authStore';
import { usePermissions } from '@/hooks/usePermissions';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

export function ConversationList() {
  // ✅ PERFORMANCE: Usar seletores específicos com shallow comparison para evitar re-renders desnecessários
  const { 
    conversations, 
    setConversations, 
    activeConversation, 
    setActiveConversation, 
    setOpenInSpyMode,
    openInSpyMode,
    activeDepartment,
    waitingForResponseMode,
    setWaitingForResponseMode,
  } = useChatStore(
    (state) => ({
      conversations: state.conversations,
      setConversations: state.setConversations,
      activeConversation: state.activeConversation,
      setActiveConversation: state.setActiveConversation,
      setOpenInSpyMode: state.setOpenInSpyMode,
      openInSpyMode: state.openInSpyMode,
      activeDepartment: state.activeDepartment,
      waitingForResponseMode: state.waitingForResponseMode,
      setWaitingForResponseMode: state.setWaitingForResponseMode,
    }),
    shallow // ✅ Comparação shallow para evitar re-renders quando objetos não mudaram
  );
  const [refreshTick, setRefreshTick] = useState(0);
  const { isAdmin, isGerente } = usePermissions();
  const canSpy = isAdmin || isGerente;
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [showNewConversation, setShowNewConversation] = useState(false);
  
  // ✅ PERFORMANCE: Debounce na busca para evitar filtros excessivos
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 300); // 300ms de debounce
    
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // ✅ Modo Aguardando Resposta: atualizar tempo de espera a cada 1 min
  useEffect(() => {
    if (!waitingForResponseMode) return;
    const interval = setInterval(() => setRefreshTick((t) => t + 1), 60_000);
    return () => clearInterval(interval);
  }, [waitingForResponseMode]);

  // 🔄 MELHORIA: Buscar conversas apenas na primeira carga (evita sobrescrever WebSocket)
  // WebSocket adicionará novas conversas automaticamente ao Zustand Store via useTenantSocket
  // Filtro por departamento é feito localmente (mais rápido e mantém conversas do WebSocket)
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<number>(0);
  
  // ✅ PERFORMANCE: Refresh inteligente - apenas se necessário (não muito frequente)
  const REFRESH_INTERVAL_MS = 30000; // 30 segundos
  
  useEffect(() => {
    // ✅ MELHORIA: Só buscar uma vez (primeira carga)
    // Se já carregou antes, não buscar novamente (evita sobrescrever WebSocket)
    if (hasLoaded) {
      return;
    }
    
    const fetchConversations = async () => {
      try {
        setLoading(true);
        
        // Buscar conversas com parâmetro assigned_to_me se necessário
        const params: any = { ordering: '-last_message_at' };
        if (activeDepartment?.id === 'my_conversations') {
          params.assigned_to_me = 'true';
        }
        
        const response = await api.get('/chat/conversations/', { params });
        
        const convs = response.data.results || response.data;
        
        // ✅ CORREÇÃO CRÍTICA: Limpar cache do conversationUpdater antes de fazer merge
        // Isso garante que atualizações importantes não sejam ignoradas por debounce
        const { clearUpdateCache } = await import('../store/conversationUpdater');
        clearUpdateCache();
        
        // ✅ MELHORIA: Usar upsertConversation para cada conversa (evita sobrescrever WebSocket)
        // Isso garante que se WebSocket adicionou conversas enquanto estava carregando, não serão perdidas
        const { conversations: currentConvs } = useChatStore.getState();
        let updatedConvs = currentConvs;
        
        for (const conversationItem of convs) {
          updatedConvs = upsertConversation(updatedConvs, conversationItem);
        }
        
        setConversations(updatedConvs);
        setHasLoaded(true);
        setLastRefresh(Date.now());
      } catch (error) {
        console.error('❌ [ConversationList] Erro ao carregar conversas:', error);
        setHasLoaded(true); // Marcar como carregado mesmo em erro para não tentar novamente
      } finally {
        setLoading(false);
      }
    };

    // Buscar conversas apenas na primeira carga
    fetchConversations();
  }, [hasLoaded, setConversations]);

  // ✅ NOVO: Buscar conversas quando mudar para "Minhas Conversas"
  useEffect(() => {
    if (activeDepartment?.id === 'my_conversations' && hasLoaded) {
      const fetchMyConversations = async () => {
        try {
          setLoading(true);
          const params: any = { ordering: '-last_message_at', assigned_to_me: 'true' };
          const response = await api.get('/chat/conversations/', { params });
          const convs = response.data.results || response.data;
          
          const { clearUpdateCache } = await import('../store/conversationUpdater');
          clearUpdateCache();
          
          const { conversations: currentConvs } = useChatStore.getState();
          let updatedConvs = currentConvs;
          
          for (const conversationItem of convs) {
            updatedConvs = upsertConversation(updatedConvs, conversationItem);
          }
          
          setConversations(updatedConvs);
        } catch (error) {
          console.error('❌ [ConversationList] Erro ao carregar minhas conversas:', error);
        } finally {
          setLoading(false);
        }
      };
      
      fetchMyConversations();
    }
  }, [activeDepartment?.id, hasLoaded, setConversations]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const conversationId = params.get('conversation_id');
    if (!conversationId) return;
    if (activeConversation?.id === conversationId) return;

    const match = conversations.find((item) => String(item.id) === conversationId);
    if (match) {
      setActiveConversation(match);
      params.delete('conversation_id');
      const url = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}`;
      window.history.replaceState({}, '', url);
    }
  }, [conversations, activeConversation, setActiveConversation]);
  
  // ✅ NOVO: Refresh inteligente periódico (apenas se necessário)
  // Não muito frequente para não sobrecarregar o servidor
  useEffect(() => {
    if (!hasLoaded) return;
    
    // Verificar se precisa fazer refresh (último refresh foi há mais de 30s)
    const timeSinceLastRefresh = Date.now() - lastRefresh;
    if (timeSinceLastRefresh < REFRESH_INTERVAL_MS) {
      return; // Ainda não precisa refresh
    }
    
    // ✅ Refresh silencioso em background (não mostrar loading)
    const refreshConversations = async () => {
      try {
        const response = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at' }
        });
        
        const convs = response.data.results || response.data;
        const { conversations: currentConvs } = useChatStore.getState();
        let updatedConvs = currentConvs;
        
        // ✅ Usar upsert para não perder conversas do WebSocket
        for (const conversationItem of convs) {
          updatedConvs = upsertConversation(updatedConvs, conversationItem);
        }
        
        setConversations(updatedConvs);
        setLastRefresh(Date.now());
      } catch (error) {
        // Silencioso: não logar erro de refresh periódico
      }
    };
    
    // Refresh a cada 30 segundos se necessário
    const interval = setInterval(() => {
      refreshConversations();
    }, REFRESH_INTERVAL_MS);
    
    return () => clearInterval(interval);
  }, [hasLoaded, lastRefresh, setConversations]);

  // ✅ PERFORMANCE: Memoizar filtro de conversas para evitar recalcular a cada render
  // ✅ OTIMIZAÇÃO: Usar debouncedSearchTerm ao invés de searchTerm direto
  const filteredConversations = useMemo(() => {
    if (!conversations.length) return [];
    
    const searchLower = debouncedSearchTerm.toLowerCase().trim();
    
    // ✅ CORREÇÃO: Renomear conv para conversationItem para evitar conflito de minificação
    const filtered = conversations.filter((conversationItem) => {
      // 1. Filtro de busca (nome ou telefone) - apenas se houver termo de busca
      if (searchLower) {
        const matchesSearch = 
          conversationItem.contact_name?.toLowerCase().includes(searchLower) ||
          conversationItem.contact_phone.includes(debouncedSearchTerm) ||
          (conversationItem.group_metadata?.group_name || '').toLowerCase().includes(searchLower);
        
        if (!matchesSearch) {
          return false;
        }
      }
      
      // 2. Filtro de departamento (se houver departamento ativo)
      if (!activeDepartment) {
        // ✅ SEM departamento ativo: mostrar TODAS as conversas (inclui novas)
        return true;
      }
      
      const departmentId = typeof conversationItem.department === 'string' 
        ? conversationItem.department 
        : conversationItem.department?.id || null;
      const convStatus = conversationItem.status || 'pending';
      const activeDeptId = String(activeDepartment.id);
      const convDeptId = departmentId ? String(departmentId) : null;
      
      // ✅ DEBUG CRÍTICO: Log detalhado para TODAS as conversas sendo filtradas
      // Isso ajuda a identificar por que conversas não aparecem
      const isActiveConversation = activeConversation?.id === conversationItem.id;
      if (isActiveConversation || convStatus === 'pending' || convStatus === 'open') {
        console.log('🔍 [FILTER] Verificando conversa:', {
          conversationId: conversationItem.id,
          conversationName: conversationItem.contact_name,
          conversationPhone: conversationItem.contact_phone,
          conversationDepartmentId: convDeptId,
          conversationDepartmentName: conversationItem.department_name || 'N/A',
          conversationStatus: convStatus,
          activeDepartmentId: activeDeptId,
          activeDepartmentName: activeDepartment.name,
          isActiveConversation,
          departmentMatch: convDeptId === activeDeptId,
          statusMatch: convStatus === 'pending' || (convStatus === 'open' && activeDepartment.id !== 'inbox')
        });
      }
      
      if (activeDepartment.id === 'inbox') {
        // Inbox: conversas pendentes SEM departamento
        // ✅ CORREÇÃO: Inbox só mostra conversas SEM departamento E com status='pending'
        const passes = !departmentId && convStatus === 'pending';
        
        // ✅ DEBUG: Log quando conversa não passa no filtro do Inbox
        if (!passes) {
          console.log('🔍 [FILTER] Conversa não passou no filtro do Inbox:', {
            conversationId: conversationItem.id,
            conversationName: conversationItem.contact_name,
            departmentId: convDeptId,
            status: convStatus,
            reason: departmentId ? 'Tem departamento' : 'Status não é pending',
            expected: 'Sem departamento E status=pending'
          });
        }
        
        return passes;
      }
      
      if (activeDepartment.id === 'my_conversations') {
        // Minhas Conversas: todas as conversas atribuídas ao usuário (com ou sem departamento)
        const { user } = useAuthStore.getState();
        if (!user) return false;
        
        return (
          conversationItem.assigned_to === user.id &&
          conversationItem.status === 'open'
        );
      } else {
        // Departamento específico: conversas do departamento (qualquer status EXCETO closed)
        if (conversationItem.status === 'closed') {
          console.warn('⚠️ [FILTER] Conversa fechada, excluindo:', {
            conversationId: conversationItem.id,
            conversationName: conversationItem.contact_name,
            conversationPhone: conversationItem.contact_phone,
            status: conversationItem.status,
            department: conversationItem.department_name || 'N/A',
            departmentId: convDeptId,
            activeDepartmentId: activeDeptId,
            activeDepartmentName: activeDepartment.name,
            last_message_at: conversationItem.last_message_at,
            isActiveConversation: isActiveConversation,
            reason: 'Status é closed - conversa não deve aparecer na lista'
          });
          return false;
        }
        
        const passes = convDeptId === activeDeptId;
        
        // ✅ DEBUG: Log quando conversa não passa no filtro do departamento
        if (!passes) {
          console.log('🔍 [FILTER] Conversa não passou no filtro do departamento:', {
            conversationId: conversationItem.id,
            conversationName: conversationItem.contact_name,
            activeDepartmentId: activeDeptId,
            activeDepartmentName: activeDepartment.name,
            conversationDepartmentId: convDeptId,
            conversationDepartmentName: conversationItem.department_name || 'N/A',
            conversationStatus: convStatus,
            reason: convDeptId !== activeDeptId ? 'Departamento diferente' : 'Status closed',
            expected: `departmentId === ${activeDeptId}`
          });
        } else {
          console.log('✅ [FILTER] Conversa passou no filtro do departamento:', {
            conversationId: conversationItem.id,
            conversationName: conversationItem.contact_name,
            departmentId: convDeptId,
            status: convStatus
          });
        }
        
        return passes;
      }
    });
    
    // ✅ DEBUG: Log do resultado do filtro
    if (filtered.length !== conversations.length) {
      console.log('🔍 [FILTER] Resultado do filtro:', {
        totalConversations: conversations.length,
        filteredConversations: filtered.length,
        activeDepartment: activeDepartment?.name || 'Nenhum',
        searchTerm: debouncedSearchTerm || 'Nenhum'
      });
    }

    // Modo normal: mesma ordem do store (last_message_at desc)
    if (!waitingForResponseMode) return filtered;

    // Modo Aguardando Resposta: só última mensagem do cliente, ordenar da mais atrasada (topo)
    const waitingList = filtered.filter((c) => c.last_message?.direction === 'incoming');
    const activeId = activeConversation?.id != null ? String(activeConversation.id) : null;
    const needsPin =
      activeId &&
      filtered.some((c) => String(c.id) === activeId) &&
      !waitingList.some((c) => String(c.id) === activeId);
    const sortedWaiting = [...waitingList].sort((a, b) => {
      const tA = new Date(a.last_message_at).getTime() || 0;
      const tB = new Date(b.last_message_at).getTime() || 0;
      return tA - tB || String(a.id).localeCompare(String(b.id));
    });
    return needsPin && activeConversation ? [activeConversation, ...sortedWaiting] : sortedWaiting;
  }, [conversations, debouncedSearchTerm, activeDepartment, waitingForResponseMode, activeConversation?.id]);

  // ✅ PERFORMANCE: Memoizar função de formatação
  const formatTime = useCallback((dateString: string | undefined) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: false, locale: ptBR });
    } catch {
      return '';
    }
  }, []);

  // Tempo de espera (modo Aguardando Resposta): ícone CircleDot (pendente) + "Xh Ymin" ou "Xmin"
  const formatWaitingTime = useCallback((dateString: string | undefined) => {
    if (!dateString) return '';
    try {
      const diffMs = Date.now() - new Date(dateString).getTime();
      if (Number.isNaN(diffMs) || diffMs < 0) return '0min';
      const totalMins = Math.floor(diffMs / 60_000);
      const hours = Math.floor(totalMins / 60);
      const mins = totalMins % 60;
      if (hours === 0) return `${mins}min`;
      return mins === 0 ? `${hours}h` : `${hours}h ${mins}min`;
    } catch {
      return '';
    }
  }, []);

  return (
    <div className="flex flex-col h-full w-full bg-white dark:bg-gray-800">
      {/* Search + New - Responsivo */}
      <div className="flex-shrink-0 flex items-center gap-2 p-2 sm:p-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex-1 relative min-w-0">
          <Search className="absolute left-2 sm:left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
          <input
            type="text"
            placeholder="Buscar ou iniciar conversa"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              // ✅ PERFORMANCE: Debounce é feito no useEffect acima
            }}
            className="w-full pl-8 sm:pl-10 pr-3 py-2 bg-[#f0f2f5] dark:bg-gray-800 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#00a884] focus:bg-white dark:focus:bg-gray-700 transition-colors text-gray-900 dark:text-white"
          />
        </div>
        <button
          onClick={() => {
            console.log('🆕 [CONVERSATION LIST] Botão Nova Conversa clicado');
            setShowNewConversation(true);
            console.log('🆕 [CONVERSATION LIST] showNewConversation setado para true');
          }}
          className="flex-shrink-0 p-2 hover:bg-gray-100 dark:hover:bg-gray-700 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
          title="Nova conversa"
        >
          <Plus className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="flex gap-2 mb-3">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">Carregando conversas...</p>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="w-24 h-24 mb-4 opacity-20">
              <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400 w-full h-full">
                <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.33-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
              </svg>
            </div>
            {waitingForResponseMode ? (
              <>
                <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">Nenhuma conversa aguardando resposta</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs mb-4">
                  Desative o filtro para ver todas as conversas.
                </p>
                <button
                  type="button"
                  onClick={() => setWaitingForResponseMode(false)}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Desative o filtro
                </button>
              </>
            ) : (
              <>
                <h3 className="text-base font-medium text-gray-700 dark:text-gray-300 mb-2">Nenhuma conversa</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-xs">
                  Inicie uma nova conversa para começar!
                </p>
              </>
            )}
          </div>
        ) : (
          filteredConversations.map((conversationItem, index) => (
            <div
              key={conversationItem.id}
              role="button"
              tabIndex={0}
              onClick={() => {
                const isSame = activeConversation?.id === conversationItem.id;
                if (isSame && openInSpyMode) {
                  setOpenInSpyMode(false);
                  return;
                }
                if (isSame && !openInSpyMode) {
                  return;
                }
                setActiveConversation(conversationItem);
                setOpenInSpyMode(false);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  const isSame = activeConversation?.id === conversationItem.id;
                  if (isSame && openInSpyMode) {
                    setOpenInSpyMode(false);
                    return;
                  }
                  if (isSame && !openInSpyMode) return;
                  setActiveConversation(conversationItem);
                  setOpenInSpyMode(false);
                }
              }}
              className={`
                w-full flex items-start gap-2 sm:gap-3 px-3 sm:px-4 py-3 
                hover:bg-[#f0f2f5] dark:hover:bg-gray-700 active:scale-[0.98] 
                transition-all duration-150 border-b border-gray-100 dark:border-gray-700
                animate-fade-in cursor-pointer
                ${activeConversation?.id === conversationItem.id ? 'bg-[#f0f2f5] dark:bg-gray-700 shadow-sm' : ''}
              `}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              {/* Avatar com foto - responsivo */}
              <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden relative">
                {conversationItem.profile_pic_url ? (
                    <img
                      src={getMediaProxyUrl(conversationItem.profile_pic_url)}
                      alt={getDisplayName(conversationItem)}
                    className="w-full h-full object-cover"
                      onLoad={() => console.log(`✅ [IMG LIST] Foto carregada: ${conversationItem.contact_name}`)}
                      onError={(e) => {
                        console.error(`❌ [IMG LIST] Erro ao carregar foto: ${conversationItem.contact_name}`, e.currentTarget.src);
                      // Fallback se imagem não carregar
                      e.currentTarget.style.display = 'none';
                      e.currentTarget.parentElement!.innerHTML = `
                        <div class="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                          ${conversationItem.conversation_type === 'group' ? '👥' : (conversationItem.contact_name || conversationItem.contact_phone)[0].toUpperCase()}
                        </div>
                      `;
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300 font-medium text-lg">
                    {conversationItem.conversation_type === 'group' ? '👥' : getDisplayName(conversationItem)[0].toUpperCase()}
                  </div>
                )}
                
                {/* Badge de grupo no canto inferior direito */}
                {conversationItem.conversation_type === 'group' && (
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-[10px]">
                    👥
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0 text-left">
                {/* Nome + Hora */}
                <div className="flex items-baseline justify-between mb-1">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate text-sm flex items-center gap-1">
                    {conversationItem.conversation_type === 'group' && <span>👥</span>}
                    {conversationItem.conversation_type === 'group' 
                      ? (conversationItem.group_metadata?.group_name || conversationItem.contact_name || 'Grupo WhatsApp')
                      : getDisplayName(conversationItem)
                    }
                  </h3>
                  <span className="text-xs text-gray-500 dark:text-gray-400 ml-2 flex-shrink-0 flex items-center gap-1">
                    {waitingForResponseMode ? (
                      <>
                        <CircleDot className="w-3.5 h-3.5 flex-shrink-0" aria-hidden />
                        {formatWaitingTime(conversationItem.last_message_at)}
                      </>
                    ) : (
                      formatTime(conversationItem.last_message_at)
                    )}
                  </span>
                </div>

                {/* Tags: Instância + Tags do Contato */}
                {((conversationItem.instance_friendly_name || conversationItem.instance_name) || (conversationItem.contact_tags && conversationItem.contact_tags.length > 0)) && (
                  <div className="flex items-center gap-1 flex-wrap mb-1">
                    {/* Tag da Instância (azul) - Exibe nome amigável, não UUID */}
                    {(conversationItem.instance_friendly_name || conversationItem.instance_name) && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-[10px] font-medium">
                        📱 {conversationItem.instance_friendly_name || conversationItem.instance_name}
                      </span>
                    )}
                    
                    {/* Tags do Contato */}
                    {conversationItem.contact_tags && conversationItem.contact_tags.map((tag) => (
                      <span 
                        key={tag.id}
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium"
                        style={{
                          backgroundColor: `${tag.color}20`,
                          color: tag.color
                        }}
                      >
                        🏷️ {tag.name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Aviso: Fulano está atendendo (apenas na aba do departamento) */}
                {conversationItem.assigned_to && activeDepartment?.id !== 'my_conversations' && activeDepartment?.id !== 'inbox' && (
                  <div className="flex items-center gap-1 mb-1">
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200 rounded text-[10px] font-medium">
                      👤 {(conversationItem.assigned_to_data?.first_name || conversationItem.assigned_to_data?.email || 'Atendente').trim() || 'Atendente'} está atendendo
                    </span>
                  </div>
                )}

                {/* Última mensagem + Badge de não lidas */}
                <div className="flex items-center justify-between">
                  {/* ✅ MELHORIA UX: Loading state para última mensagem */}
                  {conversationItem.last_message ? (
                    <p className="text-sm text-gray-600 dark:text-gray-400 truncate">
                      {/* Mensagem apagada: indicar sem exibir conteúdo */}
                      {conversationItem.last_message?.is_deleted
                        ? 'Mensagem apagada'
                        : (() => {
                            const raw = conversationItem.last_message?.content;
                            const c = typeof raw === 'string' ? raw : String(raw ?? '');
                            const preview = (c.trim() === '[button]' || c.trim() === '[interactive]' ? 'Resposta de botão' : c.trim() === '[templateMessage]' ? 'Mensagem de template' : c.trim() === '[buttonsMessage]' ? 'Mensagem com botões' : c) || '';
                            return conversationItem.conversation_type === 'group' && conversationItem.last_message?.sender_name
                              ? `${conversationItem.last_message.sender_name}: ${preview}`
                              : (preview || '📎 Anexo');
                          })()
                      }
                    </p>
                  ) : (
                    // ✅ CORREÇÃO: Para conversas novas sem mensagens, mostrar texto estático ao invés de loading infinito
                    <p className="text-sm text-gray-400 dark:text-gray-500 italic truncate">
                      Nova conversa
                    </p>
                  )}
                  {conversationItem.unread_count > 0 && (
                    <span className="ml-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full font-medium flex-shrink-0">
                      {conversationItem.unread_count}
                    </span>
                  )}
                </div>
              </div>

              {/* Modo Espião: abrir sem marcar como lida (apenas admin/gerente) */}
              {canSpy && (
                <button
                  type="button"
                  className={`flex-shrink-0 p-1.5 rounded-full transition-colors ${
                    activeConversation?.id === conversationItem.id && openInSpyMode
                      ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800/40'
                      : 'hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                  }`}
                  title={activeConversation?.id === conversationItem.id && openInSpyMode ? 'Sair do modo espião (assumir conversa)' : 'Abrir em modo espião (não marca como lida)'}
                  onClick={(e) => {
                    e.stopPropagation();
                    const isSameAndSpy = activeConversation?.id === conversationItem.id && openInSpyMode;
                    if (isSameAndSpy) {
                      setOpenInSpyMode(false);
                    } else {
                      setActiveConversation(conversationItem);
                      setOpenInSpyMode(true);
                    }
                  }}
                  aria-label={activeConversation?.id === conversationItem.id && openInSpyMode ? 'Sair do modo espião' : 'Abrir em modo espião'}
                  aria-pressed={activeConversation?.id === conversationItem.id && openInSpyMode}
                >
                  <Eye className="w-4 h-4" aria-hidden />
                </button>
              )}
            </div>
          ))
        )}
      </div>

      {/* Modal de Nova Conversa */}
      <NewConversationModal
        isOpen={showNewConversation}
        onClose={() => setShowNewConversation(false)}
      />
    </div>
  );
}
