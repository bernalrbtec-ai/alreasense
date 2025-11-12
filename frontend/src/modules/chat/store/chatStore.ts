/**
 * Zustand Store para o Flow Chat
 */
import { create } from 'zustand';
import { Conversation, Message, Department } from '../types';
import { upsertConversation } from './conversationUpdater';

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
  updateMessageReactions: (
    messageId: string,
    reactions: Message['reactions'],
    summary: Message['reactions_summary']
  ) => void;
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
    // ✅ MELHORIA: Usar função unificada upsertConversation
    const updatedConversations = upsertConversation(state.conversations, conversation);
    
    // ✅ Atualizar conversa ativa se for a mesma
    const updatedActiveConversation = state.activeConversation?.id === conversation.id
      ? {
          ...state.activeConversation,
          ...conversation
        }
      : state.activeConversation;
    
    return {
      conversations: updatedConversations,
      activeConversation: updatedActiveConversation
    };
  }),
  updateConversation: (conversation) => set((state) => {
    // ✅ MELHORIA: Usar função unificada upsertConversation (mesma lógica de addConversation)
    const updatedConversations = upsertConversation(state.conversations, conversation);
    
    // ✅ Atualizar conversa ativa também para garantir que unread_count seja atualizado
    const updatedActiveConversation = state.activeConversation?.id === conversation.id 
      ? {
          ...state.activeConversation,
          ...conversation
        }
      : state.activeConversation;
    
    return {
      conversations: updatedConversations,
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
    
    // ✅ FIX CRÍTICO: Comparar conversation_id da mensagem com a conversa ativa
    // O campo pode ser 'conversation' (UUID objeto ou string) ou 'conversation_id' (string)
    // Precisamos normalizar para string para comparação correta
    let messageConversationId: string | null = null;
    
    // ✅ FIX: Verificar se conversation_id existe primeiro (mais confiável)
    if (message.conversation_id) {
      messageConversationId = String(message.conversation_id);
    } else if (message.conversation) {
      // Se é objeto UUID, extrair o id ou converter para string
      if (typeof message.conversation === 'object' && message.conversation.id) {
        messageConversationId = String(message.conversation.id);
      } else if (typeof message.conversation === 'string') {
        // ✅ FIX: Verificar se é UUID válido (não é nome da conversa)
        // UUIDs têm formato: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (uuidRegex.test(message.conversation)) {
          messageConversationId = message.conversation;
        } else {
          // Se não é UUID, é provavelmente o nome da conversa - ignorar
          console.warn('⚠️ [STORE] conversation é string mas não é UUID (provavelmente nome):', message.conversation);
          messageConversationId = null;
        }
      } else {
        messageConversationId = String(message.conversation);
      }
    }
    
    const activeConversationId = state.activeConversation.id ? String(state.activeConversation.id) : null;
    
    console.log('🔍 [STORE] Verificando se mensagem pertence à conversa ativa:', {
      messageId: message.id,
      messageConversationId,
      activeConversationId,
      messageConversation: message.conversation,
      messageConversationType: typeof message.conversation,
      messageConversationIdField: message.conversation_id,
      activeConversationIdType: typeof state.activeConversation.id,
      match: messageConversationId === activeConversationId,
      messageContent: message.content?.substring(0, 50)
    });
    
    // ✅ FIX CRÍTICO: NUNCA adicionar mensagens sem conversation_id válido
    // Isso previne mensagens de outras conversas aparecerem na conversa ativa
    if (!messageConversationId) {
      console.warn('⚠️ [STORE] Mensagem sem conversation_id válido, ignorando:', {
        messageId: message.id,
        direction: message.direction,
        conversation: message.conversation,
        conversation_id: message.conversation_id,
        messageContent: message.content?.substring(0, 50)
      });
      return state; // Não adicionar mensagem sem conversation_id válido
    }
    
    // ✅ FIX CRÍTICO: NUNCA adicionar mensagens que não pertencem à conversa ativa
    // Isso previne mensagens de outras conversas (incluindo WhatsApp Web) aparecerem na conversa errada
    if (messageConversationId !== activeConversationId) {
      console.log('⚠️ [STORE] Mensagem não pertence à conversa ativa, ignorando:', {
        messageId: message.id,
        messageConversationId,
        activeConversationId,
        direction: message.direction,
        messageContent: message.content?.substring(0, 50),
        typeMismatch: typeof messageConversationId !== typeof activeConversationId
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
        // ✅ Ordenar após atualizar (garantir ordem correta - mais antigas primeiro)
        .sort((a, b) => {
          const timeA = new Date(a.created_at).getTime();
          const timeB = new Date(b.created_at).getTime();
          return timeA - timeB; // Mais antiga primeiro (timeA - timeB)
        })
      };
    }
    // ✅ FIX: Ordenar mensagens por timestamp antes de adicionar
    // Isso garante que mensagens fora de ordem via WebSocket sejam ordenadas corretamente
    const newMessages = [...state.messages, message].sort((a, b) => {
      const timeA = new Date(a.created_at).getTime();
      const timeB = new Date(b.created_at).getTime();
      return timeA - timeB; // Mais antiga primeiro (timeA - timeB)
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
  updateMessageReactions: (messageId, reactions, summary) => set((state) => {
    const updatedMessages = state.messages.map((m) =>
      m.id === messageId
        ? {
            ...m,
            reactions: reactions ? [...reactions] : [],
            reactions_summary: summary ? { ...summary } : {},
          }
        : m
    );

    const updatedConversations = state.conversations.map((conversation) => {
      if (conversation.last_message?.id === messageId) {
        return {
          ...conversation,
          last_message: {
            ...conversation.last_message,
            reactions: reactions ? [...reactions] : [],
            reactions_summary: summary ? { ...summary } : {},
          },
        };
      }
      return conversation;
    });

    const updatedActiveConversation =
      state.activeConversation?.last_message?.id === messageId
        ? {
            ...state.activeConversation,
            last_message: state.activeConversation.last_message
              ? {
                  ...state.activeConversation.last_message,
                  reactions: reactions ? [...reactions] : [],
                  reactions_summary: summary ? { ...summary } : {},
                }
              : state.activeConversation.last_message,
          }
        : state.activeConversation;

    return {
      messages: updatedMessages,
      conversations: updatedConversations,
      activeConversation: updatedActiveConversation,
    };
  }),
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

