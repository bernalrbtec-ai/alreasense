/**
 * Lista de conversas - Estilo WhatsApp Web
 */
import React, { useState, useEffect } from 'react';
import { Search, Plus, User } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Conversation } from '../types';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

export function ConversationList() {
  const { conversations, setConversations, activeConversation, setActiveConversation, activeDepartment } = useChatStore();
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showNewConversation, setShowNewConversation] = useState(false);
  
  // 🔍 Debug: Log quando conversations mudam
  useEffect(() => {
    console.log('📋 [ConversationList] Conversas no store:', conversations.length);
    if (activeDepartment) {
      const filtered = conversations.filter(conv => {
        if (activeDepartment.id === 'inbox') {
          // Inbox: conversas pendentes SEM departamento
          const departmentId = typeof conv.department === 'string' 
            ? conv.department 
            : conv.department?.id || null;
          return conv.status === 'pending' && !departmentId;
        } else {
          // Departamento específico: conversas do departamento (qualquer status)
          const departmentId = typeof conv.department === 'string' 
            ? conv.department 
            : conv.department?.id || null;
          return departmentId === activeDepartment.id;
        }
      });
      console.log(`   📂 Filtradas para ${activeDepartment.name}:`, filtered.length);
    }
  }, [conversations, activeDepartment]);

  // 🔄 FIX V2: Buscar conversas ao montar componente (apenas uma vez)
  // WebSocket adicionará novas conversas automaticamente ao Zustand Store via useTenantSocket
  // Filtro por departamento é feito localmente (mais rápido e mantém conversas do WebSocket)
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        setLoading(true);
        console.log('🔄 [ConversationList] Carregando conversas iniciais...');
        
        // Buscar TODAS as conversas (sem filtro de departamento)
        const response = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at' }
        });
        
        const convs = response.data.results || response.data;
        console.log(`✅ [ConversationList] ${convs.length} conversas carregadas`);
        setConversations(convs);
      } catch (error) {
        console.error('❌ [ConversationList] Erro ao carregar conversas:', error);
      } finally {
        setLoading(false);
      }
    };

    // Buscar conversas ao montar componente (apenas uma vez)
    fetchConversations();
    
    // Limpar ao desmontar (boa prática)
    return () => {
      console.log('🧹 [ConversationList] Desmontando componente');
    };
  }, []); // Array vazio = executa apenas uma vez no mount

  // 🎯 Filtrar conversas localmente (busca + departamento)
  const filteredConversations = conversations.filter((conv) => {
    // 1. Filtro de busca (nome ou telefone)
    const matchesSearch = 
      conv.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      conv.contact_phone.includes(searchTerm);
    
    if (!matchesSearch) return false;
    
    // 2. Filtro de departamento (se houver departamento ativo)
    if (!activeDepartment) return true;
    
    if (activeDepartment.id === 'inbox') {
      // Inbox: conversas pendentes SEM departamento
      // Tratar department como string (ID) ou objeto ou null
      const departmentId = typeof conv.department === 'string' 
        ? conv.department 
        : conv.department?.id || null;
      return conv.status === 'pending' && !departmentId;
    } else {
      // Departamento específico: conversas do departamento (qualquer status)
      // ✅ Tratar department como string (ID) ou objeto { id, name }
      const departmentId = typeof conv.department === 'string' 
        ? conv.department 
        : conv.department?.id || null;
      return departmentId === activeDepartment.id;
    }
  });

  const formatTime = (dateString: string | undefined) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: false, locale: ptBR });
    } catch {
      return '';
    }
  };

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
            onChange={(e) => setSearchTerm(e.target.value)}
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
              onClick={() => setActiveConversation(conv)}
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
                    alt={conv.contact_name || conv.contact_phone}
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
                    {conv.conversation_type === 'group' ? '👥' : (conv.contact_name || conv.contact_phone)[0].toUpperCase()}
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
                      : (conv.contact_name || conv.contact_phone)
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
                  <p className="text-sm text-gray-600 truncate">
                    {/* Para grupos, mostrar "Nome: mensagem" */}
                    {conv.conversation_type === 'group' && conv.last_message?.sender_name
                      ? `${conv.last_message.sender_name}: ${conv.last_message.content || ''}`
                      : (conv.last_message?.content || 'Sem mensagens')
                    }
                  </p>
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
    </div>
  );
}
