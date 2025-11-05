/**
 * Zustand Store para o Flow Chat
 */
import { create } from 'zustand';
import { Conversation, Message, Department } from '../types';

interface ChatState {
  // Departamentos
  departments: Department[];
  activeDepartment: Department | null;
  setDepartments: (departments: Department[]) => void;
  setActiveDepartment: (department: Department | null) => void;

  // Conversas
  conversations: Conversation[];
  activeConversation: Conversation | null;
  setConversations: (conversations: Conversation[]) => void;
  setActiveConversation: (conversation: Conversation | null) => void;
  addConversation: (conversation: Conversation) => void;
  updateConversation: (conversation: Conversation) => void;
  removeConversation: (conversationId: string) => void;

  // Mensagens
  messages: Message[];
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessageStatus: (messageId: string, status: string) => void;
  updateAttachment: (attachmentId: string, updates: Partial<Message['attachments'][number]>) => void;

  // Estado do chat
  typing: boolean;
  typingUser: string | null;
  setTyping: (typing: boolean, user?: string) => void;

  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  setConnectionStatus: (status: 'connecting' | 'connected' | 'disconnected') => void;

  // Reset
  reset: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  // State inicial
  departments: [],
  activeDepartment: null,
  conversations: [],
  activeConversation: null,
  messages: [],
  typing: false,
  typingUser: null,
  connectionStatus: 'disconnected',

  // Departamentos
  setDepartments: (departments) => set({ departments }),
  setActiveDepartment: (department) => set({ activeDepartment: department }),

