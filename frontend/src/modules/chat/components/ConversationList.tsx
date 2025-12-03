/**
 * Lista de conversas - Estilo WhatsApp Web
 * ✅ PERFORMANCE: Componente otimizado com memoização
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Search, Plus, User } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { shallow } from 'zustand/shallow';
import { Conversation } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { upsertConversation } from '../store/conversationUpdater';
import { getDisplayName } from '../utils/phoneFormatter';
import { NewConversationModal } from './NewConversationModal';

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
    activeDepartment 
  } = useChatStore(
    (state) => ({
      conversations: state.conversations,
      setConversations: state.setConversations,
      activeConversation: state.activeConversation,
      setActiveConversation: state.setActiveConversation,
      activeDepartment: state.activeDepartment,
    }),
    shallow // ✅ Comparação shallow para evitar re-renders quando objetos não mudaram
  );
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
        
        // Buscar TODAS as conversas (sem filtro de departamento)
        const response = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at' }
        });
        
        const convs = response.data.results || response.data;
        
        // ✅ CORREÇÃO CRÍTICA: Limpar cache do conversationUpdater antes de fazer merge
        // Isso garante que atualizações importantes não sejam ignoradas por debounce
        const { clearUpdateCache } = await import('../store/conversationUpdater');
        clearUpdateCache();
        
        // ✅ MELHORIA: Usar upsertConversation para cada conversa (evita sobrescrever WebSocket)
        // Isso garante que se WebSocket adicionou conversas enquanto estava carregando, não serão perdidas
        const { conversations: currentConvs } = useChatStore.getState();
        let updatedConvs = currentConvs;
        
        for (const conv of convs) {
          updatedConvs = upsertConversation(updatedConvs, conv);
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
        for (const conv of convs) {
          updatedConvs = upsertConversation(updatedConvs, conv);
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
    
    return conversations.filter((conv) => {
      // 1. Filtro de busca (nome ou telefone) - apenas se houver termo de busca
      if (searchLower) {
        const matchesSearch = 
          conv.contact_name?.toLowerCase().includes(searchLower) ||
          conv.contact_phone.includes(debouncedSearchTerm) ||
          (conv.group_metadata?.group_name || '').toLowerCase().includes(searchLower);
        
        if (!matchesSearch) {
          return false;
        }
      }
      
      // 2. Filtro de departamento (se houver departamento ativo)
      if (!activeDepartment) {
        // ✅ SEM departamento ativo: mostrar TODAS as conversas (inclui novas)
        return true;
      }
      
      if (activeDepartment.id === 'inbox') {
        // Inbox: conversas pendentes SEM departamento
        const departmentId = typeof conv.department === 'string' 
          ? conv.department 
          : conv.department?.id || null;
        const convStatus = conv.status || 'pending';
        
        // ✅ CORREÇÃO: Inbox só mostra conversas SEM departamento E com status='pending'
        return !departmentId && convStatus === 'pending';
      } else {
        // Departamento específico: conversas do departamento (qualquer status EXCETO closed)
        if (conv.status === 'closed') {
          return false;
        }
        
        const departmentId = typeof conv.department === 'string' 
          ? conv.department 
          : conv.department?.id || null;
        
        const activeDeptId = String(activeDepartment.id);
        const convDeptId = departmentId ? String(departmentId) : null;
        
        return convDeptId === activeDeptId;
      }
    });
  }, [conversations, debouncedSearchTerm, activeDepartment]); // ✅ Usar debouncedSearchTerm

  // ✅ PERFORMANCE: Memoizar função de formatação
  const formatTime = useCallback((dateString: string | undefined) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: false, locale: ptBR });
    } catch {
      return '';
    }
  }, []);

  return (
    <div className="flex flex-col h-full w-full bg-white">
      {/* Search + New - Responsivo */}
      <div className="flex-shrink-0 flex items-center gap-2 p-2 sm:p-3 border-b border-gray-200">
        <div className="flex-1 relative min-w-0">
          <Search className="absolute left-2 sm:left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar ou iniciar conversa"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              // ✅ PERFORMANCE: Debounce é feito no useEffect acima
            }}
            className="w-full pl-8 sm:pl-10 pr-3 py-2 bg-[#f0f2f5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#00a884] focus:bg-white transition-colors"
          />
        </div>
        <button
          onClick={() => setShowNewConversation(true)}
          className="flex-shrink-0 p-2 hover:bg-gray-100 active:scale-95 rounded-full transition-all duration-150 shadow-sm hover:shadow-md"
          title="Nova conversa"
        >
          <Plus className="w-5 h-5 text-gray-600" />
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
            <p className="text-sm text-gray-500">Carregando conversas...</p>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="w-24 h-24 mb-4 opacity-20">
              <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400 w-full h-full">
                <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.33-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
              </svg>
            </div>
            <h3 className="text-base font-medium text-gray-700 mb-2">Nenhuma conversa</h3>
            <p className="text-sm text-gray-500 text-center max-w-xs">
              Inicie uma nova conversa para começar!
            </p>
          </div>
        ) : (
          filteredConversations.map((conv, index) => (
            <button
              key={conv.id}
              onClick={() => {
                // ✅ FIX: Verificar se é a mesma conversa antes de definir
                // Se já é a conversa ativa, não fazer nada (evita desselecionar)
                if (activeConversation?.id === conv.id) {
                  console.log('🔕 [LIST] Conversa já está ativa, mantendo selecionada:', conv.id);
                  return;
                }
                console.log('✅ [LIST] Selecionando conversa:', conv.id);
                setActiveConversation(conv);
              }}
              className={`
                w-full flex items-start gap-2 sm:gap-3 px-3 sm:px-4 py-3 
                hover:bg-[#f0f2f5] active:scale-[0.98] 
                transition-all duration-150 border-b border-gray-100
                animate-fade-in
                ${activeConversation?.id === conv.id ? 'bg-[#f0f2f5] shadow-sm' : ''}
              `}
              style={{ animationDelay: `${index * 30}ms` }}
            >
              {/* Avatar com foto - responsivo */}
              <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gray-200 overflow-hidden relative">
                {conv.profile_pic_url ? (
                  <img 
                    src={getMediaProxyUrl(conv.profile_pic_url)}
                    alt={getDisplayName(conv)}
                    className="w-full h-full object-cover"
                    onLoad={() => console.log(`✅ [IMG LIST] Foto carregada: ${conv.contact_name}`)}
                    onError={(e) => {
                      console.error(`❌ [IMG LIST] Erro ao carregar foto: ${conv.contact_name}`, e.currentTarget.src);
                      // Fallback se imagem não carregar
                      e.currentTarget.style.display = 'none';
                      e.currentTarget.parentElement!.innerHTML = `
                        <div class="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                          ${conv.conversation_type === 'group' ? '👥' : (conv.contact_name || conv.contact_phone)[0].toUpperCase()}
                        </div>
                      `;
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                    {conv.conversation_type === 'group' ? '👥' : getDisplayName(conv)[0].toUpperCase()}
                  </div>
                )}
                
                {/* Badge de grupo no canto inferior direito */}
                {conv.conversation_type === 'group' && (
                  <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-[10px]">
                    👥
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0 text-left">
                {/* Nome + Hora */}
                <div className="flex items-baseline justify-between mb-1">
                  <h3 className="font-medium text-gray-900 truncate text-sm flex items-center gap-1">
                    {conv.conversation_type === 'group' && <span>👥</span>}
                    {conv.conversation_type === 'group' 
                      ? (conv.group_metadata?.group_name || conv.contact_name || 'Grupo WhatsApp')
                      : getDisplayName(conv)
                    }
                  </h3>
                  <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                    {formatTime(conv.last_message_at)}
                  </span>
                </div>

                {/* Tags: Instância + Tags do Contato */}
                {((conv.instance_friendly_name || conv.instance_name) || (conv.contact_tags && conv.contact_tags.length > 0)) && (
                  <div className="flex items-center gap-1 flex-wrap mb-1">
                    {/* Tag da Instância (azul) - Exibe nome amigável, não UUID */}
                    {(conv.instance_friendly_name || conv.instance_name) && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-medium">
                        📱 {conv.instance_friendly_name || conv.instance_name}
                      </span>
                    )}
                    
                    {/* Tags do Contato */}
                    {conv.contact_tags && conv.contact_tags.map((tag) => (
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

                {/* Última mensagem + Badge de não lidas */}
                <div className="flex items-center justify-between">
                  {/* ✅ MELHORIA UX: Loading state para última mensagem */}
                  {conv.last_message ? (
                    <p className="text-sm text-gray-600 truncate">
                      {/* Para grupos, mostrar "Nome: mensagem" */}
                      {conv.conversation_type === 'group' && conv.last_message?.sender_name
                        ? `${conv.last_message.sender_name}: ${conv.last_message.content || ''}`
                        : (conv.last_message?.content || '📎 Anexo')
                      }
                    </p>
                  ) : (
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <div className="w-3 h-3 border-2 border-gray-300 border-t-gray-500 rounded-full animate-spin flex-shrink-0" />
                      <span className="text-xs text-gray-400 truncate">Carregando última mensagem...</span>
                    </div>
                  )}
                  {conv.unread_count > 0 && (
                    <span className="ml-2 px-2 py-0.5 bg-green-500 text-white text-xs rounded-full font-medium flex-shrink-0">
                      {conv.unread_count}
                    </span>
                  )}
                </div>
              </div>
            </button>
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
