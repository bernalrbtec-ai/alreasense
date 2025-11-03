/**
 * Hook WebSocket global do tenant
 * Monitora eventos do tenant inteiro (novas conversas, etc)
 * Fica sempre conectado enquanto estiver na página do chat
 */
import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { toast } from 'sonner';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'wss://alreasense-backend-production.up.railway.app';

// ✅ SINGLETON global para WebSocket do tenant - garante apenas UMA conexão
// Isso previne múltiplas conexões quando useTenantSocket é chamado várias vezes
let globalWebSocket: WebSocket | null = null;
let globalWebSocketRefs: Set<() => void> = new Set(); // Callbacks para notificar todas as instâncias

// ✅ SINGLETON global para prevenir toasts duplicados ACROSS múltiplas instâncias
// Isso é necessário porque useTenantSocket pode ser chamado múltiplas vezes (React StrictMode, etc)
const globalToastRegistry = {
  shownToasts: new Set<string>(),
  
  addToast(toastKey: string): boolean {
    // ✅ Verificar e adicionar ATÔMICAMENTE
    if (this.shownToasts.has(toastKey)) {
      return false; // Já existe, retornar false
    }
    this.shownToasts.add(toastKey);
    return true; // Adicionado com sucesso
  },
  
  removeToast(toastKey: string): void {
    this.shownToasts.delete(toastKey);
  },
  
  clearAfterTimeout(toastKey: string, timeout: number): void {
    setTimeout(() => {
      this.shownToasts.delete(toastKey);
    }, timeout);
  }
};