  // Conversas
  setConversations: (conversations) => set({ conversations }),
  setActiveConversation: (conversation) => set((state) => {
    // ✅ FIX: Se conversation é null ou undefined, limpar
    if (!conversation) {
      console.log('🔕 [STORE] Limpando conversa ativa');
      return {
        activeConversation: null,
        messages: []
      };
    }
    
    // ✅ FIX: Se já é a mesma conversa, não fazer nada (evita resetar mensagens e referencia)
    if (state.activeConversation?.id === conversation.id) {
      console.log('🔕 [STORE] Conversa já está ativa, mantendo:', conversation.id);
      return state; // Retornar state atual sem mudanças
    }
    
    console.log('✅ [STORE] Definindo conversa ativa:', conversation.id, '| Antiga:', state.activeConversation?.id || 'nenhuma');
    return {
      activeConversation: conversation,
      messages: [] // Limpa mensagens ao trocar conversa
    };
  }),
  addConversation: (conversation) => set((state) => {
    // ✅ IMPORTANTE: Garantir que conversation tem os campos necessários
    if (!conversation || !conversation.id) {
      console.error('❌ [STORE] Tentativa de adicionar conversa inválida:', conversation);
      return state;
    }
    
    // Evitar duplicatas
    const exists = state.conversations.some(c => c.id === conversation.id);
    if (exists) {
      console.log('⚠️ [STORE] Conversa duplicada, ignorando:', conversation.contact_name || conversation.contact_phone);
      // ✅ MAS: Atualizar conversa existente se dados novos foram recebidos
      const updatedConversations = state.conversations.map(c => 
        c.id === conversation.id ? conversation : c
      );
      
      // ✅ FIX: Ordenar por last_message_at após atualizar
      const sortedConversations = [...updatedConversations].sort((a, b) => {
        const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
        const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
        return bTime - aTime; // Mais recente primeiro
      });
      
      return {
        conversations: sortedConversations
      };
    }
    
    // ✅ IMPORTANTE: Garantir que conversation tem status (default 'pending' se não tiver)
    const conversationWithStatus = {
      ...conversation,
      status: conversation.status || 'pending'
    };
    
    // Adicionar no início da lista (conversas mais recentes primeiro)
    const newConversations = [conversationWithStatus, ...state.conversations];
    
    // ✅ FIX: Ordenar por last_message_at para garantir ordem correta
    const sortedConversations = [...newConversations].sort((a, b) => {
      const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
      const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      return bTime - aTime; // Mais recente primeiro
    });
    
    console.log('✅ [STORE] Nova conversa adicionada:', conversation.contact_name || conversation.contact_phone);
    console.log(`   Total de conversas: ${state.conversations.length} → ${sortedConversations.length}`);
    console.log(`   Status: ${conversationWithStatus.status}, Department: ${conversationWithStatus.department || 'null'}`);
    console.log(`   ID: ${conversationWithStatus.id}`);
    console.log(`   ✅ STORE ATUALIZADO - Nova lista:`, sortedConversations.map(c => ({
      id: c.id,
      name: c.contact_name || c.contact_phone,
      status: c.status,
      department: c.department || null,
      last_message_at: c.last_message_at
    })));
    
    return {
      conversations: sortedConversations
    };
  }),
  updateConversation: (conversation) => set((state) => {
    // ✅ IMPORTANTE: Garantir que conversation tem os campos necessários
    if (!conversation || !conversation.id) {
      console.error('❌ [STORE] Tentativa de atualizar conversa inválida:', conversation);
      return state;
    }
    
    // ✅ FIX: Log detalhado para debug
    const existingConv = state.conversations.find(c => c.id === conversation.id);
    console.log('🔄 [STORE] Atualizando conversa:', {
      id: conversation.id,
      contact: conversation.contact_name || conversation.contact_phone,
      oldDepartment: existingConv?.department || null,
      newDepartment: conversation.department || null,
      oldStatus: existingConv?.status || null,
      newStatus: conversation.status || null,
      oldUnreadCount: existingConv?.unread_count || 0,
      newUnreadCount: conversation.unread_count || 0,
      departmentName: conversation.department_name || null
    });
    
    // ✅ FIX: Se conversa não existe no store, adicionar (pode acontecer em race conditions)
    const exists = state.conversations.some(c => c.id === conversation.id);
    if (!exists) {
      console.log('⚠️ [STORE] Conversa não encontrada no store, adicionando...');
      return {
        conversations: [...state.conversations, conversation]
        // ✅ FIX: NÃO definir automaticamente como ativa - usuário deve escolher qual abrir
        // activeConversation: state.activeConversation || conversation  // ❌ REMOVIDO
      };
    }
    
    // ✅ FIX CRÍTICO: Fazer merge completo para garantir que unread_count e outros campos sejam atualizados
    const updatedConversations = state.conversations.map(c => {
      if (c.id === conversation.id) {
        // ✅ FIX: Merge completo para garantir que todos os campos sejam atualizados
        const updated = {
          ...c,
          ...conversation,  // Sobrescrever com dados atualizados (inclui unread_count e last_message_at)
          // Preservar mensagens existentes (não sobrescrever com mensagens vazias)
          messages: c.messages && c.messages.length > 0 ? c.messages : (conversation.messages || [])
        };
        console.log(`   🔄 [STORE] Conversa ${c.id} atualizada: unread_count ${c.unread_count || 0} → ${updated.unread_count || 0}`);
        return updated;
      }
      return c;
    });
    
    // ✅ FIX CRÍTICO: Ordenar conversas por last_message_at (mais recente primeiro)
    // Quando uma nova mensagem chega, a conversa deve ir para o topo
    const sortedConversations = [...updatedConversations].sort((a, b) => {
      const aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
      const bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      return bTime - aTime; // Mais recente primeiro (decrescente)
    });
    
    // ✅ FIX CRÍTICO: Atualizar conversa ativa também para garantir que unread_count seja atualizado
    const updatedActiveConversation = state.activeConversation?.id === conversation.id 
      ? {
          ...state.activeConversation,
          ...conversation,  // ✅ FIX: Atualizar todos os campos incluindo unread_count
          // Preservar mensagens existentes
          messages: state.activeConversation.messages && state.activeConversation.messages.length > 0 
            ? state.activeConversation.messages 
            : (conversation.messages || [])
        }
      : state.activeConversation;
    
    console.log('   ✅ STORE ATUALIZADO - Conversas:', sortedConversations.map(c => ({
      id: c.id,
      name: c.contact_name || c.contact_phone,
      status: c.status,
      department: c.department || null,
      departmentName: c.department_name || null,
      unread_count: c.unread_count || 0,
      last_message_at: c.last_message_at
    })));
    
    return {
      conversations: sortedConversations,  // ✅ FIX: Retornar lista ordenada
      activeConversation: updatedActiveConversation
    };
  }),
  removeConversation: (conversationId) => set((state) => ({
    conversations: state.conversations.filter(c => c.id !== conversationId),
    // Se a conversa removida era a ativa, limpar
    activeConversation: state.activeConversation?.id === conversationId 
      ? null 
      : state.activeConversation
  })),

