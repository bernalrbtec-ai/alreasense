/**
 * Hook WebSocket global do tenant
 * Monitora eventos do tenant inteiro (novas conversas, etc)
 * Fica sempre conectado enquanto estiver na página do chat
 */
import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { toast } from 'sonner';
import { getDisplayName } from '../utils/phoneFormatter';

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
  const departmentsDebounceRef = useRef<NodeJS.Timeout | null>(null);

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
          
          // ✅ FIX CRÍTICO: Refetch departamentos quando nova conversa é criada com departamento
          // Isso garante que o contador do departamento seja atualizado imediatamente
          // ✅ OTIMIZAÇÃO: Usar debounce para evitar múltiplas requisições
          const { setDepartments } = useChatStore.getState();
          
          // ✅ Debounce: aguardar 500ms antes de fazer requisição (evita múltiplas requisições)
          if (departmentsDebounceRef.current) {
            clearTimeout(departmentsDebounceRef.current);
          }
          
          departmentsDebounceRef.current = setTimeout(() => {
          import('@/lib/api').then(({ api }) => {
            api.get('/auth/departments/').then(response => {
              const depts = response.data.results || response.data;
              setDepartments(depts);
            }).catch(error => {
              console.error('❌ [TENANT WS] Erro ao refetch departamentos após nova conversa:', error);
            });
          });
          }, 500); // 500ms de debounce
          
          // ✅ MELHORIA: Usar função centralizada para obter nome de exibição (nome ou telefone formatado)
          const displayName = getDisplayName(data.conversation);
          const isGroup = data.conversation.conversation_type === 'group';
          
          const currentPath = window.location.pathname;
          const isOnChatPage = currentPath === '/chat';
          
          // ✅ Prevenir múltiplos toasts usando registry global
          const toastKey = `new-conversation-${data.conversation.id}`;
          
          // 🔔 Toast notification - NÃO mostrar se já está na página do chat
          if (!isOnChatPage) {
            // ✅ Verificar registry global antes de mostrar (simplificado)
            if (globalToastRegistry.addToast(toastKey)) {
              toast.success('Nova Mensagem Recebida! 💬', {
                title: displayName, // ✅ Título mostra apenas o nome do grupo/contato
                description: isGroup ? 'Nova mensagem no grupo' : 'Nova mensagem recebida', // ✅ Descrição sem repetir nome
                duration: 3000, // ✅ Reduzido de 6s para 3s para aparecer mais rápido
                id: toastKey, // ✅ Usar mesmo ID para deduplicação
                action: {
                  label: 'Abrir',
                  onClick: () => navigateToChat(data.conversation)
                },
                onDismiss: () => globalToastRegistry.removeToast(toastKey),
                onAutoClose: () => globalToastRegistry.removeToast(toastKey)
              });
              
              // ✅ Limpar após 5 segundos (reduzido de 10s)
              globalToastRegistry.clearAfterTimeout(toastKey, 5000);
            } else {
              console.log('🔕 [TOAST] Toast já foi mostrado para nova conversa, ignorando...');
            }
          } else {
            console.log('🔕 [TOAST] Não exibido - usuário já está na página do chat');
          }
          
          // 🔔 Desktop notification (se permitido) - sempre mostrar para não perder
          if ('Notification' in window) {
            if (Notification.permission === 'granted') {
              // ✅ Para grupos e contatos: título com nome, corpo sem repetir nome
              new Notification('Nova Mensagem no Chat', {
                body: isGroup ? `Grupo: ${displayName}` : `Contato: ${displayName}`,
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
              console.log('ℹ️ [TENANT WS] Attachment já atualizado, ignorando update duplicado:', {
                attachmentId,
                oldUrl: existingAttachment?.file_url?.substring(0, 80) || 'VAZIO',
                newUrl: fileUrl?.substring(0, 80) || 'VAZIO',
                metadata: existingAttachment?.metadata
              });
              return;  // Já está atualizado e processado, não fazer nada
            }
            
            // ✅ Se está processando OU URL mudou OU URL estava vazia, ATUALIZAR
            console.log('🔄 [TENANT WS] Atualizando attachment:', {
              attachmentId,
              isProcessing,
              isSameUrl,
              hasValidUrl,
              oldUrl: existingAttachment?.file_url?.substring(0, 80) || 'VAZIO',
              newUrl: fileUrl?.substring(0, 80) || 'VAZIO',
              oldMetadata: existingAttachment?.metadata,
              newMetadata: data.data?.metadata
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

      case 'message_received':
        // ✅ FIX CRÍTICO: Handler para mensagens recebidas via WebSocket
        // Este evento é enviado quando uma nova mensagem é criada (incluindo mensagem inicial)
        console.log('💬 [TENANT WS] Mensagem recebida via WebSocket:', data);
        console.log('💬 [TENANT WS] Message conversation_id:', data.message?.conversation_id || data.message?.conversation);
        console.log('💬 [TENANT WS] Data conversation id:', data.conversation?.id);
        console.log('💬 [TENANT WS] Data conversation_id (direto):', data.conversation_id);
        console.log('💬 [TENANT WS] Active conversation id:', useChatStore.getState().activeConversation?.id);
        
        if (data.message) {
          const { addMessage, activeConversation } = useChatStore.getState();
          
          // ✅ CORREÇÃO: Verificar conversation_id em TODAS as possíveis localizações
          // Backend pode enviar: data.conversation_id OU data.message.conversation OU data.conversation.id
          const messageConversationId = data.message.conversation 
            ? String(data.message.conversation) 
            : (data.message.conversation_id ? String(data.message.conversation_id) : null);
          const dataConversationId = data.conversation?.id ? String(data.conversation.id) : null;
          const directConversationId = data.conversation_id ? String(data.conversation_id) : null;
          const activeConversationId = activeConversation?.id ? String(activeConversation.id) : null;
          
          // ✅ CORREÇÃO: Usar qualquer um dos IDs disponíveis (prioridade: direct > message > conversation)
          const finalMessageConvId = directConversationId || messageConversationId || dataConversationId;
          const isActiveConversation = activeConversationId && finalMessageConvId && (
            activeConversationId === finalMessageConvId
          );
          
          console.log('🔍 [TENANT WS] Verificando se mensagem é da conversa ativa:', {
            messageConversationId: messageConversationId,
            dataConversationId: dataConversationId,
            directConversationId: directConversationId,
            finalMessageConvId: finalMessageConvId,
            activeConversationId: activeConversationId,
            messageConversation: data.message.conversation,
            messageConversationIdField: data.message.conversation_id,
            dataConversationIdField: data.conversation_id,
            isActiveConversation
          });
          
          if (isActiveConversation) {
            console.log('✅ [TENANT WS] Mensagem é da conversa ativa, adicionando ao store...');
            addMessage(data.message);
          } else {
            console.log('ℹ️ [TENANT WS] Mensagem NÃO é da conversa ativa, NÃO adicionando ao store');
            console.log('   ⚠️ Mensagem será carregada quando a conversa correta for aberta');
          }
          
          // ✅ Atualizar conversa na lista se fornecida (sempre atualizar para unread_count)
          if (data.conversation) {
            const { updateConversation, setDepartments } = useChatStore.getState();
            console.log('🔄 [TENANT WS] Atualizando conversa com unread_count:', data.conversation.unread_count);
            updateConversation(data.conversation);
            
            // ✅ FIX CRÍTICO: Refetch departamentos quando nova mensagem chega
            // Isso garante que o contador do departamento seja atualizado em tempo real
            console.log('🔄 [TENANT WS] Nova mensagem recebida, refetching departamentos...');
            import('@/lib/api').then(({ api }) => {
              api.get('/auth/departments/').then(response => {
                const depts = response.data.results || response.data;
                setDepartments(depts);
                console.log('✅ [TENANT WS] Departamentos atualizados após nova mensagem:', depts.map((d: any) => ({
                  id: d.id,
                  name: d.name,
                  pending_count: d.pending_count
                })));
              }).catch(error => {
                console.error('❌ [TENANT WS] Erro ao refetch departamentos após nova mensagem:', error);
              });
            });
          }
        }
        break;

      case 'new_message_notification':
        console.log('💬 [TENANT WS] Nova mensagem em conversa existente:', data);
        if (data.conversation) {
          // Atualizar conversa na lista (mover para o topo, atualizar última mensagem)
          const { updateConversation, activeConversation } = useChatStore.getState();
          updateConversation(data.conversation);
          
          // ✅ MELHORIA: Para grupos, mostrar apenas o nome do grupo (sem nome do contato/sender)
          const isGroup = data.conversation.conversation_type === 'group';
          const displayName = isGroup 
            ? (data.conversation.group_metadata?.group_name || data.conversation.contact_name || 'Grupo WhatsApp')
            : (data.conversation.contact_name || data.conversation.contact_phone);
          
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
              // ✅ Para grupos e contatos: mostrar apenas mensagem na descrição (nome já está no título)
              const toastDescription = `${messagePreview.substring(0, 50)}${messagePreview.length > 50 ? '...' : ''}`;
              
              toast.info('Nova Mensagem! 💬', {
                title: displayName, // ✅ Título mostra apenas o nome do grupo/contato
                description: toastDescription, // ✅ Descrição mostra apenas a mensagem (sem repetir nome)
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
            // ✅ Para grupos e contatos: título com nome, corpo com apenas mensagem (sem repetir nome)
            new Notification(`${displayName}`, {
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
        console.log('📊 [DEBUG] unread_count:', data.conversation?.unread_count);
        console.log('📊 [DEBUG] status:', data.conversation?.status);
        console.log('📊 [DEBUG] department:', data.conversation?.department);
        
        // Atualizar conversa na lista
        const { updateConversation, addConversation, conversations, activeConversation, setMessages, setDepartments } = useChatStore.getState();
        if (data.conversation) {
          // ✅ Detectar se status mudou de 'closed' para 'pending' (conversa reaberta)
          const existingConversation = conversations.find(c => c.id === data.conversation.id);
          const wasClosed = existingConversation?.status === 'closed';
          const isNowPending = data.conversation.status === 'pending';
          const statusReopened = wasClosed && isNowPending;
          const statusChanged = existingConversation && existingConversation.status !== data.conversation.status;
          const unreadCountChanged = existingConversation && existingConversation.unread_count !== data.conversation.unread_count;
          
          // ✅ IMPORTANTE: Se conversa não existe no store, adicionar (pode acontecer em race conditions)
          const isNewConversation = !existingConversation;
          if (isNewConversation) {
            console.log('⚠️ [TENANT WS] Conversa não encontrada no store, adicionando...');
            addConversation(data.conversation);
          } else {
            console.log('✅ [TENANT WS] Chamando updateConversation...');
            updateConversation(data.conversation);
          }
          console.log('✅ [TENANT WS] Store atualizada!');
          
          // ✅ FIX CRÍTICO: SEMPRE refetch departamentos quando conversation_updated é recebido
          // Isso garante que pending_count seja atualizado em tempo real, mesmo se não houver mudanças aparentes
          // O contador pode mudar mesmo sem mudanças visíveis (ex: mensagem nova em outra conversa do mesmo depto)
          console.log('🔄 [TENANT WS] Conversa atualizada, refetching departamentos...', {
            statusChanged,
            unreadCountChanged,
            isNewConversation,
            unreadCount: data.conversation.unread_count
          });
          // Refetch departamentos para atualizar pending_count
          import('@/lib/api').then(({ api }) => {
            api.get('/auth/departments/').then(response => {
              const depts = response.data.results || response.data;
              setDepartments(depts);
              console.log('✅ [TENANT WS] Departamentos atualizados:', depts.map((d: any) => ({
                id: d.id,
                name: d.name,
                pending_count: d.pending_count
              })));
            }).catch(error => {
              console.error('❌ [TENANT WS] Erro ao refetch departamentos:', error);
            });
          });
          
          // ✅ NOVO: Se conversa atualizada é a conversa ativa E foi criada recentemente,
          // forçar re-fetch de mensagens para garantir que mensagens novas sejam carregadas
          if (activeConversation?.id === data.conversation.id && data.updated_fields) {
            const updatedName = data.updated_fields.includes('contact_name');
            const updatedMetadata = data.updated_fields.includes('group_metadata');
            
            // Se nome ou metadados foram atualizados, pode ser que conversa estava vazia antes
            // Forçar re-fetch de mensagens após 500ms
            if (updatedName || updatedMetadata) {
              console.log('🔄 [TENANT WS] Conversa ativa atualizada (nome/metadados), re-fetch de mensagens em 500ms...');
              setTimeout(async () => {
                try {
                  const { api } = await import('@/lib/api');
                  const response = await api.get(`/chat/conversations/${data.conversation.id}/messages/`, {
                    params: { ordering: 'created_at' }
                  });
                  const msgs = response.data.results || response.data;
                  if (msgs.length > 0) {
                    console.log(`✅ [TENANT WS] Re-fetch encontrou ${msgs.length} mensagem(ns)!`);
                    setMessages(msgs);
                  }
                } catch (error) {
                  console.error('❌ [TENANT WS] Erro no re-fetch de mensagens:', error);
                }
              }, 500);
            }
          }
          
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

      case 'message_reaction_update':
        console.log('ℹ️ [TENANT WS] Evento: message_reaction_update');
        if (data.message) {
          const { updateMessageReactions, activeConversation } = useChatStore.getState();
          
          // ✅ CORREÇÃO: Verificar se mensagem pertence à conversa ativa antes de atualizar
          const messageConversationId = data.message.conversation 
            ? String(data.message.conversation) 
            : (data.conversation_id ? String(data.conversation_id) : null);
          const activeConversationId = activeConversation?.id ? String(activeConversation.id) : null;
          
          // Só atualizar se mensagem pertence à conversa ativa OU se não há conversa ativa (pode ser mensagem de outra conversa)
          // Mas sempre atualizar se conversation_id bater (mensagem está na conversa ativa)
          if (activeConversationId && messageConversationId && messageConversationId === activeConversationId) {
            console.log('👍 [TENANT WS] Reação atualizada (conversa ativa):', data.message.id, data.reaction);
            updateMessageReactions(
              data.message.id,
              data.message.reactions || [],
              data.message.reactions_summary || {}
            );
          } else if (!activeConversationId) {
            // Se não há conversa ativa, atualizar de qualquer forma (pode ser necessário para outras conversas)
            console.log('👍 [TENANT WS] Reação atualizada (sem conversa ativa):', data.message.id, data.reaction);
            updateMessageReactions(
              data.message.id,
              data.message.reactions || [],
              data.message.reactions_summary || {}
            );
          } else {
            console.log('ℹ️ [TENANT WS] Reação atualizada ignorada (mensagem não pertence à conversa ativa):', {
              messageId: data.message.id,
              messageConversationId,
              activeConversationId
            });
          }
        }
        break;

      case 'campaign_update':
        // ✅ NOVO: Handler para atualizações de campanha via WebSocket
        console.log('📡 [TENANT WS] Evento: campaign_update', data);
        // O backend envia: { type: 'campaign_update', data: payload, timestamp }
        // O consumer espera: event.get('payload', {})
        const campaignPayload = data.data || data.payload || data;
        if (campaignPayload && campaignPayload.campaign_id) {
          // Disparar evento customizado para que CampaignsPage possa escutar
          const customEvent = new CustomEvent('campaign_update', {
            detail: campaignPayload
          });
          window.dispatchEvent(customEvent);
          console.log('📡 [TENANT WS] Evento customizado disparado para campanha:', campaignPayload.campaign_id);
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

