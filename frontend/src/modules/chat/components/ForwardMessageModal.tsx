/**
 * Modal para encaminhar mensagem para outra conversa ou contato
 */
import React, { useState, useEffect, useCallback } from 'react';
import { X, Search, MessageSquare, User } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import type { Message, Conversation } from '../types';

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

interface Contact {
  id: string;
  name: string;
  phone: string;
  tags?: Array<{ id: string; name: string; color: string }>;
}

type ForwardableItem = Conversation | Contact;

function isContact(item: ForwardableItem): item is Contact {
  return 'phone' in item && !('conversation_type' in item);
}

function isConversation(item: ForwardableItem): item is Conversation {
  return 'conversation_type' in item || 'status' in item;
}

interface ForwardMessageModalProps {
  message: Message;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ForwardMessageModal({ message, onClose, onSuccess }: ForwardMessageModalProps) {
  const { conversations, activeConversation, setActiveConversation, addConversation, activeDepartment } = useChatStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filteredItems, setFilteredItems] = useState<ForwardableItem[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [isSearchingContacts, setIsSearchingContacts] = useState(false);
  const [selectedItem, setSelectedItem] = useState<ForwardableItem | null>(null);
  const [sending, setSending] = useState(false);

  // Bloquear modal se mensagem foi apagada
  useEffect(() => {
    if (message?.is_deleted) {
      toast.error('Não é possível encaminhar uma mensagem que foi apagada');
      onClose();
    }
  }, [message?.is_deleted, onClose]);

  // Normalizar telefone (reutilizar lógica do NewConversationModal)
  const normalizePhone = useCallback((phone: string): string => {
    let clean = phone.replace(/[^\d+]/g, '');
    if (!clean.startsWith('+')) {
      if (clean.startsWith('55')) {
        clean = '+' + clean;
      } else {
        clean = '+55' + clean;
      }
    }
    return clean;
  }, []);

  const validatePhone = useCallback((phone: string): boolean => {
    if (!phone) return false;
    const normalized = normalizePhone(phone);
    return /^\+55\d{10,11}$/.test(normalized);
  }, [normalizePhone]);

  // Buscar contatos quando searchQuery muda (com debounce e fallback)
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) {
      setContacts([]);
      setIsSearchingContacts(false);
      return;
    }

