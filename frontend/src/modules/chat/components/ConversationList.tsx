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

export function ConversationList() {
  const { conversations, setConversations, activeConversation, setActiveConversation, activeDepartment } = useChatStore();
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showNewConversation, setShowNewConversation] = useState(false);
  
  // 🔍 Debug: Log quando conversations mudam
  useEffect(() => {
    console.log('📋 [ConversationList] Conversas atualizadas:', conversations.length);
    conversations.forEach(conv => {
      if (conv.profile_pic_url) {
        console.log(`  ✅ ${conv.contact_name}: tem foto`);
      }
    });
  }, [conversations]);

  useEffect(() => {
    if (!activeDepartment) return;

    const fetchConversations = async () => {
      try {
        setLoading(true);
        const params: any = {
          ordering: '-last_message_at'
        };

        if (activeDepartment.id === 'inbox') {
          params.status = 'pending';
        } else {
          params.department = activeDepartment.id;
        }

        const response = await api.get('/chat/conversations/', { params });
        const convs = response.data.results || response.data;
        setConversations(convs);
      } catch (error) {
        console.error('❌ Erro ao carregar conversas:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, [activeDepartment, setConversations]);

  const filteredConversations = conversations.filter((conv) =>
    conv.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.contact_phone.includes(searchTerm)
  );

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
          className="flex-shrink-0 p-2 hover:bg-gray-100 rounded-full transition-all active:scale-95"
          title="Nova conversa"
        >
          <Plus className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* Conversations */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="text-sm text-gray-500">Carregando...</div>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="text-gray-400 text-center">
              <p className="text-sm">Nenhuma conversa</p>
              <p className="text-xs mt-1">Inicie uma nova conversa para começar</p>
            </div>
          </div>
        ) : (
          filteredConversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setActiveConversation(conv)}
              className={`
                w-full flex items-start gap-2 sm:gap-3 px-3 sm:px-4 py-3 hover:bg-[#f0f2f5] transition-colors border-b border-gray-100
                ${activeConversation?.id === conv.id ? 'bg-[#f0f2f5]' : ''}
              `}
            >
              {/* Avatar com foto - responsivo */}
              <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-gray-200 overflow-hidden">
                {conv.profile_pic_url ? (
                  <img 
                    src={`/api/chat/conversations/profile-pic-proxy/?url=${encodeURIComponent(conv.profile_pic_url)}`}
                    alt={conv.contact_name || conv.contact_phone}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      // Fallback se imagem não carregar
                      e.currentTarget.style.display = 'none';
                      e.currentTarget.parentElement!.innerHTML = `
                        <div class="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                          ${(conv.contact_name || conv.contact_phone)[0].toUpperCase()}
                        </div>
                      `;
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-lg">
                    {(conv.contact_name || conv.contact_phone)[0].toUpperCase()}
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0 text-left">
                {/* Nome + Hora */}
                <div className="flex items-baseline justify-between mb-1">
                  <h3 className="font-medium text-gray-900 truncate text-sm">
                    {conv.contact_name || conv.contact_phone}
                  </h3>
                  <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                    {formatTime(conv.last_message_at)}
                  </span>
                </div>

                {/* Tags: Instância + Tags do Contato */}
                {(conv.instance_name || (conv.contact_tags && conv.contact_tags.length > 0)) && (
                  <div className="flex items-center gap-1 flex-wrap mb-1">
                    {/* Tag da Instância (azul) */}
                    {conv.instance_name && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px] font-medium">
                        📱 {conv.instance_name}
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
                    {conv.last_message?.content || 'Sem mensagens'}
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