  // Mensagens
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => {
    // ✅ FIX CRÍTICO: Verificar se mensagem pertence à conversa ativa
    // Se não houver conversa ativa ou a mensagem não pertence à conversa ativa, NÃO adicionar
    if (!state.activeConversation) {
      console.log('⚠️ [STORE] Nenhuma conversa ativa, ignorando mensagem:', message.id);
      return state;
    }
    
    // ✅ FIX: Comparar conversation_id da mensagem com a conversa ativa
    // O campo pode ser 'conversation' (UUID) ou 'conversation_id' (string)
    const messageConversationId = message.conversation 
      ? String(message.conversation) 
      : (message.conversation_id ? String(message.conversation_id) : null);
    const activeConversationId = state.activeConversation.id ? String(state.activeConversation.id) : null;
    
    console.log('🔍 [STORE] Verificando se mensagem pertence à conversa ativa:', {
      messageId: message.id,
      messageConversationId,
      activeConversationId,
      messageConversation: message.conversation,
      messageConversationIdField: message.conversation_id,
      match: messageConversationId === activeConversationId
    });
    
    if (messageConversationId !== activeConversationId) {
      console.log('⚠️ [STORE] Mensagem não pertence à conversa ativa, ignorando:', {
        messageId: message.id,
        messageConversationId,
        activeConversationId,
        messageContent: message.content?.substring(0, 50)
      });
      return state; // Não adicionar mensagem se não for da conversa ativa
    }
    
    console.log('✅ [STORE] Mensagem pertence à conversa ativa, adicionando:', message.id);
    
    // Evitar duplicatas: verificar se mensagem já existe
    const exists = state.messages.some(m => m.id === message.id);
    if (exists) {
      // ✅ MELHORIA: Merge inteligente de attachments - preservar attachments atualizados
      return {
        messages: state.messages.map(m => {
          if (m.id === message.id) {
            // Fazer merge inteligente de attachments
            if (m.attachments && m.attachments.length > 0 && message.attachments && message.attachments.length > 0) {
              // ✅ MERGE: Preservar attachments existentes que estão atualizados (com file_url)
              // e usar novos attachments apenas se não existirem ou estiverem desatualizados
              const mergedAttachments = m.attachments.map(existingAtt => {
                const newAtt = message.attachments.find(a => a.id === existingAtt.id);
                if (newAtt) {
                  // Se attachment existente tem file_url válido e novo não tem, manter o existente
                  const existingHasUrl = existingAtt.file_url && existingAtt.file_url.trim() && 
                                        !existingAtt.file_url.includes('whatsapp.net') &&
                                        !existingAtt.file_url.includes('evo.');
                  const newHasUrl = newAtt.file_url && newAtt.file_url.trim() &&
                                   !newAtt.file_url.includes('whatsapp.net') &&
                                   !newAtt.file_url.includes('evo.');
                  
                  // ✅ FIX: Priorizar attachment com URL válida OU mais recente (timestamp-based)
                  if (existingHasUrl && !newHasUrl) {
                    return existingAtt; // Manter attachment atualizado
                  }
                  if (newHasUrl && !existingHasUrl) {
                    return newAtt; // Usar novo que tem URL válida
                  }
                  // Ambos têm ou não têm URL - usar o mais recente (timestamp-based merge)
                  const existingTime = existingAtt.created_at ? new Date(existingAtt.created_at).getTime() : 0;
                  const newTime = newAtt.created_at ? new Date(newAtt.created_at).getTime() : 0;
                  return newTime > existingTime ? newAtt : existingAtt;
                }
                return existingAtt; // Manter attachment que não existe na nova mensagem
              });
              
              // Adicionar novos attachments que não existem
              const newAttachmentIds = new Set(mergedAttachments.map(a => a.id));
              message.attachments.forEach(newAtt => {
                if (!newAttachmentIds.has(newAtt.id)) {
                  mergedAttachments.push(newAtt);
                }
              });
              
              return { ...message, attachments: mergedAttachments };
            }
            
            // Se a mensagem nova tem attachments mas a antiga não, usar os novos
            if (message.attachments && message.attachments.length > 0) {
              return message;
            }
            // Se a mensagem nova não tem attachments mas a antiga tem, preservar os da antiga
            if (m.attachments && m.attachments.length > 0) {
              return { ...message, attachments: m.attachments };
            }
            // Caso contrário, usar a mensagem nova
            return message;
          }
          return m;
        })
      };
    }
    // ✅ FIX: Ordenar mensagens por timestamp antes de adicionar
    // Isso garante que mensagens fora de ordem via WebSocket sejam ordenadas corretamente
    const newMessages = [...state.messages, message].sort((a, b) => {
      const timeA = new Date(a.created_at).getTime();
      const timeB = new Date(b.created_at).getTime();
      return timeA - timeB; // Mais antiga primeiro
    });
    
    return {
      messages: newMessages
    };
  }),
  updateMessageStatus: (messageId, status) => set((state) => ({
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, status: status as any } : m
    )
  })),
  updateAttachment: (attachmentId, updates) => set((state) => ({
    messages: state.messages.map(m => {
      if (!m.attachments || m.attachments.length === 0) return m;
      const idx = m.attachments.findIndex(a => a.id === attachmentId);
      if (idx === -1) return m;
      const updatedAttachments = [...m.attachments];
      updatedAttachments[idx] = { ...updatedAttachments[idx], ...updates } as any;
      return { ...m, attachments: updatedAttachments } as any;
    })
  })),

  // Estado do chat
  setTyping: (typing, user) => set({ typing, typingUser: user || null }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  // Reset
  reset: () => set({
    departments: [],
    activeDepartment: null,
    conversations: [],
    activeConversation: null,
    messages: [],
    typing: false,
    typingUser: null,
    connectionStatus: 'disconnected'
  })
}));

