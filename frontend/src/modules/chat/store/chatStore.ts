/**
 * Zustand Store para o Flow Chat
 * ✅ MELHORIA: Estado normalizado para melhor performance
 * ✅ MELHORIA: Seletores memoizados para reduzir re-renders
 */
import { create } from 'zustand';
import { shallow } from 'zustand/shallow';
import { Conversation, Message, Department } from '../types';
import { upsertConversation, mergeConversations } from './conversationUpdater';
import { sortMessagesByTimestamp, mergeAttachments } from '../utils/messageUtils';

/**
 * ✅ NOVO: Estrutura normalizada de mensagens
 * - byId: Busca O(1) por ID
 * - byConversationId: IDs ordenados por conversa (sem reordenar a cada add)
 * - Ordenação apenas ao carregar, não a cada adição
 */
interface NormalizedMessages {
  byId: Record<string, Message>;
  byConversationId: Record<string, string[]>; // conversationId -> array de messageIds ordenados
}

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

  // ✅ MELHORIA: Mensagens normalizadas
  messages: NormalizedMessages;
  // ✅ COMPATIBILIDADE: Manter getter para array (para componentes existentes)
  getMessagesArray: (conversationId?: string) => Message[];
  setMessages: (messages: Message[], conversationId?: string) => void;
  addMessage: (message: Message) => void;
  updateMessageStatus: (messageId: string, status: string) => void;
  updateMessageReactions: (
    messageId: string,
    reactions: Message['reactions'],
    summary: Message['reactions_summary']
  ) => void;
  updateMessageDeleted: (messageId: string) => void;
  updateAttachment: (attachmentId: string, updates: Partial<Message['attachments'][number]>) => void;

  // Estado do chat
  typing: boolean;
  typingUser: string | null;
  setTyping: (typing: boolean, user?: string) => void;

  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  setConnectionStatus: (status: 'connecting' | 'connected' | 'disconnected') => void;

  // Reply (responder mensagem)
  replyToMessage: Message | null;
  setReplyToMessage: (message: Message | null) => void;
  clearReply: () => void;

  // Reset
  reset: () => void;
}

/**
 * ✅ HELPER: Normaliza array de mensagens para estrutura normalizada
 */
function normalizeMessages(messages: Message[]): NormalizedMessages {
  const byId: Record<string, Message> = {};
  const byConversationId: Record<string, string[]> = {};
  
  // Ordenar uma vez antes de normalizar
  const sorted = sortMessagesByTimestamp(messages);
  
  sorted.forEach((messageItem) => {
    byId[messageItem.id] = messageItem;
    
    // Extrair conversationId
    const conversationId = message.conversation_id 
      ? String(message.conversation_id)
      : (typeof message.conversation === 'object' && message.conversation?.id)
      ? String(message.conversation.id)
      : (typeof message.conversation === 'string')
      ? message.conversation
      : null;
    
    if (conversationId) {
      if (!byConversationId[conversationId]) {
        byConversationId[conversationId] = [];
      }
      // ✅ Adicionar ID mantendo ordem (já está ordenado)
      if (!byConversationId[conversationId].includes(message.id)) {
        byConversationId[conversationId].push(message.id);
      }
    }
  });
  
  return { byId, byConversationId };
}

/**
 * ✅ HELPER: Insere mensagem na posição correta (mantém ordem sem reordenar tudo)
 */
