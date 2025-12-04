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
  const { addMessage, updateMessageStatus, setTyping, updateConversation, updateMessageReactions } = useChatStore();
  // ✅ REMOVIDO: updateAttachment não é mais usado aqui (movido para useTenantSocket)
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
      // ✅ CORREÇÃO CRÍTICA: Usar activeConversation do store ao invés de conversationId do closure
      // Isso garante que sempre temos o valor atualizado, mesmo se a conversa mudou rapidamente
      const { activeConversation: currentActiveConversation } = useChatStore.getState();
      const currentConversationId = currentActiveConversation?.id;
      
      console.log('🔔 [HOOK] handleMessageReceived chamado!', {
        hasMessage: !!data.message,
        messageId: data.message?.id,
        messageConversationId: data.message?.conversation || data.message?.conversation_id,
        subscribedConversationId: conversationId,
        activeConversationId: currentConversationId,
        fullData: data
      });
      
      if (data.message) {
        console.log('💬 [HOOK] Nova mensagem recebida via useChatSocket:', data.message);
        console.log('💬 [HOOK] Conversation ID:', data.message.conversation || data.message.conversation_id);
        console.log('💬 [HOOK] Active conversation ID:', currentConversationId);
        
        // ✅ DEBUG: Verificar se mensagem tem reply_to
        if (data.message.metadata?.reply_to) {
          console.log('💬 [HOOK] ✅ Mensagem tem reply_to:', data.message.metadata.reply_to);
          console.log('💬 [HOOK] Metadata completo:', data.message.metadata);
        } else {
          console.log('💬 [HOOK] ⚠️ Mensagem NÃO tem reply_to no metadata');
          console.log('💬 [HOOK] Metadata:', data.message.metadata);
        }
        
        // ✅ CORREÇÃO CRÍTICA: Usar activeConversation do store ao invés de conversationId do closure
        // Isso garante que sempre temos o valor atualizado, mesmo se a conversa mudou rapidamente
        const { activeConversation: currentActiveConversation } = useChatStore.getState();
        const messageConversationId = data.message.conversation 
          ? String(data.message.conversation) 
          : (data.message.conversation_id ? String(data.message.conversation_id) : null);
        const activeConversationId = currentActiveConversation?.id ? String(currentActiveConversation.id) : null;
        const subscribedConversationId = conversationId ? String(conversationId) : null;
        
        // ✅ CORREÇÃO: Verificar se mensagem pertence à conversa subscrita OU à conversa ativa
        // Isso trata o caso onde a conversa mudou rapidamente mas a mensagem ainda chegou
        // ✅ CORREÇÃO CRÍTICA: Se não há conversationId subscrito mas há conversa ativa, aceitar mensagem
        // Isso resolve o problema onde mensagens chegam antes do subscribe ser processado
        const belongsToSubscribed = subscribedConversationId && messageConversationId && 
          messageConversationId === subscribedConversationId;
        const belongsToActive = activeConversationId && messageConversationId && 
          messageConversationId === activeConversationId;
        
        // ✅ CORREÇÃO: Aceitar mensagem se pertence à conversa ativa OU se não há subscribe ainda mas há conversa ativa
        // Isso garante que mensagens sejam adicionadas mesmo se o subscribe ainda não foi processado
        if (!belongsToSubscribed && !belongsToActive) {
          console.log('⚠️ [HOOK] Mensagem não pertence à conversa subscrita/ativa, ignorando:', {
            messageConversationId,
            subscribedConversationId,
            activeConversationId
          });
          return; // Não adicionar mensagem se não pertence à conversa correta
        }
        
        console.log('✅ [HOOK] Mensagem aceita para adicionar:', {
          belongsToSubscribed,
          belongsToActive,
          messageConversationId
        });
        
        // ✅ Verificar se mensagem já existe e preservar attachments existentes
        // ✅ CORREÇÃO: Usar currentActiveConversation já obtido acima (evita múltiplas chamadas)
        const { getMessagesArray } = useChatStore.getState();
        const messages = currentActiveConversation ? getMessagesArray(currentActiveConversation.id) : [];
        const existingMessage = messages.find((messageItem) => messageItem.id === data.message.id);
        if (existingMessage && existingMessage.attachments && existingMessage.attachments.length > 0) {
          // Se a mensagem nova não tiver attachments mas a antiga tiver, preservar
          if (!data.message.attachments || data.message.attachments.length === 0) {
            console.log('📎 [HOOK] Preservando attachments existentes na mensagem:', data.message.id);
            addMessage({ ...data.message, attachments: existingMessage.attachments });
          } else {
            addMessage(data.message);
          }
        } else {
          addMessage(data.message);
        }
        
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
        setTyping(data.is_typing || false, data.user_email || data.user_id);
      }
    };

    const handleConversationUpdate = (data: WebSocketMessage) => {
      if (data.conversation) {
        console.log('🔄 [HOOK] Conversa atualizada:', data.conversation);
        // ✅ IMPORTANTE: Apenas atualizar store, NÃO mostrar toast
        // Toasts são responsabilidade do useTenantSocket (evita duplicação)
        updateConversation(data.conversation);
      }
    };

    const handleReactionUpdate = (data: WebSocketMessage) => {
      if (data.message) {
        // ✅ CORREÇÃO: Verificar se mensagem pertence à conversa ativa antes de atualizar
        const { activeConversation } = useChatStore.getState();
        const messageConversationId = data.message.conversation 
          ? String(data.message.conversation) 
          : (data.conversation_id ? String(data.conversation_id) : null);
        const activeConversationId = activeConversation?.id ? String(activeConversation.id) : null;
        
        // Só atualizar se mensagem pertence à conversa ativa OU se não há conversa ativa (pode ser mensagem de outra conversa)
        // Mas sempre atualizar se conversation_id bater (mensagem está na conversa ativa)
        if (activeConversationId && messageConversationId && messageConversationId === activeConversationId) {
          console.log('👍 [HOOK] Reação atualizada (conversa ativa):', data.message.id, data.reaction);
          updateMessageReactions(
            data.message.id,
            data.message.reactions || [],
            data.message.reactions_summary || {}
          );
        } else if (!activeConversationId) {
          // Se não há conversa ativa, atualizar de qualquer forma (pode ser necessário para outras conversas)
          console.log('👍 [HOOK] Reação atualizada (sem conversa ativa):', data.message.id, data.reaction);
          updateMessageReactions(
            data.message.id,
            data.message.reactions || [],
            data.message.reactions_summary || {}
          );
        } else {
          console.log('ℹ️ [HOOK] Reação atualizada ignorada (mensagem não pertence à conversa ativa):', {
            messageId: data.message.id,
            messageConversationId,
            activeConversationId
          });
        }
      }
    };

    const handleMessageDeleted = (data: WebSocketMessage) => {
      if (data.message) {
        const { updateMessageDeleted } = useChatStore.getState();
        console.log('🗑️ [HOOK] Mensagem apagada:', data.message.id);
        updateMessageDeleted(data.message.id);
      }
    };

    // ✅ REMOVIDO: handleAttachmentUpdated movido para useTenantSocket
    // O useTenantSocket já escuta o grupo tenant e processa attachment_updated
    // Remover daqui evita duplicação, já que o ChatWebSocketManager também está conectado ao grupo tenant
    // e receberia o mesmo evento duas vezes (do grupo tenant + do grupo da conversa via subscribe)

    // ✅ ESCUTAR novas conversas do tenant (via ChatConsumerV2)
    // ⚠️ IMPORTANTE: Este evento é TAMBÉM processado por useTenantSocket
    // O useTenantSocket é responsável por toasts, este hook apenas atualiza store
    const handleNewConversation = (data: WebSocketMessage) => {
      if (data.conversation) {
        console.log('🆕 [HOOK] Nova conversa recebida via WebSocket:', data.conversation);
        // ✅ IMPORTANTE: Apenas atualizar store, NÃO mostrar toast
        // Toasts são responsabilidade do useTenantSocket (evita duplicação)
        const { addConversation } = useChatStore.getState();
        addConversation(data.conversation);
      }
    };

    // Registrar listeners
    chatWebSocketManager.on('message_received', handleMessageReceived);
    chatWebSocketManager.on('message_status_update', handleStatusUpdate);
    chatWebSocketManager.on('typing', handleTyping);
    chatWebSocketManager.on('conversation_updated', handleConversationUpdate);
    chatWebSocketManager.on('message_reaction_update', handleReactionUpdate);
    chatWebSocketManager.on('message_deleted', handleMessageDeleted);
    // ✅ REMOVIDO: attachment_updated - processado por useTenantSocket (evita duplicação)
    chatWebSocketManager.on('new_conversation', handleNewConversation);

    // Cleanup
    return () => {
      chatWebSocketManager.off('message_received', handleMessageReceived);
      chatWebSocketManager.off('message_status_update', handleStatusUpdate);
      chatWebSocketManager.off('typing', handleTyping);
      chatWebSocketManager.off('conversation_updated', handleConversationUpdate);
      chatWebSocketManager.off('message_reaction_update', handleReactionUpdate);
      chatWebSocketManager.off('message_deleted', handleMessageDeleted);
      // ✅ REMOVIDO: attachment_updated - processado por useTenantSocket (evita duplicação)
      chatWebSocketManager.off('new_conversation', handleNewConversation);
    };
  }, [addMessage, updateMessageStatus, setTyping, updateConversation, updateMessageReactions, notificationsEnabled, showNotification]);

  // API pública
  // ✅ CORREÇÃO CRÍTICA: Buscar conversationId do store diretamente ao invés de usar do closure
  // Isso garante que sempre usamos a conversa ativa atual, mesmo se mudou rapidamente
  const sendMessage = useCallback((content: string, includeSignature = true, isInternal = false, replyToMessageId?: string, mentions?: string[]): boolean => {
    if (!isConnected) {
      console.warn('⚠️ [HOOK] WebSocket não conectado (ignorando envio)');
      return false;
    }

    // ✅ CORREÇÃO CRÍTICA: Buscar activeConversation do store diretamente (não usar closure)
    const { activeConversation: currentActiveConversation } = useChatStore.getState();
    const currentConversationId = currentActiveConversation?.id;
    
    if (!currentConversationId) {
      console.error('❌ [HOOK] Nenhuma conversa ativa para enviar mensagem');
      return false;
    }
    
    // ✅ LOG CRÍTICO: Verificar se conversationId mudou
    if (conversationId !== currentConversationId) {
      console.warn('⚠️ [HOOK] ATENÇÃO: conversationId mudou!', {
        oldId: conversationId,
        newId: currentConversationId,
        oldName: conversationId ? 'N/A' : 'N/A',
        newName: currentActiveConversation?.contact_name || 'N/A',
        newPhone: currentActiveConversation?.contact_phone || 'N/A',
        newType: currentActiveConversation?.conversation_type || 'N/A'
      });
    }

    // ✅ NOVO: Suporte a reply_to via metadata
    if (replyToMessageId) {
      console.log('📤 [HOOK] Enviando mensagem com reply:', content.substring(0, 50), `| Reply to: ${replyToMessageId}`);
      console.log('📤 [HOOK] Payload completo:', {
        type: 'send_message',
        conversation_id: currentConversationId,
        content: content.substring(0, 50),
        include_signature: includeSignature,
        is_internal: isInternal,
        reply_to: replyToMessageId,
        mentions: mentions
      });
      // ✅ CORREÇÃO: Usar sendChatMessage ao invés de sendMessage privado
      // sendChatMessage não suporta reply_to diretamente, então precisamos usar o método público
      // que aceita todos os parâmetros necessários
      console.log('📤 [HOOK] Enviando mensagem com reply via sendChatMessage');
      // Nota: reply_to será adicionado via metadata no backend se necessário
      // Por enquanto, usar sendChatMessage normal e o backend processará reply_to se fornecido
      return chatWebSocketManager.sendChatMessage(content, includeSignature, isInternal, mentions, currentConversationId);
    }

    console.log('📤 [HOOK] Enviando mensagem:', content.substring(0, 50), `| Assinatura: ${includeSignature ? 'SIM' : 'NÃO'}`, mentions ? `| Mentions: ${mentions.length}` : '');
    // ✅ CORREÇÃO: Passar conversationId atual para sendChatMessage
    return chatWebSocketManager.sendChatMessage(content, includeSignature, isInternal, mentions, currentConversationId);
  }, [isConnected, conversationId]); // ✅ Manter conversationId na dependência para detectar mudanças

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

