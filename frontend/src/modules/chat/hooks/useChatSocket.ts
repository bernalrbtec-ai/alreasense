/**
 * 🎣 useChatSocket - Hook para gerenciar WebSocket de chat
 * 
 * Usa o ChatWebSocketManager global (1 conexão persistente)
 * ao invés de criar/destruir conexões a cada troca de conversa.
 * 
 * Arquitetura:
 * - 1 WebSocket por usuário (não por conversa)
 * - Subscribe/Unsubscribe para trocar conversas
 * - Escalável para 10-20+ conversas simultâneas
 */

import { useEffect, useCallback, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useChatStore } from '../store/chatStore';
import { chatWebSocketManager, WebSocketMessage } from '../services/ChatWebSocketManager';
import { useDesktopNotifications } from '@/hooks/useDesktopNotifications';

export function useChatSocket(conversationId?: string) {
  const [isConnected, setIsConnected] = useState(false);
  const { token, user } = useAuthStore();
  const { addMessage, updateMessageStatus, setTyping, updateConversation } = useChatStore();
  const { showNotification, isEnabled: notificationsEnabled } = useDesktopNotifications();

  // Conectar ao manager global (1 vez por sessão)
  useEffect(() => {
    if (!token || !user || !user.tenant_id) {
      console.log('⏸️ [HOOK] Aguardando autenticação...');
      return;
    }

    console.log('🔌 [HOOK] Conectando ao manager global...');
    chatWebSocketManager.connect(user.tenant_id, token);

    // Atualizar estado de conexão
    const checkConnection = setInterval(() => {
      setIsConnected(chatWebSocketManager.getIsConnected());
    }, 500);

    return () => {
      clearInterval(checkConnection);
    };
  }, [token, user]);

  // Subscribe/Unsubscribe quando conversationId muda
  useEffect(() => {
    if (!conversationId) {
      console.log('⏸️ [HOOK] Sem conversationId');
      return;
    }

    if (!chatWebSocketManager.getIsConnected()) {
      console.log('⏸️ [HOOK] Aguardando conexão...');
      return;
    }

    console.log(`🔄 [HOOK] Subscrevendo à conversa: ${conversationId}`);
    chatWebSocketManager.subscribe(conversationId);

    return () => {
      console.log(`🔌 [HOOK] Desinscrevendo da conversa: ${conversationId}`);
      chatWebSocketManager.unsubscribe(conversationId);
    };
  }, [conversationId]);

  // Registrar listeners de eventos
  useEffect(() => {
    const handleMessageReceived = (data: WebSocketMessage) => {
      if (data.message) {
        console.log('💬 [HOOK] Nova mensagem recebida:', data.message);
        addMessage(data.message);
        
        // 🔔 Notificar desktop (apenas se for mensagem recebida e notificações estão habilitadas)
        if (notificationsEnabled && data.message.direction === 'inbound') {
          const conversationName = data.message.conversation || 'Nova mensagem';
          const senderName = data.message.sender_name || data.message.sender_phone || 'Contato';
          const preview = data.message.content 
            ? data.message.content.substring(0, 100) 
            : data.message.attachments?.length 
            ? '📎 Anexo' 
            : 'Nova mensagem';
          
          showNotification({
            title: conversationName,
            body: `${senderName}: ${preview}`,
            tag: data.message.conversation,
            conversationId: data.message.conversation,
          });
        }
      }
    };

    const handleStatusUpdate = (data: WebSocketMessage) => {
      if (data.message_id && data.status) {
        console.log(`📊 [HOOK] Status atualizado: ${data.message_id} → ${data.status}`);
        updateMessageStatus(data.message_id, data.status);
      }
    };

    const handleTyping = (data: WebSocketMessage) => {
      if (data.user_id) {
        console.log(`✍️ [HOOK] Typing: ${data.user_email} (${data.is_typing ? 'start' : 'stop'})`);
        setTyping(data.user_id, data.is_typing || false);
      }
    };

    const handleConversationUpdate = (data: WebSocketMessage) => {
      if (data.conversation) {
        console.log('🔄 [HOOK] Conversa atualizada:', data.conversation);
        updateConversation(data.conversation);
      }
    };

    // Registrar listeners
    chatWebSocketManager.on('message_received', handleMessageReceived);
    chatWebSocketManager.on('message_status_update', handleStatusUpdate);
    chatWebSocketManager.on('typing', handleTyping);
    chatWebSocketManager.on('conversation_updated', handleConversationUpdate);

    // Cleanup
    return () => {
      chatWebSocketManager.off('message_received', handleMessageReceived);
      chatWebSocketManager.off('message_status_update', handleStatusUpdate);
      chatWebSocketManager.off('typing', handleTyping);
      chatWebSocketManager.off('conversation_updated', handleConversationUpdate);
    };
  }, [addMessage, updateMessageStatus, setTyping, updateConversation, notificationsEnabled, showNotification]);

  // API pública
  const sendMessage = useCallback((content: string, isInternal = false): boolean => {
    if (!isConnected) {
      console.warn('⚠️ [HOOK] WebSocket não conectado (ignorando envio)');
      return false;
    }

    console.log('📤 [HOOK] Enviando mensagem:', content.substring(0, 50));
    return chatWebSocketManager.sendChatMessage(content, isInternal);
  }, [isConnected]);

  const sendTyping = useCallback((isTyping: boolean) => {
    if (!isConnected) return;
    chatWebSocketManager.sendTyping(isTyping);
  }, [isConnected]);

  const markAsSeen = useCallback((messageId: string) => {
    if (!isConnected) return;
    chatWebSocketManager.markAsSeen(messageId);
  }, [isConnected]);

  return {
    sendMessage,
    sendTyping,
    markAsSeen,
    isConnected,
  };
}

