/**
 * Lista de conversas (sidebar esquerda)
 */
import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Conversation } from '../types';
import { Loader2, Search, MessageCircle, Plus } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from 'sonner';

export function ConversationList() {
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewChatModal, setShowNewChatModal] = useState(false);
  const [newChatPhone, setNewChatPhone] = useState('');
  const [newChatName, setNewChatName] = useState('');
  const [creating, setCreating] = useState(false);
  
  // Busca de contatos
  const [contactSearchMode, setContactSearchMode] = useState<'manual' | 'search'>('search');
  const [contactSearch, setContactSearch] = useState('');
  const [contacts, setContacts] = useState<any[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [selectedContact, setSelectedContact] = useState<any>(null);
  
  const {
    activeDepartment,
    conversations,
    activeConversation,
    setConversations,
    setActiveConversation
  } = useChatStore();
  
  // Buscar contatos do tenant
  const fetchContacts = async (search: string) => {
    if (!search || search.length < 2) {
      setContacts([]);
      return;
    }
    
    try {
      setLoadingContacts(true);
      const response = await api.get('/contacts/contacts/', {
        params: {
          search,
          page_size: 10
        }
      });
      setContacts(response.data.results || response.data);
    } catch (error) {
      console.error('Erro ao buscar contatos:', error);
      setContacts([]);
    } finally {
      setLoadingContacts(false);
    }
  };
  
  // Debounce na busca
  useEffect(() => {
    if (contactSearchMode === 'search') {
      const timer = setTimeout(() => {
        fetchContacts(contactSearch);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [contactSearch, contactSearchMode]);

  useEffect(() => {
    if (!activeDepartment) return;

    const fetchConversations = async () => {
      try {
        setLoading(true);
        
        // Parâmetros de filtro
        const params: any = {
          ordering: '-last_message_at'
        };
        
        // Se Inbox, filtrar por status=pending
        if (activeDepartment.id === 'inbox') {
          params.status = 'pending';
        } else {
          // Se departamento normal, filtrar por department
          params.department = activeDepartment.id;
        }
        
        const response = await api.get('/chat/conversations/', { params });
        
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

  const handleStartNewChat = async () => {
    let phone = '';
    let name = '';
    
    if (contactSearchMode === 'search' && selectedContact) {
      phone = selectedContact.phone;
      name = selectedContact.name || selectedContact.phone;
    } else {
      phone = newChatPhone.trim();
      name = newChatName.trim();
    }
    
    if (!phone) {
      toast.error('Selecione um contato ou digite um telefone');
      return;
    }

    try {
      setCreating(true);
      const response = await api.post('/chat/conversations/start/', {
        contact_phone: phone,
        contact_name: name,
        department: activeDepartment?.id
      });

      toast.success(response.data.message || 'Conversa iniciada!');
      
      // Resetar form
      setShowNewChatModal(false);
      setNewChatPhone('');
      setNewChatName('');
      setContactSearch('');
      setSelectedContact(null);
      setContacts([]);

      // Recarregar conversas
      const convResponse = await api.get('/chat/conversations/', {
        params: {
          department: activeDepartment?.id,
          ordering: '-last_message_at'
        }
      });
      const convs = convResponse.data.results || convResponse.data;
      setConversations(convs);

      // Selecionar a nova conversa
      const newConv = response.data.conversation;
      if (newConv) {
        setActiveConversation(newConv);
      }
    } catch (error: any) {
      console.error('Erro ao iniciar conversa:', error);
      toast.error(error.response?.data?.error || 'Erro ao iniciar conversa');
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#141a20] border-r border-gray-800">
        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
        <p className="mt-2 text-sm text-gray-500">Carregando conversas...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full md:w-96 lg:w-[420px] bg-[#141a20] border-r border-gray-800">
      {/* Header com busca e botão Nova Conversa */}
      <div className="p-4 border-b border-gray-800 space-y-3">
        <button
          onClick={() => setShowNewChatModal(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors font-medium"
        >
          <Plus className="w-4 h-4" />
          Nova Conversa
        </button>
        
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

      {/* Modal Nova Conversa */}
      {showNewChatModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-[#1f262e] rounded-xl shadow-2xl w-full max-w-md border border-gray-800">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
              <h2 className="text-lg font-semibold text-white">Nova Conversa</h2>
              <button
                onClick={() => {
                  setShowNewChatModal(false);
                  setNewChatPhone('');
                  setNewChatName('');
                }}
                className="p-1 hover:bg-gray-700 rounded transition-colors"
              >
                <Plus className="w-5 h-5 text-gray-400 rotate-45" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Tabs: Buscar / Manual */}
              <div className="flex gap-2 border-b border-gray-700 pb-2">
                <button
                  onClick={() => {
                    setContactSearchMode('search');
                    setNewChatPhone('');
                    setNewChatName('');
                  }}
                  className={`px-4 py-2 rounded-t-lg transition-colors ${
                    contactSearchMode === 'search'
                      ? 'bg-green-600 text-white'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <Search className="w-4 h-4 inline-block mr-2" />
                  Buscar Contato
                </button>
                <button
                  onClick={() => {
                    setContactSearchMode('manual');
                    setContactSearch('');
                    setSelectedContact(null);
                    setContacts([]);
                  }}
                  className={`px-4 py-2 rounded-t-lg transition-colors ${
                    contactSearchMode === 'manual'
                      ? 'bg-green-600 text-white'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <Plus className="w-4 h-4 inline-block mr-2" />
                  Digitar Número
                </button>
              </div>

              {/* Modo: Buscar Contato */}
              {contactSearchMode === 'search' && (
                <div className="space-y-3">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                      type="text"
                      value={contactSearch}
                      onChange={(e) => setContactSearch(e.target.value)}
                      placeholder="Buscar por nome ou telefone..."
                      className="w-full pl-10 pr-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-600"
                    />
                    {loadingContacts && (
                      <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-gray-500" />
                    )}
                  </div>

                  {/* Lista de resultados */}
                  {contacts.length > 0 && (
                    <div className="max-h-48 overflow-y-auto space-y-2 border border-gray-700 rounded-lg p-2">
                      {contacts.map((contact) => (
                        <div
                          key={contact.id}
                          onClick={() => setSelectedContact(contact)}
                          className={`p-3 rounded-lg cursor-pointer transition-colors ${
                            selectedContact?.id === contact.id
                              ? 'bg-green-600 text-white'
                              : 'bg-gray-700 hover:bg-gray-600 text-gray-100'
                          }`}
                        >
                          <div className="font-medium">{contact.name || 'Sem nome'}</div>
                          <div className="text-sm opacity-80">{contact.phone}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {contactSearch.length >= 2 && contacts.length === 0 && !loadingContacts && (
                    <p className="text-sm text-gray-400 text-center py-4">
                      Nenhum contato encontrado
                    </p>
                  )}

                  {selectedContact && (
                    <div className="p-3 bg-green-600/20 border border-green-600 rounded-lg">
                      <p className="text-sm text-gray-300">Selecionado:</p>
                      <p className="text-white font-medium">{selectedContact.name || 'Sem nome'}</p>
                      <p className="text-sm text-gray-400">{selectedContact.phone}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Modo: Digitar Manual */}
              {contactSearchMode === 'manual' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Telefone (obrigatório)
                    </label>
                    <input
                      type="text"
                      value={newChatPhone}
                      onChange={(e) => setNewChatPhone(e.target.value)}
                      placeholder="+5517999999999"
                      className="w-full px-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-600"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Formato: +55 DDD NÚMERO
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Nome (opcional)
                    </label>
                    <input
                      type="text"
                      value={newChatName}
                      onChange={(e) => setNewChatName(e.target.value)}
                      placeholder="João Silva"
                      className="w-full px-4 py-2 bg-[#2b2f36] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-green-600"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800">
              <button
                onClick={() => {
                  setShowNewChatModal(false);
                  setNewChatPhone('');
                  setNewChatName('');
                }}
                disabled={creating}
                className="px-4 py-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-300 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleStartNewChat}
                disabled={
                  creating ||
                  (contactSearchMode === 'search' && !selectedContact) ||
                  (contactSearchMode === 'manual' && !newChatPhone.trim())
                }
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Criando...</span>
                  </>
                ) : (
                  <>
                    <MessageCircle className="w-4 h-4" />
                    <span>Iniciar Conversa</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
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

