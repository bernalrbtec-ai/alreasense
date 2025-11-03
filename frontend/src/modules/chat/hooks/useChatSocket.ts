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
  const { updateAttachment } = useChatStore.getState();
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
        // ✅ Verificar se mensagem já existe e preservar attachments existentes
        const { messages } = useChatStore.getState();
        const existingMessage = messages.find(m => m.id === data.message.id);
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
        setTyping(data.user_id, data.is_typing || false);
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

    // ✅ REMOVIDO: handleAttachmentDownloaded não é mais usado
    // O evento 'attachment_downloaded' foi substituído por 'attachment_updated'
    // que é mais robusto e inclui metadata normalizado

    const handleAttachmentUpdated = (data: WebSocketMessage) => {
      if (data.data?.attachment_id) {
        const attachmentId = data.data.attachment_id;
        const messageId = data.data.message_id;
        const fileUrl = data.data.file_url || '';
        
        // ✅ LOG REDUZIDO: Apenas informações essenciais (sem spam)
        // O log completo está no useTenantSocket, não precisa duplicar aqui
        console.log('📎 [HOOK] Attachment updated:', attachmentId);
        
        // ✅ Verificar se URL está correta (deve conter media-proxy)
        if (fileUrl && !fileUrl.includes('/api/chat/media-proxy')) {
          console.warn('⚠️ [HOOK] URL não é do media-proxy! URL recebida:', fileUrl.substring(0, 100));
        } else if (!fileUrl) {
          console.warn('⚠️ [HOOK] URL está vazia no evento attachment_updated!');
        }
        
        // ✅ LÓGICA MELHORADA: Buscar mensagem por message_id se fornecido (mais confiável)
        const { messages } = useChatStore.getState();
        let messageWithAttachment = null;
        
        if (messageId) {
          // Se message_id fornecido, usar ele (mais preciso)
          messageWithAttachment = messages.find(m => m.id === messageId);
        }
        
        if (!messageWithAttachment) {
          // Fallback: buscar por attachment_id
          messageWithAttachment = messages.find(m => 
            m.attachments?.some(a => a.id === attachmentId)
          );
        }
        
        if (messageWithAttachment) {
          // ✅ RACE CONDITION FIX: Verificar se attachment já foi atualizado
          // Evita updates duplicados ou conflitos se múltiplos eventos chegarem
          const existingAttachment = messageWithAttachment.attachments?.find(a => a.id === attachmentId);
          
          // ✅ MELHORIA: Só ignorar se:
          // 1. Attachment existe
          // 2. file_url não está vazio E é igual ao novo
          // 3. E metadata não tem flag processing (já está processado)
          const hasValidUrl = existingAttachment?.file_url && existingAttachment.file_url.trim() !== '';
          const isSameUrl = hasValidUrl && existingAttachment.file_url === fileUrl;
          const isProcessing = existingAttachment?.metadata?.processing === true;
          
          // ✅ IGNORAR apenas se tem URL válida, é a mesma URL, E não está processando
          if (existingAttachment && hasValidUrl && isSameUrl && !isProcessing) {
            console.log('ℹ️ [HOOK] Attachment já atualizado, ignorando update duplicado:', {
              attachmentId,
              oldUrl: existingAttachment?.file_url?.substring(0, 80) || 'VAZIO',
              newUrl: fileUrl?.substring(0, 80) || 'VAZIO',
              metadata: existingAttachment?.metadata
            });
            return;  // Já está atualizado e processado, não fazer nada
          }
          
          // ✅ Se está processando OU URL mudou OU URL estava vazia, ATUALIZAR
          console.log('🔄 [HOOK] Atualizando attachment:', {
            attachmentId,
            isProcessing,
            isSameUrl,
            hasValidUrl,
            oldUrl: existingAttachment?.file_url?.substring(0, 80) || 'VAZIO',
            newUrl: fileUrl?.substring(0, 80) || 'VAZIO',
            oldMetadata: existingAttachment?.metadata,
            newMetadata: data.data?.metadata
          });
          
          // ✅ IMPORTANTE: Atualizar metadata removendo flag processing explicitamente
          const updatedMetadata = { ...(data.data.metadata || {}) };
          delete updatedMetadata.processing; // Garantir que processing é false
          
          // Atualizar attachment específico
          updateAttachment(attachmentId, {
            file_url: fileUrl,
            thumbnail_url: data.data.thumbnail_url,
            mime_type: data.data.mime_type,
            metadata: updatedMetadata,  // ✅ Metadata sem flag processing
          } as any);
          
          // ✅ Forçar re-render da mensagem completa (clonar para garantir mudança de referência)
          const updatedMessage = {
            ...messageWithAttachment,
            attachments: messageWithAttachment.attachments?.map(att => {
              if (att.id === attachmentId) {
                return {
                  ...att,
                  file_url: fileUrl,
                  thumbnail_url: data.data.thumbnail_url,
                  mime_type: data.data.mime_type,
                  metadata: updatedMetadata  // ✅ Metadata sem flag processing
                };
              }
              return att;
            })
          };
          addMessage(updatedMessage as any);
          console.log('✅ [HOOK] Mensagem atualizada com attachment:', attachmentId);
        } else {
          console.warn('⚠️ [HOOK] Mensagem com attachment não encontrada:', { attachmentId, messageId });
          // ✅ NOVO: Se mensagem não está na lista (conversa não aberta), buscar do servidor
          // Isso garante que o attachment será atualizado quando a conversa for aberta
          if (messageId) {
            console.log('🔄 [HOOK] Mensagem não encontrada localmente, será atualizada quando conversa for aberta');
            // Não fazer fetch aqui - será carregado quando conversa for aberta
            // O attachment já está atualizado no banco, então quando carregar a mensagem,
            // o serializer já retornará a URL correta
          }
        }
      }
    };

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
    chatWebSocketManager.on('attachment_updated', handleAttachmentUpdated);
    chatWebSocketManager.on('new_conversation', handleNewConversation);

    // Cleanup
    return () => {
      chatWebSocketManager.off('message_received', handleMessageReceived);
      chatWebSocketManager.off('message_status_update', handleStatusUpdate);
      chatWebSocketManager.off('typing', handleTyping);
      chatWebSocketManager.off('conversation_updated', handleConversationUpdate);
      chatWebSocketManager.off('attachment_updated', handleAttachmentUpdated);
      chatWebSocketManager.off('new_conversation', handleNewConversation);
    };
  }, [addMessage, updateMessageStatus, setTyping, updateConversation, notificationsEnabled, showNotification]);

  // API pública
  const sendMessage = useCallback((content: string, includeSignature = true, isInternal = false): boolean => {
    if (!isConnected) {
      console.warn('⚠️ [HOOK] WebSocket não conectado (ignorando envio)');
      return false;
    }

    console.log('📤 [HOOK] Enviando mensagem:', content.substring(0, 50), `| Assinatura: ${includeSignature ? 'SIM' : 'NÃO'}`);
    return chatWebSocketManager.sendChatMessage(content, includeSignature, isInternal);
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

