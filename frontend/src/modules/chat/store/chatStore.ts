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
  setActiveConversation: (conversation) => set({ 
    activeConversation: conversation,
    messages: [] // Limpa mensagens ao trocar conversa
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
      return {
        conversations: state.conversations.map(c => 
          c.id === conversation.id ? conversation : c
        )
      };
    }
    
    // ✅ IMPORTANTE: Garantir que conversation tem status (default 'pending' se não tiver)
    const conversationWithStatus = {
      ...conversation,
      status: conversation.status || 'pending'
    };
    
    // Adicionar no início da lista (conversas mais recentes primeiro)
    const newConversations = [conversationWithStatus, ...state.conversations];
    
    console.log('✅ [STORE] Nova conversa adicionada:', conversation.contact_name || conversation.contact_phone);
    console.log(`   Total de conversas: ${state.conversations.length} → ${newConversations.length}`);
    console.log(`   Status: ${conversationWithStatus.status}, Department: ${conversationWithStatus.department || 'null'}`);
    console.log(`   ID: ${conversationWithStatus.id}`);
    console.log(`   ✅ STORE ATUALIZADO - Nova lista:`, newConversations.map(c => ({
      id: c.id,
      name: c.contact_name || c.contact_phone,
      status: c.status,
      department: c.department || null
    })));
    
    return {
      conversations: newConversations
    };
  }),
  updateConversation: (conversation) => set((state) => ({
    conversations: state.conversations.map(c => 
      c.id === conversation.id ? conversation : c
    ),
    activeConversation: state.activeConversation?.id === conversation.id 
      ? conversation 
      : state.activeConversation
  })),
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
                  
                  // Priorizar attachment com URL válida
                  if (existingHasUrl && !newHasUrl) {
                    return existingAtt; // Manter attachment atualizado
                  }
                  // Se novo tem URL válida ou ambos não têm, usar o novo
                  return newAtt;
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
    // Adicionar nova mensagem
    return {
      messages: [...state.messages, message]
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