function insertMessageInOrder(
  messageIds: string[],
  messageId: string,
  message: Message,
  byId: Record<string, Message>
): string[] {
  // Se já existe, não adicionar
  if (messageIds.includes(messageId)) {
    return messageIds;
  }
  
  const messageTime = new Date(message.created_at).getTime();
  
  // ✅ Busca binária para encontrar posição correta (O(log n) ao invés de O(n))
  let left = 0;
  let right = messageIds.length;
  
  while (left < right) {
    const mid = Math.floor((left + right) / 2);
    const midMessage = byId[messageIds[mid]];
    if (!midMessage) {
      // Se mensagem não existe, pular
      left = mid + 1;
      continue;
    }
    const midTime = new Date(midMessage.created_at).getTime();
    
    if (messageTime < midTime) {
      right = mid;
    } else {
      left = mid + 1;
    }
  }
  
  // Inserir na posição encontrada
  const newIds = [...messageIds];
  newIds.splice(left, 0, messageId);
  return newIds;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // State inicial
  departments: [],
  activeDepartment: null,
  conversations: [],
  activeConversation: null,
  messages: { byId: {}, byConversationId: {} },
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
        messages: { byId: {}, byConversationId: {} }
      };
    }
    
    // ✅ FIX: Se já é a mesma conversa, não fazer nada (evita resetar mensagens e referencia)
    if (state.activeConversation?.id === conversation.id) {
      console.log('🔕 [STORE] Conversa já está ativa, mantendo:', conversation.id);
      return state; // Retornar state atual sem mudanças
    }
    
    console.log('✅ [STORE] Definindo conversa ativa:', conversation.id, '| Antiga:', state.activeConversation?.id || 'nenhuma');
    
    // ✅ MELHORIA: Manter mensagens de outras conversas no cache (byId)
    // Mas limpar apenas as mensagens da conversa anterior (se houver)
    // Isso permite cache entre conversas sem carregar tudo na memória
    const updatedMessages = { ...state.messages };
    
    // Se tinha conversa ativa anterior, manter suas mensagens no cache (não limpar)
    // Apenas garantir que a nova conversa tenha array vazio se não existir
    if (conversation.id && !updatedMessages.byConversationId[conversation.id]) {
      updatedMessages.byConversationId[conversation.id] = [];
    }
    
    return {
      activeConversation: conversation,
      messages: updatedMessages
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
    
    // ✅ CORREÇÃO CRÍTICA: SEMPRE atualizar activeConversation se for a mesma conversa
    // Isso garante que nome, foto, last_message, etc. atualizem em tempo real
    const isActiveConversation = state.activeConversation?.id === conversation.id;
    
    if (isActiveConversation) {
      console.log('🔄 [STORE] Atualizando activeConversation:', {
        oldName: state.activeConversation.contact_name,
        newName: conversation.contact_name,
        oldPhone: state.activeConversation.contact_phone,
        newPhone: conversation.contact_phone,
        oldType: state.activeConversation.conversation_type,
        newType: conversation.conversation_type,
        conversationId: conversation.id
      });
    }
    
    // ✅ CORREÇÃO CRÍTICA: Usar mergeConversations para garantir merge correto
    // Isso garante que campos importantes sejam atualizados corretamente (nome, foto, telefone, tipo, last_message)
    const updatedActiveConversation = isActiveConversation && state.activeConversation
      ? {
          ...mergeConversations(state.activeConversation, conversation),  // ✅ Usar função de merge unificada
          // ✅ FORÇAR nova referência para garantir re-render
          _updatedAt: Date.now()
        }
      : state.activeConversation;
    
    return {
      conversations: updatedConversations,
      activeConversation: updatedActiveConversation
    };
  }),
  removeConversation: (conversationId) => set((state) => {
    const updatedMessages = { ...state.messages };
    // ✅ Limpar mensagens da conversa removida
    delete updatedMessages.byConversationId[conversationId];
    // Remover mensagens do byId também (opcional - pode manter para cache)
    
    return {
      conversations: state.conversations.filter(c => c.id !== conversationId),
      // Se a conversa removida era a ativa, limpar
      activeConversation: state.activeConversation?.id === conversationId 
        ? null 
        : state.activeConversation,
      messages: updatedMessages
    };
  }),

  // ✅ MELHORIA: Getter para array (compatibilidade com código existente)
  getMessagesArray: (conversationId) => {
    const state = get();
    if (!conversationId && state.activeConversation) {
      conversationId = state.activeConversation.id;
    }
    
    if (!conversationId) {
      return [];
    }
    
    const messageIds = state.messages.byConversationId[conversationId] || [];
    return messageIds.map(id => state.messages.byId[id]).filter(Boolean);
  },

  // ✅ MELHORIA: setMessages agora normaliza e organiza por conversa
  setMessages: (messages, conversationId) => set((state) => {
    if (!conversationId && state.activeConversation) {
      conversationId = state.activeConversation.id;
    }
    
    if (!conversationId) {
      console.warn('⚠️ [STORE] setMessages sem conversationId');
      return state;
    }
    
    // ✅ Normalizar novas mensagens
    const normalized = normalizeMessages(messages);
    
    // ✅ Merge com mensagens existentes (preservar outras conversas)
    const updatedById = { ...state.messages.byId, ...normalized.byId };
    const updatedByConversationId = { 
      ...state.messages.byConversationId,
      [conversationId]: normalized.byConversationId[conversationId] || []
    };
    
    return {
      messages: {
        byId: updatedById,
        byConversationId: updatedByConversationId
      }
    };
  }),

  // ✅ MELHORIA: addMessage agora usa estrutura normalizada (sem reordenar tudo)
  addMessage: (message) => set((state) => {
    // ✅ FIX CRÍTICO: Verificar se mensagem pertence à conversa ativa
    if (!state.activeConversation) {
      console.log('⚠️ [STORE] Nenhuma conversa ativa, ignorando mensagem:', message.id);
      return state;
    }
    
    // ✅ FIX CRÍTICO: Comparar conversation_id da mensagem com a conversa ativa
    let messageConversationId: string | null = null;
    
    if (message.conversation_id) {
      messageConversationId = String(message.conversation_id);
    } else if (message.conversation) {
      if (typeof message.conversation === 'object' && message.conversation.id) {
        messageConversationId = String(message.conversation.id);
      } else if (typeof message.conversation === 'string') {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
        if (uuidRegex.test(message.conversation)) {
          messageConversationId = message.conversation;
        } else {
          console.warn('⚠️ [STORE] conversation é string mas não é UUID:', message.conversation);
          messageConversationId = null;
        }
      } else {
        messageConversationId = String(message.conversation);
      }
    }
    
    const activeConversationId = state.activeConversation.id ? String(state.activeConversation.id) : null;
    
    if (!messageConversationId) {
      console.warn('⚠️ [STORE] Mensagem sem conversation_id válido, ignorando:', message.id);
      return state;
    }
    
    if (messageConversationId !== activeConversationId) {
      console.log('⚠️ [STORE] Mensagem não pertence à conversa ativa, ignorando:', {
        messageId: message.id,
        messageConversationId,
        activeConversationId
      });
      return state;
    }
    
    console.log('✅ [STORE] Mensagem pertence à conversa ativa, adicionando:', message.id);
    
    // ✅ Verificar se mensagem já existe
    const existingMessage = state.messages.byId[message.id];
    const messageIds = state.messages.byConversationId[messageConversationId] || [];
    
    if (existingMessage) {
      // ✅ Merge inteligente de attachments
      let updatedMessage = message;
      if (existingMessage.attachments && existingMessage.attachments.length > 0 && 
          message.attachments && message.attachments.length > 0) {
        const mergedAttachments = mergeAttachments(existingMessage.attachments, message.attachments);
        updatedMessage = { ...message, attachments: mergedAttachments };
      } else if (existingMessage.attachments && existingMessage.attachments.length > 0) {
        // Preservar attachments existentes se nova mensagem não tem
        updatedMessage = { ...message, attachments: existingMessage.attachments };
      } else if (message.attachments && message.attachments.length > 0) {
        // Usar novos attachments
        updatedMessage = message;
      }
      
      // ✅ Atualizar mensagem existente (sem reordenar)
      return {
        messages: {
          byId: {
            ...state.messages.byId,
            [message.id]: updatedMessage
          },
          byConversationId: state.messages.byConversationId
        }
      };
    }
    
    // ✅ NOVA MENSAGEM: Inserir na posição correta (O(log n) ao invés de O(n log n))
    const updatedMessageIds = insertMessageInOrder(
      messageIds,
      message.id,
      message,
      state.messages.byId
    );
    
    return {
      messages: {
        byId: {
          ...state.messages.byId,
          [message.id]: message
        },
        byConversationId: {
          ...state.messages.byConversationId,
          [messageConversationId]: updatedMessageIds
        }
      }
    };
  }),

  updateMessageStatus: (messageId, status) => set((state) => {
    const message = state.messages.byId[messageId];
    if (!message) return state;
    
    return {
      messages: {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [messageId]: { ...message, status: status as any }
        }
      }
    };
  }),

  updateMessageReactions: (messageId, reactions, summary) => set((state) => {
    const message = state.messages.byId[messageId];
    if (!message) return state;
    
    const updatedMessage = {
      ...message,
      reactions: reactions ? [...reactions] : [],
      reactions_summary: summary ? { ...summary } : {},
    };
    
    // ✅ Atualizar também nas conversas se for last_message
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
      messages: {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [messageId]: updatedMessage
        }
      },
      conversations: updatedConversations,
      activeConversation: updatedActiveConversation,
    };
  }),

  updateMessageDeleted: (messageId) => set((state) => {
    const message = state.messages.byId[messageId];
    if (!message) return state;
    
    const updatedMessage = {
      ...message,
      is_deleted: true,
      deleted_at: new Date().toISOString()
    };
    
    // ✅ Atualizar activeConversation se for a mesma conversa
    const messageConversationId = message.conversation_id 
      ? String(message.conversation_id)
      : (typeof message.conversation === 'object' && message.conversation?.id)
      ? String(message.conversation.id)
      : (typeof message.conversation === 'string')
      ? message.conversation
      : null;
    
    const updatedActiveConversation = state.activeConversation && 
      messageConversationId === state.activeConversation.id
      ? {
          ...state.activeConversation,
          // Não precisa atualizar messages array aqui (já está normalizado)
        }
      : state.activeConversation;

    return {
      messages: {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [messageId]: updatedMessage
        }
      },
      activeConversation: updatedActiveConversation
    };
  }),

  updateAttachment: (attachmentId, updates) => set((state) => {
    // ✅ Buscar mensagem que contém o attachment
    let foundMessage: Message | null = null;
    let foundMessageId: string | null = null;
    
    for (const [messageId, message] of Object.entries(state.messages.byId)) {
      if (message.attachments?.some(att => att.id === attachmentId)) {
        foundMessage = message;
        foundMessageId = messageId;
        break;
      }
    }
    
    if (!foundMessage || !foundMessageId) return state;
    
    const updatedAttachments = foundMessage.attachments.map(att =>
      att.id === attachmentId ? { ...att, ...updates } : att
    );
    
    return {
      messages: {
        ...state.messages,
        byId: {
          ...state.messages.byId,
          [foundMessageId]: {
            ...foundMessage,
            attachments: updatedAttachments
          }
        }
      }
    };
  }),

  // Estado do chat
  setTyping: (typing, user) => set({ typing, typingUser: user || null }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  // Reply (responder mensagem)
  replyToMessage: null,
  setReplyToMessage: (message) => set({ replyToMessage: message }),
  clearReply: () => set({ replyToMessage: null }),

  // Reset
  reset: () => set({
    departments: [],
    activeDepartment: null,
    conversations: [],
    activeConversation: null,
    messages: { byId: {}, byConversationId: {} },
    typing: false,
    typingUser: null,
    connectionStatus: 'disconnected',
    replyToMessage: null
  })
}));
