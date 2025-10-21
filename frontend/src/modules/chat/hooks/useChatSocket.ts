/**
 * Hook WebSocket para Flow Chat
 * Gerencia conexão, reconexão automática e eventos
 */
import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { WebSocketMessage } from '../types';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'wss://alreasense-backend-production.up.railway.app';

export function useChatSocket(conversationId?: string) {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const {
    addMessage,
    updateMessageStatus,
    setTyping,
    setConnectionStatus,
    connectionStatus,
    updateConversation
  } = useChatStore();

  // Obter dados de autenticação do Zustand
  const { token, user } = useAuthStore();
  
  // useRef para evitar re-criação do callback connect
  const conversationIdRef = useRef(conversationId);
  const tokenRef = useRef(token);
  const userRef = useRef(user);
  
  // Atualizar refs quando valores mudarem
  useEffect(() => {
    conversationIdRef.current = conversationId;
    tokenRef.current = token;
    userRef.current = user;
  }, [conversationId, token, user]);

  const handleWebSocketMessage = useCallback((data: WebSocketMessage) => {
    console.log('📨 [WS] Mensagem recebida:', data);

    switch (data.type) {
      case 'message_received':
        if (data.message) {
          addMessage(data.message);
          // Auto-scroll para última mensagem
          setTimeout(() => {
            const messagesContainer = document.querySelector('.chat-messages');
            if (messagesContainer) {
              messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
          }, 100);
        }
        break;

      case 'message_status_update':
        console.log('📊 [WS] Atualização de status recebida:', data);
        if (data.message_id && data.status) {
          console.log(`   Atualizando mensagem ${data.message_id} para status: ${data.status}`);
          updateMessageStatus(data.message_id, data.status);
          console.log('   ✅ Status atualizado no store');
        } else {
          console.warn('   ⚠️ Dados incompletos para atualização de status:', data);
        }
        break;

      case 'typing_status':
        setTyping(data.is_typing || false, data.user_email);
        // Auto-limpar typing após 3s
        if (data.is_typing) {
          setTimeout(() => setTyping(false), 3000);
        }
        break;

      case 'conversation_transferred':
        console.log('🔄 [WS] Conversa transferida:', data);
        // Mostrar notificação
        if (data.new_department || data.new_agent) {
          const message = `Conversa transferida para ${data.new_department || 'outro departamento'}`;
          // Usar toast notification
          if (window.toast) {
            window.toast.info(message);
          }
        }
        break;

      case 'new_conversation':
        console.log('🆕 [WS] Nova conversa criada:', data.conversation);
        // Adicionar conversa à lista (via store)
        if (data.conversation) {
          // Usar função do store para adicionar conversa
          const { addConversation } = useChatStore.getState();
          if (addConversation) {
            addConversation(data.conversation);
          }
        }
        break;

      case 'user_joined':
        console.log('👋 [WS] Usuário entrou:', data.user_email);
        break;

      default:
        console.warn('⚠️ [WS] Evento desconhecido:', data.type);
    }
  }, [addMessage, updateMessageStatus, setTyping, updateConversation]);

  const connect = useCallback(() => {
    const currentToken = tokenRef.current;
    const currentUser = userRef.current;
    const currentConversationId = conversationIdRef.current;
    
    console.log('🔍 [WS DEBUG] token:', currentToken ? `${currentToken.substring(0, 20)}...` : 'null');
    console.log('🔍 [WS DEBUG] user:', currentUser);
    console.log('🔍 [WS DEBUG] conversationId:', currentConversationId);
    
    if (!currentToken || !currentUser) {
      console.log('⏸️ [WS] Aguardando autenticação...', { token: !!currentToken, user: !!currentUser });
      return;
    }

    const tenantId = currentUser.tenant_id;
    
    console.log('🔍 [WS DEBUG] tenantId:', tenantId);

    if (!tenantId) {
      console.log('⏸️ [WS] Aguardando tenant_id...');
      return;
    }

    if (!currentConversationId) {
      console.log('⏸️ [WS] Aguardando conversationId...');
      return;
    }

    // Limpar WebSocket antigo se estiver fechado/fechando
    if (socketRef.current) {
      const state = socketRef.current.readyState;
      
      // Se já está conectado/conectando para a MESMA conversa, não reconectar
      if ((state === WebSocket.CONNECTING || state === WebSocket.OPEN)) {
        console.log('⏸️ [WS] Já conectado/conectando');
        return;
      }
      
      // Se está fechando/fechado, limpar referência
      if (state === WebSocket.CLOSING || state === WebSocket.CLOSED) {
        console.log('🧹 [WS] Limpando WebSocket antigo (estado:', state, ')');
        socketRef.current = null;
      }
    }

    setConnectionStatus('connecting');

    const wsUrl = `${WS_BASE_URL}/ws/chat/${tenantId}/${currentConversationId}/?token=${currentToken}`;
    console.log('🔌 [WS] Conectando:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        console.log('✅ [WS] Conectado com sucesso!');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('❌ [WS] Erro ao parsear mensagem:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ [WS] Erro:', error);
        setConnectionStatus('disconnected');
      };

      ws.onclose = (event) => {
        console.warn('🔌 [WS] Conexão fechada:', event.code, event.reason);
        setConnectionStatus('disconnected');
        socketRef.current = null;

        // Reconectar com backoff exponencial
        if (reconnectAttemptsRef.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`🔄 [WS] Reconectando em ${delay}ms (tentativa ${reconnectAttemptsRef.current + 1})...`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        } else {
          console.error('❌ [WS] Máximo de tentativas de reconexão atingido');
        }
      };

    } catch (error) {
      console.error('❌ [WS] Erro ao criar WebSocket:', error);
      setConnectionStatus('disconnected');
    }
  }, [setConnectionStatus, handleWebSocketMessage]); // ✅ Dependências estáveis

  const disconnect = useCallback(() => {
    console.log('🔌 [WS] Desconectando...');
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    // Resetar contador de reconexão ao desconectar manualmente
    reconnectAttemptsRef.current = 0;

    setConnectionStatus('disconnected');
  }, [setConnectionStatus]);

  const sendMessage = useCallback((content: string, isInternal = false) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      // Só logar erro se não estiver em transição (conectando)
      if (socketRef.current?.readyState !== WebSocket.CONNECTING) {
        console.warn('⚠️ [WS] WebSocket não conectado (ignorando envio)');
      }
      return false;
    }

    try {
      socketRef.current.send(JSON.stringify({
        type: 'send_message',
        content,
        is_internal: isInternal
      }));
      console.log('📤 [WS] Mensagem enviada');
      return true;
    } catch (error) {
      console.error('❌ [WS] Erro ao enviar mensagem:', error);
      return false;
    }
  }, []);

  const sendTyping = useCallback((isTyping: boolean) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      socketRef.current.send(JSON.stringify({
        type: 'typing',
        is_typing: isTyping
      }));
    } catch (error) {
      console.error('❌ [WS] Erro ao enviar typing:', error);
    }
  }, []);

  const markAsSeen = useCallback((messageId: string) => {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      socketRef.current.send(JSON.stringify({
        type: 'mark_as_seen',
        message_id: messageId
      }));
    } catch (error) {
      console.error('❌ [WS] Erro ao marcar como vista:', error);
    }
  }, []);

  // Conectar quando conversation mudar
  useEffect(() => {
    if (!conversationId) {
      console.log('⏸️ [WS] Sem conversationId, não conectando');
      return;
    }

    console.log(`🔄 [WS] Trocando para conversa: ${conversationId}`);
    connect();

    return () => {
      console.log(`🔌 [WS] Limpando conversa: ${conversationId}`);
      disconnect();
    };
  }, [conversationId]); // ✅ CORRETO: Só reconecta quando conversationId muda

  return {
    sendMessage,
    sendTyping,
    markAsSeen,
    isConnected: connectionStatus === 'connected'
  };
}