    setIsSearchingContacts(true);
    const timeoutId = setTimeout(async () => {
      try {
        const response = await api.get('/contacts/contacts/', {
          params: { search: searchQuery, page_size: 10 }
        });
        const results = response.data.results || response.data || [];
        setContacts(Array.isArray(results) ? results : []);
      } catch (error) {
        // Fallback silencioso: se busca falhar, continuar só com conversas
        setContacts([]);
      } finally {
        setIsSearchingContacts(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Combinar conversas + contatos em lista filtrada
  useEffect(() => {
    if (!searchQuery.trim()) {
      // Sem busca: mostrar todas as conversas exceto a atual
      setFilteredItems(
        conversations.filter((conv) => conv.id !== activeConversation?.id)
      );
    } else {
      const query = searchQuery.toLowerCase();
      // Filtrar conversas
      const filteredConvs = conversations.filter((conv) => {
        if (conv.id === activeConversation?.id) return false;
        const name = (conv.contact_name || '').toLowerCase();
        const phone = (conv.contact_phone || '').toLowerCase();
        return name.includes(query) || phone.includes(query);
      });
      // Filtrar contatos (já filtrados pela API, mas garantir que não duplicam conversas existentes)
      const filteredContacts = contacts.filter((contact) => {
        // Não mostrar contato se já existe conversa com esse telefone
        const contactPhone = contact.phone.replace(/[^\d]/g, '');
        return !conversations.some((conv) => {
          const convPhone = (conv.contact_phone || '').replace(/[^\d]/g, '');
          return convPhone === contactPhone || convPhone === `55${contactPhone}` || `55${convPhone}` === contactPhone;
        });
      });
      // Combinar: conversas primeiro, depois contatos
      setFilteredItems([...filteredConvs, ...filteredContacts]);
    }
  }, [searchQuery, conversations, contacts, activeConversation]);

  const handleForward = async () => {
    if (!selectedItem || sending) return;

    try {
      setSending(true);

      let conversationId: string;
      let displayName: string;

      let destConversation: Conversation | null = null;

      // Se selecionado for CONTATO, criar conversa primeiro
      if (isContact(selectedItem)) {
        // Validação: verificar telefone válido antes de criar conversa
        if (!selectedItem.phone || !validatePhone(selectedItem.phone)) {
          toast.error('Telefone inválido. Verifique o número do contato.');
          return;
        }

        try {
          // Criar/iniciar conversa com o contato
          const departmentId = activeDepartment && activeDepartment.id !== 'inbox' && activeDepartment.id !== 'my_conversations' ? activeDepartment.id : undefined;
          const createResponse = await api.post('/chat/conversations/start/', {
            contact_phone: selectedItem.phone,
            contact_name: selectedItem.name,
            ...(departmentId && { department: departmentId })
          });
          destConversation = createResponse.data.conversation || createResponse.data;
          conversationId = destConversation.id;
          displayName = selectedItem.name || selectedItem.phone;
          addConversation(destConversation);
        } catch (createError: any) {
          const createErrorMsg = createError.response?.data?.error || createError.response?.data?.detail || createError.message || 'Erro ao criar conversa';
          toast.error(`Não foi possível criar conversa: ${createErrorMsg}`);
          return; // Não encaminhar se não conseguiu criar conversa
        }
      } else {
        // Se selecionado for CONVERSA, usar diretamente
        conversationId = selectedItem.id;
        displayName = selectedItem.contact_name || selectedItem.contact_phone;
        destConversation = selectedItem;
      }

      // Encaminhar mensagem para a conversa (criada ou existente)
      const { data } = await api.post<{
        status: string;
        conversation_id?: string;
        forwarded_message_id?: string;
      }>(`/chat/messages/${message.id}/forward/`, {
        conversation_id: conversationId
      });

      toast.success(`Mensagem encaminhada para ${displayName}`);

      // Se já temos a conversa (criada ou selecionada), usar diretamente
      // Caso contrário, buscar do backend usando conversation_id da resposta
      if (!destConversation) {
        const destId = data?.conversation_id || conversationId;
        destConversation = conversations.find((c) => String(c.id) === String(destId)) || null;
        if (!destConversation) {
          try {
            const res = await api.get(`/chat/conversations/${destId}/`);
            destConversation = res.data;
            addConversation(destConversation);
          } catch (err: any) {
            if (err?.response?.status === 404 || err?.response?.status === 403) {
              onSuccess?.();
              onClose();
              return;
            }
            // Outros erros: não abrir conversa
            onSuccess?.();
            onClose();
            return;
          }
        }
      }

      // Abrir a conversa de destino
      if (destConversation) {
        setActiveConversation(destConversation);
      }
      onSuccess?.();
      onClose();
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.response?.data?.detail || error.message || 'Erro ao encaminhar mensagem';
      toast.error(errorMsg);
    } finally {
      setSending(false);
    }
  };

  // Não renderizar se mensagem apagada (após todos os hooks)
  if (message?.is_deleted) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="forward-message-modal-title">
      <div
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 w-full max-w-md mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 id="forward-message-modal-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">Encaminhar Mensagem</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Preview da mensagem */}
        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Mensagem a encaminhar:</p>
          <div className="bg-white dark:bg-gray-700 rounded p-2 border border-gray-200 dark:border-gray-600">
            <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">
              {(() => {
                const c = message.content != null ? String(message.content) : '';
                const display =
                  c.trim() === '[button]' ? 'Resposta de botão' : c.trim() === '[templateMessage]' ? 'Mensagem de template' : c;
                return display || (message.attachments && message.attachments.length > 0 ? '📎 Anexo' : 'Mensagem');
              })()}
            </p>
          </div>
        </div>

        {/* Busca */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
            <input
              type="text"
              placeholder="Buscar conversa ou contato..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400"
            />
            {isSearchingContacts && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
              </div>
            )}
          </div>
        </div>

        {/* Lista de conversas e contatos */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {filteredItems.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <MessageSquare className="w-12 h-12 mx-auto mb-2 text-gray-300 dark:text-gray-500" />
              <p>{searchQuery.trim() ? 'Nenhuma conversa ou contato encontrado' : 'Nenhuma conversa disponível'}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredItems.map((item) => {
                const isConv = isConversation(item);
                const isSelected = selectedItem && (
                  (isConv && isConversation(selectedItem) && selectedItem.id === item.id) ||
                  (!isConv && isContact(selectedItem) && selectedItem.id === item.id)
                );
                const displayName = isConv ? (item.contact_name || item.contact_phone) : item.name;
                const displayPhone = isConv ? item.contact_phone : item.phone;

                return (
                  <button
                    key={isConv ? item.id : `contact-${item.id}`}
                    onClick={() => setSelectedItem(item)}
                    className={`
                      w-full text-left p-3 rounded-lg border transition-all flex items-center gap-3
                      ${isSelected
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
                      }
                    `}
                  >
                    {/* Avatar */}
                    {isConv && item.profile_pic_url ? (
                      <img
                        src={getMediaProxyUrl(item.profile_pic_url)}
                        alt={displayName}
                        className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center flex-shrink-0">
                        {isConv ? (
                          <MessageSquare className="w-5 h-5 text-gray-400 dark:text-gray-500" />
                        ) : (
                          <User className="w-5 h-5 text-gray-400 dark:text-gray-500" />
                        )}
                      </div>
                    )}
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100 truncate">
                          {displayName}
                        </p>
                        <span className={`
                          text-xs px-1.5 py-0.5 rounded
                          ${isConv 
                            ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                          }
                        `}>
                          {isConv ? 'Conversa' : 'Contato'}
                        </span>
                      </div>
                      {displayPhone && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 truncate">{displayPhone}</p>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 dark:border-gray-600 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            disabled={sending}
          >
            Cancelar
          </button>
          <button
            onClick={handleForward}
            disabled={!selectedItem || sending}
            className={`
              px-4 py-2 rounded-lg transition-colors
              ${selectedItem && !sending
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
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

