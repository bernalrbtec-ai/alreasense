/**
 * Lista de conversas (sidebar esquerda)
 */
import React, { useEffect, useState } from 'react';
import api from '@/utils/api';
import { useChatStore } from '../store/chatStore';
import { Conversation } from '../types';
import { Loader2, Search, MessageCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

export function ConversationList() {
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  const {
    activeDepartment,
    conversations,
    activeConversation,
    setConversations,
    setActiveConversation
  } = useChatStore();

  useEffect(() => {
    if (!activeDepartment) return;

    const fetchConversations = async () => {
      try {
        setLoading(true);
        const response = await api.get('/api/chat/conversations/', {
          params: {
            department: activeDepartment.id,
            ordering: '-last_message_at'
          }
        });
        
        const convs = response.data.results || response.data;
        setConversations(convs);
        
        console.log('✅ Conversas carregadas:', convs.length);
      } catch (error) {
        console.error('❌ Erro ao carregar conversas:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, [activeDepartment, setConversations]);

  const filteredConversations = conversations.filter(conv => {
    const searchLower = searchQuery.toLowerCase();
    return (
      conv.contact_name?.toLowerCase().includes(searchLower) ||
      conv.contact_phone.includes(searchLower)
    );
  });

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#141a20] border-r border-gray-800">
        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
        <p className="mt-2 text-sm text-gray-500">Carregando conversas...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-80 bg-[#141a20] border-r border-gray-800">
      {/* Header com busca */}
      <div className="p-4 border-b border-gray-800">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Buscar conversa..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[#1f262e] border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-600"
          />
        </div>
      </div>

      {/* Lista de conversas */}
      <div className="flex-1 overflow-y-auto">
        {filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center">
            <MessageCircle className="w-12 h-12 text-gray-600 mb-3" />
            <p className="text-sm text-gray-500">
              {searchQuery ? 'Nenhuma conversa encontrada' : 'Nenhuma conversa ainda'}
            </p>
          </div>
        ) : (
          filteredConversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              isActive={activeConversation?.id === conv.id}
              onClick={() => setActiveConversation(conv)}
            />
          ))
        )}
      </div>
    </div>
  );
}

interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onClick: () => void;
}

function ConversationItem({ conversation, isActive, onClick }: ConversationItemProps) {
  const getTimeAgo = (dateString?: string) => {
    if (!dateString) return '';
    try {
      return formatDistanceToNow(new Date(dateString), {
        addSuffix: true,
        locale: ptBR
      });
    } catch {
      return '';
    }
  };

  const lastMessagePreview = conversation.last_message?.content || 'Sem mensagens';
  const truncatedPreview = lastMessagePreview.length > 50 
    ? lastMessagePreview.substring(0, 50) + '...' 
    : lastMessagePreview;

  return (
    <div
      onClick={onClick}
      className={`
        p-4 cursor-pointer border-b border-gray-800 transition-colors
        ${isActive ? 'bg-[#2f7d32]' : 'hover:bg-[#1f262e]'}
      `}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-green-600 to-green-700 flex items-center justify-center text-white font-semibold">
          {(conversation.contact_name || conversation.contact_phone)[0].toUpperCase()}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h3 className={`font-medium truncate ${isActive ? 'text-white' : 'text-gray-200'}`}>
              {conversation.contact_name || conversation.contact_phone}
            </h3>
            
            {conversation.last_message_at && (
              <span className={`text-xs flex-shrink-0 ml-2 ${isActive ? 'text-gray-200' : 'text-gray-500'}`}>
                {getTimeAgo(conversation.last_message_at)}
              </span>
            )}
          </div>

          <div className="flex items-center justify-between gap-2">
            <p className={`text-sm truncate ${isActive ? 'text-gray-200' : 'text-gray-400'}`}>
              {truncatedPreview}
            </p>
            
            {conversation.unread_count > 0 && (
              <span className="flex-shrink-0 px-2 py-0.5 bg-green-600 text-white text-xs font-semibold rounded-full">
                {conversation.unread_count}
              </span>
            )}
          </div>

          {/* Agente atribuído */}
          {conversation.assigned_to_data && (
            <p className={`text-xs mt-1 ${isActive ? 'text-gray-300' : 'text-gray-500'}`}>
              📍 {conversation.assigned_to_data.first_name || conversation.assigned_to_data.email}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