export function useTenantSocket() {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const { addConversation, setConnectionStatus } = useChatStore();
  const { token, user } = useAuthStore();

  const handleWebSocketMessage = useCallback((data: any) => {
    console.log('📨 [TENANT WS] Mensagem recebida:', data);

    // Helper para navegar para o chat
    const navigateToChat = (conversation: any) => {
      const currentPath = window.location.pathname;
      if (currentPath === '/chat') {
        // Já está no chat, só selecionar a conversa
        const { setActiveConversation } = useChatStore.getState();
        setActiveConversation(conversation);
      } else {
        // Precisa navegar - usar pushState para não perder o estado
        const { setActiveConversation } = useChatStore.getState();
        setActiveConversation(conversation);
        window.history.pushState({}, '', '/chat');
        // Disparar evento de navegação para o React Router detectar
        window.dispatchEvent(new PopStateEvent('popstate'));
      }
    };

    switch (data.type) {
      case 'new_conversation':
        console.log('🆕 [TENANT WS] Nova conversa:', data.conversation);
        if (data.conversation) {
          addConversation(data.conversation);
          
          const contactName = data.conversation.contact_name || data.conversation.contact_phone;
          const currentPath = window.location.pathname;
          const isOnChatPage = currentPath === '/chat';
          
          // ✅ Prevenir múltiplos toasts usando registry global
          const toastKey = `new-conversation-${data.conversation.id}`;
          
          // 🔔 Toast notification - NÃO mostrar se já está na página do chat
          if (!isOnChatPage) {
            // ✅ Verificar registry global antes de mostrar
            if (globalToastRegistry.addToast(toastKey)) {
              toast.success('Nova Mensagem Recebida! 💬', {
                description: `De: ${contactName}`,
                duration: 6000,
                id: toastKey, // ✅ Usar mesmo ID para deduplicação
                action: {
                  label: 'Abrir',
                  onClick: () => navigateToChat(data.conversation)
                },
                onDismiss: () => globalToastRegistry.removeToast(toastKey),
                onAutoClose: () => globalToastRegistry.removeToast(toastKey)
              });
              
              // ✅ Limpar após 10 segundos
              globalToastRegistry.clearAfterTimeout(toastKey, 10000);
            } else {
              console.log('🔕 [TOAST] Toast já foi mostrado para nova conversa, ignorando...');
            }
          } else {
            console.log('🔕 [TOAST] Não exibido - usuário já está na página do chat');
          }
          
          // 🔔 Desktop notification (se permitido) - sempre mostrar para não perder
          if ('Notification' in window) {
            if (Notification.permission === 'granted') {
              new Notification('Nova Mensagem no Chat', {
                body: `De: ${contactName}`,
                icon: data.conversation.profile_pic_url || '/logo.png',
                badge: '/logo.png',
                tag: `chat-${data.conversation.id}`, // Evita duplicar notificações
                requireInteraction: false
              });
            } else if (Notification.permission === 'default') {
              // Pedir permissão na primeira vez (não bloqueia)
              Notification.requestPermission().then(permission => {
                console.log('🔔 [NOTIFICAÇÃO] Permissão:', permission);
              });
            }
          }
        }
        break;

      case 'attachment_updated':
        // ✅ NOVO: Tratar attachment_updated do grupo do tenant
        // Isso garante que attachments sejam atualizados mesmo se conversa não estiver aberta
        console.log('📎 [TENANT WS] Attachment atualizado:', data.data?.attachment_id);
        if (data.data?.attachment_id) {
          // Atualizar attachment via store (mesmo se conversa não estiver aberta)
          const { updateAttachment, addMessage, messages } = useChatStore.getState();
          const attachmentId = data.data.attachment_id;
          const messageId = data.data.message_id;
          
          // Buscar mensagem no store
          const messageWithAttachment = messages.find(m => 
            m.id === messageId || 
            m.attachments?.some(a => a.id === attachmentId)
          );
          
          if (messageWithAttachment) {
            // ✅ MESMA LÓGICA: Verificar se já está atualizado antes de processar
            const existingAttachment = messageWithAttachment.attachments?.find(a => a.id === attachmentId);
            const fileUrl = data.data.file_url || '';
            
            // ✅ MELHORIA: Só ignorar se:
            // 1. Attachment existe
            // 2. file_url não está vazio E é igual ao novo
            // 3. E metadata não tem flag processing (já está processado)
            const hasValidUrl = existingAttachment?.file_url && existingAttachment.file_url.trim() !== '';
            const isSameUrl = hasValidUrl && existingAttachment.file_url === fileUrl;
            const isProcessing = existingAttachment?.metadata?.processing === true;
            
            // ✅ IGNORAR apenas se tem URL válida, é a mesma URL, E não está processando
            if (existingAttachment && hasValidUrl && isSameUrl && !isProcessing) {
              console.log('ℹ️ [TENANT WS] Attachment já atualizado, ignorando update duplicado:', attachmentId);
              return;  // Já está atualizado e processado, não fazer nada
            }
            
            // ✅ Se está processando OU URL mudou OU URL estava vazia, ATUALIZAR
            console.log('🔄 [TENANT WS] Atualizando attachment:', {
              attachmentId,
              isProcessing,
              isSameUrl,
              hasValidUrl,
              oldUrl: existingAttachment?.file_url?.substring(0, 50) || 'VAZIO',
              newUrl: fileUrl?.substring(0, 50) || 'VAZIO'
            });
            
            // ✅ IMPORTANTE: Remover flag processing explicitamente
            const updatedMetadata = { ...(data.data.metadata || {}) };
            delete updatedMetadata.processing;
            
            // Atualizar attachment
            updateAttachment(attachmentId, {
              file_url: fileUrl,
              thumbnail_url: data.data.thumbnail_url,
              mime_type: data.data.mime_type,
              metadata: updatedMetadata,  // ✅ Metadata sem flag processing
            } as any);
            
            // Forçar re-render da mensagem
            const updatedMessage = {
              ...messageWithAttachment,
              attachments: messageWithAttachment.attachments?.map(att => {
                if (att.id === attachmentId) {
                  return {
                    ...att,
                    file_url: fileUrl,
                    thumbnail_url: data.data.thumbnail_url,
                    mime_type: data.data.mime_type,
                    metadata: updatedMetadata,  // ✅ Metadata sem flag processing
                  };
                }
                return att;
              })
            };
            addMessage(updatedMessage as any);
            console.log('✅ [TENANT WS] Attachment atualizado via tenant socket');
          } else {
            console.log('ℹ️ [TENANT WS] Mensagem não encontrada localmente, será atualizada quando conversa for aberta');
          }
        }
        break;

      case 'new_message_notification':
        console.log('💬 [TENANT WS] Nova mensagem em conversa existente:', data);
        if (data.conversation) {
          // Atualizar conversa na lista (mover para o topo, atualizar última mensagem)
          const { updateConversation, activeConversation } = useChatStore.getState();
          updateConversation(data.conversation);
          
          const contactName = data.conversation.contact_name || data.conversation.contact_phone;
          const messagePreview = data.message?.content || 'Nova mensagem';
          const currentPath = window.location.pathname;
          const isOnChatPage = currentPath === '/chat';
          const isActiveConversation = activeConversation?.id === data.conversation.id;
          
          // ✅ Prevenir múltiplos toasts usando registry global
          const messageId = data.message?.id || 'unknown';
          const toastKey = `new-message-${data.conversation.id}-${messageId}`;
          
          // 🔔 Toast notification - NÃO mostrar se:
          // 1. Já está na página do chat E
          // 2. É a conversa ativa (usuário já está vendo)
          if (!isOnChatPage || !isActiveConversation) {
            // ✅ Verificar registry global antes de mostrar
            if (globalToastRegistry.addToast(toastKey)) {
              toast.info('Nova Mensagem! 💬', {
                description: `${contactName}: ${messagePreview.substring(0, 50)}${messagePreview.length > 50 ? '...' : ''}`,
                duration: 5000,
                id: toastKey, // ✅ Usar mesmo ID para deduplicação
                action: {
                  label: 'Ver',
                  onClick: () => navigateToChat(data.conversation)
                },
                onDismiss: () => globalToastRegistry.removeToast(toastKey),
                onAutoClose: () => globalToastRegistry.removeToast(toastKey)
              });
              
              // ✅ Limpar após 8 segundos
              globalToastRegistry.clearAfterTimeout(toastKey, 8000);
            } else {
              console.log('🔕 [TOAST] Toast já foi mostrado para esta mensagem, ignorando...');
            }
          } else {
            console.log('🔕 [TOAST] Não exibido - usuário já está na conversa ativa');
          }
          
          // 🔔 Desktop notification - apenas se não estiver na conversa ativa
          if (!isActiveConversation && 'Notification' in window && Notification.permission === 'granted') {
            new Notification(`${contactName}`, {
              body: messagePreview.substring(0, 100),
              icon: data.conversation.profile_pic_url || '/logo.png',
              badge: '/logo.png',
              tag: `chat-msg-${data.conversation.id}`,
              requireInteraction: false
            });
          }
        }
        break;

      case 'conversation_updated':
        console.log('🔄 [TENANT WS] Conversa atualizada:', data.conversation);
        console.log('🖼️ [DEBUG] profile_pic_url:', data.conversation?.profile_pic_url);
        console.log('🖼️ [DEBUG] contact_name:', data.conversation?.contact_name);
        
        // Atualizar conversa na lista
        const { updateConversation, addConversation, conversations } = useChatStore.getState();
        if (data.conversation) {
          // ✅ Detectar se status mudou de 'closed' para 'pending' (conversa reaberta)
          const existingConversation = conversations.find(c => c.id === data.conversation.id);
          const wasClosed = existingConversation?.status === 'closed';
          const isNowPending = data.conversation.status === 'pending';
          const statusReopened = wasClosed && isNowPending;
          
          // ✅ IMPORTANTE: Se conversa não existe no store, adicionar (pode acontecer em race conditions)
          if (!existingConversation) {
            console.log('⚠️ [TENANT WS] Conversa não encontrada no store, adicionando...');
            addConversation(data.conversation);
          } else {
            console.log('✅ [TENANT WS] Chamando updateConversation...');
            updateConversation(data.conversation);
          }
          console.log('✅ [TENANT WS] Store atualizada!');
          
          // 🔔 Mostrar toast se conversa foi reaberta
          // ✅ FIX: Também mostrar se não existia no store E status é pending (nova conversa ou reaberta)
          if (statusReopened || (!existingConversation && isNowPending)) {
            const contactName = data.conversation.contact_name || data.conversation.contact_phone;
            const currentPath = window.location.pathname;
            const isOnChatPage = currentPath === '/chat';
            
            // ✅ Prevenir múltiplos toasts: só mostrar uma vez por conversa reaberta
            // Usar apenas o ID da conversa como chave (sem timestamp) para detectar duplicatas
            const toastKey = `reopened-${data.conversation.id}`;
            
            // ✅ Usar SINGLETON global para prevenir duplicatas ACROSS múltiplas instâncias do hook
            // Isso garante que mesmo se useTenantSocket for chamado múltiplas vezes, apenas 1 toast aparece
            if (!globalToastRegistry.addToast(toastKey)) {
              console.log('🔕 [TOAST] Toast já foi mostrado recentemente para esta conversa, ignorando...', toastKey);
              return; // ✅ RETORNAR DO CALLBACK COMPLETO
            }
            
            if (!isOnChatPage) {
              toast.success('Conversa Reaberta! 💬', {
                description: `${contactName} enviou uma nova mensagem`,
                duration: 5000,
                id: toastKey, // ✅ Usar mesmo ID para garantir deduplicação pelo Sonner também
                action: {
                  label: 'Abrir',
                  onClick: () => navigateToChat(data.conversation)
                },
                onDismiss: () => {
                  // ✅ Remover do registry quando toast for fechado
                  globalToastRegistry.removeToast(toastKey);
                },
                onAutoClose: () => {
                  // ✅ Remover do registry quando toast expirar
                  globalToastRegistry.removeToast(toastKey);
                }
              });
              
              // ✅ Limpar do registry após 10 segundos (backup caso callbacks não sejam chamados)
              globalToastRegistry.clearAfterTimeout(toastKey, 10000);
            } else {
              console.log('🔕 [TOAST] Não exibido - usuário já está na página do chat');
              // ✅ Remover do registry se não mostrou o toast (para permitir mostrar depois)
              globalToastRegistry.removeToast(toastKey);
            }
          }
        }
        break;

      default:
        console.log('ℹ️ [TENANT WS] Evento:', data.type);
    }
  }, [addConversation]);

  const connect = useCallback(() => {
    if (!token || !user) {
      console.log('⏸️ [TENANT WS] Aguardando autenticação...');
      return;
    }

    const tenantId = user.tenant_id;
    
    if (!tenantId) {
      console.log('⏸️ [TENANT WS] Aguardando tenant_id...');
      return;
    }

    // ✅ SINGLETON: Se já existe conexão global ativa, reutilizar
    if (globalWebSocket?.readyState === WebSocket.OPEN) {
      console.log('✅ [TENANT WS] Reutilizando conexão WebSocket global existente');
      socketRef.current = globalWebSocket;
      return;
    }

    // ✅ SINGLETON: Se já está conectando, aguardar
    if (globalWebSocket?.readyState === WebSocket.CONNECTING) {
      console.log('⏸️ [TENANT WS] Conexão global já está conectando, aguardando...');
      return;
    }

    // Não reconectar se esta instância já está conectada
    if (socketRef.current?.readyState === WebSocket.CONNECTING ||
        socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `${WS_BASE_URL}/ws/chat/tenant/${tenantId}/?token=${token}`;
    console.log('🔌 [TENANT WS] Criando nova conexão WebSocket global:', tenantId);

    try {
      const ws = new WebSocket(wsUrl);
      globalWebSocket = ws; // ✅ Guardar como singleton global
      socketRef.current = ws;

      ws.onopen = () => {
        console.log('✅ [TENANT WS] Conectado ao grupo do tenant!');
        console.log('   🔔 NOTIFICAÇÕES TOAST ATIVAS - Aguardando mensagens...');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error('❌ [TENANT WS] Erro ao parsear mensagem:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ [TENANT WS] Erro:', error);
      };

      ws.onclose = (event) => {
        console.warn('🔌 [TENANT WS] Conexão fechada:', event.code);
        socketRef.current = null;
        globalWebSocket = null; // ✅ Limpar singleton global

        // Reconectar com backoff exponencial
        if (reconnectAttemptsRef.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          console.log(`🔄 [TENANT WS] Reconectando em ${delay}ms...`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connect();
          }, delay);
        }
      };

    } catch (error) {
      console.error('❌ [TENANT WS] Erro ao criar WebSocket:', error);
    }
  }, [token, user, setConnectionStatus, handleWebSocketMessage]);

  const disconnect = useCallback(() => {
    console.log('🔌 [TENANT WS] Desconectando instância...');
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // ✅ IMPORTANTE: Não fechar conexão global aqui
    // Apenas limpar referência desta instância
    // A conexão global só fecha quando TODAS as instâncias desmontam
    socketRef.current = null;
    
    // ✅ Se esta foi a última referência, fechar conexão global
    // (Isso seria implementado com contador de refs, mas por simplicidade,
    // deixamos a conexão aberta até que todas as instâncias desmontem)
  }, []);

  // Conectar quando montar o componente
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
}

