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
    // Evitar duplicatas
    const exists = state.conversations.some(c => c.id === conversation.id);
    if (exists) {
      console.log('⚠️ [STORE] Conversa duplicada, ignorando:', conversation.contact_name || conversation.contact_phone);
      return state;
    }
    
    // Adicionar no início da lista (conversas mais recentes primeiro)
    console.log('✅ [STORE] Nova conversa adicionada:', conversation.contact_name || conversation.contact_phone);
    console.log(`   Total de conversas: ${state.conversations.length} → ${state.conversations.length + 1}`);
    return {
      conversations: [conversation, ...state.conversations]
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
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  updateMessageStatus: (messageId, status) => set((state) => ({
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, status: status as any } : m
    )
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

