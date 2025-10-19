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
          
          // 🔔 Toast notification - sempre mostrar
          toast.success('Nova Mensagem Recebida! 💬', {
            description: `De: ${contactName}`,
            duration: 6000,
            action: {
              label: 'Abrir',
              onClick: () => navigateToChat(data.conversation)
            }
          });
          
          // 🔔 Desktop notification (se permitido)
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

      case 'new_message_notification':
        console.log('💬 [TENANT WS] Nova mensagem em conversa existente:', data);
        if (data.conversation) {
          // Atualizar conversa na lista (mover para o topo, atualizar última mensagem)
          const { updateConversation } = useChatStore.getState();
          updateConversation(data.conversation);
          
          const contactName = data.conversation.contact_name || data.conversation.contact_phone;
          const messagePreview = data.message?.content || 'Nova mensagem';
          
          // 🔔 Toast notification
          toast.info('Nova Mensagem! 💬', {
            description: `${contactName}: ${messagePreview.substring(0, 50)}${messagePreview.length > 50 ? '...' : ''}`,
            duration: 5000,
            action: {
              label: 'Ver',
              onClick: () => navigateToChat(data.conversation)
            }
          });
          
          // 🔔 Desktop notification
          if ('Notification' in window && Notification.permission === 'granted') {
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
        // Atualizar conversa na lista
        const { updateConversation } = useChatStore.getState();
        if (data.conversation) {
          updateConversation(data.conversation);
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

    // Não reconectar se já está conectando/conectado
    if (socketRef.current?.readyState === WebSocket.CONNECTING ||
        socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = `${WS_BASE_URL}/ws/chat/tenant/${tenantId}/?token=${token}`;
    console.log('🔌 [TENANT WS] Conectando ao grupo do tenant:', tenantId);

    try {
      const ws = new WebSocket(wsUrl);
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
    console.log('🔌 [TENANT WS] Desconectando...');
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
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

