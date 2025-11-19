/**
 * Modal para encaminhar mensagem para outra conversa
 */
import React, { useState, useEffect } from 'react';
import { X, Search, MessageSquare } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import type { Message, Conversation } from '../types';

interface ForwardMessageModalProps {
  message: Message;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ForwardMessageModal({ message, onClose, onSuccess }: ForwardMessageModalProps) {
  const { conversations, activeConversation } = useChatStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredConversations, setFilteredConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [sending, setSending] = useState(false);

  // Filtrar conversas baseado na busca
  useEffect(() => {
    if (!searchQuery.trim()) {
      // Mostrar todas as conversas exceto a atual
      setFilteredConversations(
        conversations.filter(c => c.id !== activeConversation?.id)
      );
    } else {
      const query = searchQuery.toLowerCase();
      setFilteredConversations(
        conversations.filter(c => {
          if (c.id === activeConversation?.id) return false;
          const name = (c.contact_name || '').toLowerCase();
          const phone = (c.contact_phone || '').toLowerCase();
          return name.includes(query) || phone.includes(query);
        })
      );
    }
  }, [searchQuery, conversations, activeConversation]);

  const handleForward = async () => {
    if (!selectedConversation || sending) return;

    try {
      setSending(true);

      // Criar nova mensagem na conversa selecionada via REST API
      const payload: any = {
        conversation: selectedConversation.id,
        content: message.content,
        direction: 'outgoing',
        is_internal: false
      };

      // Se a mensagem original tinha anexos, encaminhar também
      if (message.attachments && message.attachments.length > 0) {
        payload.metadata = {
          attachment_urls: message.attachments.map(att => att.file_url).filter(Boolean),
          forwarded_from: message.id,
          forwarded_at: new Date().toISOString()
        };
      } else {
        payload.metadata = {
          forwarded_from: message.id,
          forwarded_at: new Date().toISOString()
        };
      }

      await api.post('/chat/messages/', payload);

      toast.success(`Mensagem encaminhada para ${selectedConversation.contact_name || selectedConversation.contact_phone}`);
      onSuccess?.();
      onClose();
    } catch (error: any) {
      console.error('❌ Erro ao encaminhar mensagem:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao encaminhar mensagem';
      toast.error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-md mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Encaminhar Mensagem</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Preview da mensagem */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Mensagem a encaminhar:</p>
          <div className="bg-white rounded p-2 border border-gray-200">
            <p className="text-sm text-gray-700 line-clamp-2">
              {message.content || (message.attachments && message.attachments.length > 0 ? '📎 Anexo' : 'Mensagem')}
            </p>
          </div>
        </div>

        {/* Busca */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar conversa..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {filteredConversations.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <MessageSquare className="w-12 h-12 mx-auto mb-2 text-gray-300" />
              <p>Nenhuma conversa encontrada</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredConversations.map((conversation) => (
                <button
                  key={conversation.id}
                  onClick={() => setSelectedConversation(conversation)}
                  className={`
                    w-full text-left p-3 rounded-lg border transition-all
                    ${selectedConversation?.id === conversation.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:bg-gray-50'
                    }
                  `}
                >
                  <p className="font-medium text-gray-900">
                    {conversation.contact_name || conversation.contact_phone}
                  </p>
                  {conversation.contact_name && (
                    <p className="text-sm text-gray-500">{conversation.contact_phone}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            disabled={sending}
          >
            Cancelar
          </button>
          <button
            onClick={handleForward}
            disabled={!selectedConversation || sending}
            className={`
              px-4 py-2 rounded-lg transition-colors
              ${selectedConversation && !sending
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }
            `}
          >
            {sending ? 'Encaminhando...' : 'Encaminhar'}
          </button>
        </div>
      </div>
    </div>
  );
}

