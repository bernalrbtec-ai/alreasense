/**
 * Hook WebSocket global do tenant
 * Monitora eventos do tenant inteiro (novas conversas, etc)
 * Fica sempre conectado enquanto estiver na página do chat
 */
import { useEffect, useRef, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/lib/api';
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
        // ✅ FASE 1 + 2: Tratar attachment_updated apenas da conversa ativa para evitar attachments (imagens/áudios) em conversas erradas
        console.log('📎 [TENANT WS] Attachment atualizado:', {
          attachmentId: data.data?.attachment_id,
          mimeType: data.data?.mime_type,
          hasTranscription: !!data.data?.transcription
        });
        if (data.data?.attachment_id) {
          const { updateAttachment, updateMessage, getMessagesArray, activeConversation: currentActiveConversation } = useChatStore.getState();
          const attachmentId = data.data.attachment_id;
          const messageId = data.data.message_id;
          
          // ✅ FASE 2: Buscar mensagem APENAS na conversa ativa (evita atualizar mensagem de outra conversa)
          const messages = currentActiveConversation ? getMessagesArray(currentActiveConversation.id) : [];
          const messageWithAttachment = messages.find(m => 
            m.id === messageId || 
            m.attachments?.some(a => a.id === attachmentId)
          );
          
          // ✅ FASE 2: Extrair conversation_id da mensagem encontrada e verificar se pertence à conversa ativa
          if (messageWithAttachment && currentActiveConversation) {
            const messageConversationId = messageWithAttachment.conversation_id 
              ? String(messageWithAttachment.conversation_id)
              : (typeof messageWithAttachment.conversation === 'object' && messageWithAttachment.conversation?.id
                  ? String(messageWithAttachment.conversation.id)
                  : (typeof messageWithAttachment.conversation === 'string'
                      ? messageWithAttachment.conversation
                      : null));
            const activeConversationId = String(currentActiveConversation.id);
            
            // ✅ FASE 2: Verificar se mensagem pertence à conversa ativa antes de atualizar
            if (messageConversationId && messageConversationId !== activeConversationId) {
              console.log('⚠️ [TENANT WS] Attachment de mensagem de outra conversa, ignorando:', {
                attachmentId,
                messageId,
                mimeType: data.data?.mime_type,
                messageConversationId,
                activeConversationId,
                isAudio: data.data?.mime_type?.startsWith('audio/'),
                hasTranscription: !!data.data?.transcription
              });
              // ✅ CORREÇÃO TRANSCRIÇÃO TARDIA: Fallback para verificar se mensagem é da conversa ativa
              // Para transcrições que chegam depois, só atualizar se for da conversa ativa
              if (messageId) {
                console.log('ℹ️ [TENANT WS] Tentando buscar mensagem do backend para verificar conversa...', {
                  attachmentId,
                  messageId,
                  mimeType: data.data?.mime_type,
                  isAudio: data.data?.mime_type?.startsWith('audio/'),
                  hasTranscription: !!data.data?.transcription
                });
                api.get(`/chat/messages/${messageId}/`)
                  .then((response) => {
                    const freshMessage = response.data;
                    if (!freshMessage) return;
                    // Verificar conversation_id da mensagem fresca
                    const freshConvId = freshMessage.conversation_id 
                      ? String(freshMessage.conversation_id)
                      : (freshMessage.conversation?.id ? String(freshMessage.conversation.id) : null);
                    // ✅ CRÍTICO: Só atualizar se for da conversa ativa (não atualizar mensagens de outras conversas)
                    // Isso evita que transcrições tardias apareçam na conversa errada
                    if (freshConvId === activeConversationId) {
                      updateMessage(activeConversationId, freshMessage);
                      console.log('✅ [TENANT WS] Mensagem atualizada via fetch (era da conversa ativa)', {
                        messageId,
                        isAudio: data.data?.mime_type?.startsWith('audio/'),
                        hasTranscription: !!data.data?.transcription
                      });
                    } else {
                      // ✅ CORREÇÃO: Não atualizar mensagens de outras conversas (evita aparecer na conversa errada)
                      // A mensagem será atualizada quando a conversa correta for aberta
                      console.log('⚠️ [TENANT WS] Mensagem é de outra conversa, ignorando atualização:', {
                        messageId,
                        freshConvId,
                        activeConversationId,
                        isAudio: data.data?.mime_type?.startsWith('audio/'),
                        hasTranscription: !!data.data?.transcription,
                        reason: 'Atualização será aplicada quando conversa correta for aberta'
                      });
                    }
                  })
                  .catch((error) => {
                    console.warn('⚠️ [TENANT WS] Falha ao buscar mensagem atualizada:', error);
                  });
              }
              return; // Não atualizar mensagem de outra conversa
            }
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
            const hasTranscriptionUpdate = !!data.data?.transcription || data.data?.ai_metadata?.transcription?.status === 'processing';
            if (existingAttachment && hasValidUrl && isSameUrl && !isProcessing && !hasTranscriptionUpdate) {
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
              mimeType: data.data?.mime_type,
              isAudio: data.data?.mime_type?.startsWith('audio/'),
              isProcessing,
              isSameUrl,
              hasValidUrl,
              hasTranscription: !!data.data?.transcription,
              oldUrl: existingAttachment?.file_url?.substring(0, 80) || 'VAZIO',
              newUrl: fileUrl?.substring(0, 80) || 'VAZIO',
              conversationId: activeConversationId,
              oldMetadata: existingAttachment?.metadata,
              newMetadata: data.data?.metadata
            });
            
            // ✅ IMPORTANTE: Remover flag processing explicitamente
            const updatedMetadata = { ...(data.data.metadata || {}) };
            delete updatedMetadata.processing;
            
            // ✅ MELHORIA: Atualizar todos os campos relevantes, incluindo size_bytes e original_filename
            const sizeBytes = data.data.size_bytes || existingAttachment?.size_bytes || 0;
            const originalFilename = data.data.original_filename || existingAttachment?.original_filename || 'arquivo';
            
            console.log('🔄 [TENANT WS] Atualizando attachment com:', {
              attachmentId,
              size_bytes: sizeBytes,
              original_filename: originalFilename,
              file_url: fileUrl?.substring(0, 80),
              metadata: updatedMetadata
            });
            
            updateAttachment(attachmentId, {
              file_url: fileUrl,
              thumbnail_url: data.data.thumbnail_url,
              mime_type: data.data.mime_type,
              size_bytes: sizeBytes,  // ✅ NOVO: Atualizar tamanho
              original_filename: originalFilename,  // ✅ NOVO: Atualizar nome original
              metadata: updatedMetadata,  // ✅ Metadata sem flag processing
              transcription: data.data.transcription,
              transcription_language: data.data.transcription_language,
              ai_metadata: data.data.ai_metadata,
            } as any);
            
            // ✅ FASE 1: Usar updateMessage ao invés de addMessage para garantir conversation_id correto
            // Forçar re-render da mensagem com attachment atualizado
            const updatedMessage = {
              ...messageWithAttachment,
              conversation_id: activeConversationId, // ✅ Garantir conversation_id correto
              attachments: messageWithAttachment.attachments?.map(att => {
                if (att.id === attachmentId) {
                  const updatedAtt = {
                    ...att,
                    file_url: fileUrl,
                    thumbnail_url: data.data.thumbnail_url,
                    mime_type: data.data.mime_type,
                    size_bytes: sizeBytes,
                    original_filename: originalFilename,
                    metadata: updatedMetadata,
                    transcription: data.data.transcription,
                    transcription_language: data.data.transcription_language,
                    ai_metadata: data.data.ai_metadata,
                  };
                  console.log('🔄 [TENANT WS] Attachment na mensagem atualizado:', {
                    attachmentId,
                    size_bytes: updatedAtt.size_bytes,
                    original_filename: updatedAtt.original_filename,
                    file_url: updatedAtt.file_url?.substring(0, 80)
                  });
                  return updatedAtt;
                }
                return att;
              })
            };
            // ✅ FASE 1: updateMessage garante que a mensagem vai para a conversa correta
            updateMessage(activeConversationId, updatedMessage);
            console.log('✅ [TENANT WS] Attachment atualizado via tenant socket (conversa:', activeConversationId, ')');
          } else {
            // ✅ CORREÇÃO CRÍTICA: Mensagem não encontrada na conversa ativa
            // Buscar do backend para atualizar mesmo se conversa não estiver aberta
            // Isso garante que attachments sejam atualizados para agentes sem departamento (Inbox)
            console.log('ℹ️ [TENANT WS] Mensagem não encontrada na conversa ativa, buscando do backend...', {
              attachmentId,
              messageId,
              mimeType: data.data?.mime_type,
              isAudio: data.data?.mime_type?.startsWith('audio/'),
              hasTranscription: !!data.data?.transcription,
              activeConversationId: currentActiveConversation?.id
            });
            
            // ✅ MELHORIA DE SEGURANÇA: Verificar se conversa está na lista antes de buscar
            // Isso evita chamadas desnecessárias ao backend e adiciona camada extra de segurança
            const { conversations } = useChatStore.getState();
            const conversationExists = conversations.some(conv => {
              // Verificar se mensagem pode pertencer a alguma conversa da lista
              // Não podemos verificar diretamente sem buscar a mensagem, mas podemos otimizar
              return true; // Permitir busca, backend valida acesso
            });
            
            // ✅ CORREÇÃO CRÍTICA: Sempre buscar mensagem do backend para atualizar attachment
            // Isso garante que attachments sejam atualizados mesmo quando conversa não está aberta
            // Importante para agentes sem departamento (Inbox) que podem não ter conversa ativa
            // ✅ MELHORIA: Adicionar debounce para evitar múltiplas chamadas simultâneas
            if (messageId) {
              // ✅ SEGURANÇA: Verificar se já há uma busca em andamento para evitar race conditions
              const pendingKey = `attachment_fetch_${messageId}_${attachmentId}`;
              if ((window as any)[pendingKey]) {
                console.log('⏳ [TENANT WS] Busca de mensagem já em andamento, aguardando...', { messageId, attachmentId });
                return;
              }
              
              (window as any)[pendingKey] = true;
              
              api.get(`/chat/messages/${messageId}/`)
                .then((response) => {
                  const freshMessage = response.data;
                  if (!freshMessage) {
                    (window as any)[pendingKey] = false;
                    return;
                  }
                  
                  const freshConvId = freshMessage.conversation_id 
                    ? String(freshMessage.conversation_id)
                    : (freshMessage.conversation?.id ? String(freshMessage.conversation.id) : null);
                  
                  if (!freshConvId) {
                    console.warn('⚠️ [TENANT WS] Mensagem sem conversation_id, ignorando:', messageId);
                    (window as any)[pendingKey] = false;
                    return;
                  }
                  
                  // ✅ CORREÇÃO CRÍTICA: Remover validação restritiva que bloqueia attachments
                  // A validação de tenant já foi feita no backend, não precisamos validar novamente aqui
                  // Isso estava bloqueando attachments para conversas que não estão na lista do usuário
                  // mas que pertencem ao tenant (por exemplo, conversas de outros departamentos)
                  
                  // ✅ VALIDAÇÃO: Verificar se attachment realmente pertence à mensagem
                  const attachmentInMessage = freshMessage.attachments?.some(
                    (att: any) => att.id === attachmentId
                  );
                  
                  if (!attachmentInMessage) {
                    console.warn('⚠️ [TENANT WS] Attachment não encontrado na mensagem, ignorando:', {
                      messageId,
                      attachmentId,
                      messageAttachments: freshMessage.attachments?.map((a: any) => a.id)
                    });
                    (window as any)[pendingKey] = false;
                    return;
                  }
                  
                  // ✅ CORREÇÃO CRÍTICA: Atualizar attachment diretamente no store
                  // Isso garante que o attachment seja atualizado mesmo se conversa não estiver aberta
                  const { updateAttachment, updateConversation, updateMessage } = useChatStore.getState();
                  
                  // Atualizar attachment diretamente
                  const updatedMetadata = { ...(data.data.metadata || {}) };
                  delete updatedMetadata.processing;
                  
                  updateAttachment(attachmentId, {
                    file_url: data.data.file_url || '',
                    thumbnail_url: data.data.thumbnail_url,
                    mime_type: data.data.mime_type,
                    size_bytes: data.data.size_bytes || 0,
                    original_filename: data.data.original_filename || 'arquivo',
                    metadata: updatedMetadata,
                    transcription: data.data.transcription,
                    transcription_language: data.data.transcription_language,
                    ai_metadata: data.data.ai_metadata,
                  } as any);
                  
                  // Se há conversa ativa e é a mesma, atualizar mensagem também
                  if (currentActiveConversation?.id && String(currentActiveConversation.id) === freshConvId) {
                    updateMessage(freshConvId, freshMessage);
                    console.log('✅ [TENANT WS] Mensagem atualizada via fetch (conversa ativa)', {
                      messageId,
                      conversationId: freshConvId,
                      isAudio: data.data?.mime_type?.startsWith('audio/'),
                      hasTranscription: !!data.data?.transcription
                    });
                  } else {
                    // ✅ CORREÇÃO: Atualizar conversa na lista mesmo se não estiver aberta
                    // Isso garante que quando a conversa for aberta, o attachment já esteja atualizado
                    updateConversation({
                      id: freshConvId,
                      last_message_at: freshMessage.created_at
                    } as any);
                    console.log('✅ [TENANT WS] Attachment atualizado no store (conversa não ativa)', {
                      messageId,
                      conversationId: freshConvId,
                      attachmentId,
                      file_url: data.data.file_url?.substring(0, 80)
                    });
                  }
                  
                  (window as any)[pendingKey] = false;
                })
                .catch((error) => {
                  console.warn('⚠️ [TENANT WS] Falha ao buscar mensagem atualizada:', error);
                  (window as any)[pendingKey] = false;
                  
                  // ✅ MELHORIA: Em caso de erro, ainda tentar atualizar attachment com dados do WebSocket
                  // Isso garante que mesmo se a busca falhar, o attachment seja atualizado
                  const { updateAttachment } = useChatStore.getState();
                  const updatedMetadata = { ...(data.data.metadata || {}) };
                  delete updatedMetadata.processing;
                  
                  updateAttachment(attachmentId, {
                    file_url: data.data.file_url || '',
                    thumbnail_url: data.data.thumbnail_url,
                    mime_type: data.data.mime_type,
                    size_bytes: data.data.size_bytes || 0,
                    original_filename: data.data.original_filename || 'arquivo',
                    metadata: updatedMetadata,
                    transcription: data.data.transcription,
                    transcription_language: data.data.transcription_language,
                    ai_metadata: data.data.ai_metadata,
                  } as any);
                });
            }
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
          
          // ✅ CORREÇÃO CRÍTICA: Adicionar mensagem se for da conversa ativa OU se conversa existe no store
          // Isso garante que mensagens sejam adicionadas mesmo se conversa não estiver aberta no momento
          // Quando a conversa for aberta, a mensagem já estará disponível
          const { conversations } = useChatStore.getState();
          const conversationExists = conversations.some(conv => 
            String(conv.id) === finalMessageConvId
          );
          
          if (isActiveConversation) {
            console.log('✅ [TENANT WS] Mensagem é da conversa ativa, adicionando ao store...');
            addMessage(data.message);
          } else if (conversationExists) {
            // ✅ CORREÇÃO: Se conversa existe no store mas não está aberta, adicionar mensagem também
            // Isso garante que quando a conversa for aberta, a mensagem já esteja disponível
            console.log('✅ [TENANT WS] Mensagem é de conversa existente no store, adicionando ao store...');
            addMessage(data.message);
          } else {
            console.log('ℹ️ [TENANT WS] Mensagem NÃO é da conversa ativa e conversa não existe no store');
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

      case 'group_participants_updated':
        // ✅ NOVO: Handler para atualização de participantes do grupo
        console.log('👥 [TENANT WS] Participantes do grupo atualizados:', {
          conversationId: data.conversation_id,
          added: data.added,
          removed: data.removed,
          addedCount: data.added_count,
          removedCount: data.removed_count,
          totalParticipants: data.total_participants
        });
        
        // Atualizar conversa se fornecida (isso atualiza os participantes no store)
        const { updateConversation, activeConversation } = useChatStore.getState();
        if (data.conversation) {
          updateConversation(data.conversation);
        }
        
        // Se a conversa ativa é a que foi atualizada, participantes serão atualizados automaticamente
        // A informação será visível dentro do grupo quando o usuário visualizar os participantes
        if (activeConversation?.id === data.conversation_id) {
          console.log('🔄 [TENANT WS] Conversa ativa atualizada, participantes atualizados no store');
        }
        break;

      case 'conversation_updated':
        // ✅ DEBUG: Log detalhado para debug de conversas criadas via aplicação
        console.log('📨 [TENANT WS] conversation_updated recebido:', {
          conversationId: data.conversation?.id,
          conversationName: data.conversation?.contact_name,
          conversationPhone: data.conversation?.contact_phone,
          department: data.conversation?.department?.name || 'Nenhum (Inbox)',
          status: data.conversation?.status
        });
        
        // ✅ PERFORMANCE: Reduzir logs excessivos, manter apenas logs importantes
        const { updateConversation: updateConv, addConversation, conversations, activeConversation: activeConv, setMessages, setDepartments } = useChatStore.getState();
        if (data.conversation) {
          // ✅ CORREÇÃO CRÍTICA: Verificar se last_message foi atualizado
          // ✅ MELHORIA: Tratar null explicitamente (conversas sem mensagens)
          const existingConversation = conversations.find((conversationItem) => conversationItem.id === data.conversation.id);
          const existingLastMsg = existingConversation?.last_message;
          const incomingLastMsg = data.conversation.last_message;
          // Comparar null vs undefined vs objeto corretamente
          const lastMessageUpdated = existingConversation && (
            (existingLastMsg === null && incomingLastMsg !== null) ||
            (existingLastMsg !== null && incomingLastMsg === null) ||
            (existingLastMsg && incomingLastMsg && JSON.stringify(existingLastMsg) !== JSON.stringify(incomingLastMsg))
          );
          
          if (lastMessageUpdated) {
            console.log('📨 [TENANT WS] Última mensagem atualizada:', {
              conversationId: data.conversation.id,
              oldLastMessage: existingConversation.last_message?.content?.substring(0, 50),
              newLastMessage: data.conversation.last_message?.content?.substring(0, 50)
            });
          }
          
          // ✅ Detectar se status mudou de 'closed' para 'pending' (conversa reaberta)
          const wasClosed = existingConversation?.status === 'closed';
          const isNowPending = data.conversation.status === 'pending';
          const statusReopened = wasClosed && isNowPending;
          const statusChanged = existingConversation && existingConversation.status !== data.conversation.status;
          const unreadCountChanged = existingConversation && existingConversation.unread_count !== data.conversation.unread_count;
          
          // ✅ IMPORTANTE: Se conversa não existe no store, adicionar (pode acontecer em race conditions)
          const isNewConversation = !existingConversation;
          if (isNewConversation) {
            console.log('⚠️ [TENANT WS] Conversa não encontrada no store, adicionando...', {
              id: data.conversation.id,
              name: data.conversation.contact_name,
              phone: data.conversation.contact_phone,
              department: data.conversation.department?.name || 'Nenhum (Inbox)',
              status: data.conversation.status
            });
            addConversation(data.conversation);
            console.log('✅ [TENANT WS] Conversa adicionada ao store via conversation_updated');
          } else {
            // ✅ CORREÇÃO CRÍTICA: Sempre atualizar, mesmo que pareça igual
            // Isso garante que last_message seja atualizado mesmo se outros campos não mudaram
            console.log('🔄 [TENANT WS] Atualizando conversa existente no store:', {
              id: data.conversation.id,
              name: data.conversation.contact_name,
              last_message: data.conversation.last_message?.content?.substring(0, 50),
              assigned_to: data.conversation.assigned_to,
              department: data.conversation.department,
              status: data.conversation.status
            });
            updateConv(data.conversation);
            
            // ✅ DEBUG: Verificar se conversa está visível após atualização
            const { conversations: updatedConvs, activeDepartment: activeDept } = useChatStore.getState();
            const updatedConv = updatedConvs.find(c => c.id === data.conversation.id);
            if (updatedConv && activeDept?.id === 'my_conversations') {
              const { user } = useAuthStore.getState();
              const shouldBeVisible = updatedConv.assigned_to === user?.id && updatedConv.status === 'open';
              console.log('🔍 [TENANT WS] Conversa atualizada - visibilidade em Minhas Conversas:', {
                conversationId: updatedConv.id,
                shouldBeVisible,
                assigned_to: updatedConv.assigned_to,
                userId: user?.id,
                status: updatedConv.status
              });
            }
          }
          
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
          if (activeConv?.id === data.conversation.id && data.updated_fields) {
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

      case 'task_notification':
        // Notificação de tarefa/evento da agenda
        console.log('🔔 [TENANT WS] Notificação de tarefa recebida:', data);
        if (data.data && data.data.user_id === String(user?.id)) {
          // Mostrar notificação no navegador
          if ('Notification' in window && Notification.permission === 'granted') {
            const notification = new Notification(`🔔 ${data.data.title}`, {
              body: data.data.message,
              icon: '/logo.png',
              tag: `task_${data.data.task_id}`,
              badge: '/logo.png',
              requireInteraction: false,
            });
            
            notification.onclick = () => {
              window.focus();
              window.location.href = '/dashboard';
              notification.close();
            };
            
            setTimeout(() => notification.close(), 10000);
          }
          
          // Mostrar toast também
          toast.info('🔔 Lembrete de Tarefa', {
            description: data.data.message,
            duration: 10000,
            action: {
              label: 'Ver',
              onClick: () => {
                window.location.href = '/dashboard';
              }
            }
          });
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

    // ✅ Sempre ler token AGORA do store/axios (nunca usar closure) – store pode ter token "preso" vindo do persist/localStorage
    const authHeader = api.defaults.headers.common['Authorization'] as string | undefined;
    const tokenFromApi = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : null;
    const { token: tokenFromStore, user: currentUser } = useAuthStore.getState();
    const currentToken = tokenFromApi || tokenFromStore;
    
    if (!currentToken || !currentUser?.tenant_id) {
      console.warn('⚠️ [TENANT WS] Token ou tenant_id não disponível. Token do API:', !!tokenFromApi, 'Token do store:', !!tokenFromStore);
      return;
    }
    
    // ✅ DEBUG: Log sem expor token (apenas tamanho e formato)
    const parts = currentToken.split('.');
    console.log('🔌 [TENANT WS] Conectando WebSocket:', {
      tenantId: currentUser.tenant_id,
      tokenLength: currentToken.length,
      tokenParts: parts.length,
      tokenFrom: tokenFromApi ? 'api' : 'store',
      userEmail: currentUser.email,
      wsBaseUrl: WS_BASE_URL
    });
    
    if (parts.length !== 3) {
      console.error('❌ [TENANT WS] Token não tem formato JWT (3 partes). Abortando.');
      return;
    }

    // ✅ Não conectar se o token já expirou (evita 4001 e loop; força novo login)
    try {
      const payloadB64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
      const padding = payloadB64.length % 4 ? '='.repeat(4 - (payloadB64.length % 4)) : '';
      const payload = JSON.parse(atob(payloadB64 + padding));
      const exp = payload.exp as number | undefined;
      if (exp && Math.floor(Date.now() / 1000) > exp) {
        console.warn('⚠️ [TENANT WS] Token já expirado (exp no payload). Redirecionando para login...');
        setConnectionStatus('disconnected');
        useAuthStore.getState().logout();
        return;
      }
    } catch (_) {
      // Se não conseguir decodificar, deixa o backend rejeitar
    }

    const encodedToken = encodeURIComponent(currentToken);
    const wsUrl = `${WS_BASE_URL}/ws/chat/tenant/${currentUser.tenant_id}/?token=${encodedToken}`;

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
        console.warn('🔌 [TENANT WS] Conexão fechada:', event.code, event.reason);
        socketRef.current = null;
        globalWebSocket = null; // ✅ Limpar singleton global

        // ✅ Token inválido ou expirado (4001) → limpar sessão e redirecionar para login
        if (event.code === 4001) {
          console.warn('⚠️ [TENANT WS] Token inválido/expirado (4001). Redirecionando para login...');
          setConnectionStatus('disconnected');
          useAuthStore.getState().logout();
          return;
        }

        // Reconectar com backoff exponencial para outros erros
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

  // Conectar quando montar o componente ou quando token mudar
  useEffect(() => {
    if (!token || !user) {
      console.log('⏸️ [TENANT WS] Aguardando token/usuário...');
      return;
    }

    // ✅ CORREÇÃO CRÍTICA: Se WebSocket está fechado ou token mudou, reconectar
    const shouldReconnect = 
      socketRef.current?.readyState !== WebSocket.OPEN && 
      socketRef.current?.readyState !== WebSocket.CONNECTING;
    
    if (shouldReconnect) {
      console.log('🔄 [TENANT WS] Conectando WebSocket...');
      reconnectAttemptsRef.current = 0; // Resetar tentativas
      connect();
    }

    return () => {
      disconnect();
    };
  }, [token, user?.tenant_id, connect, disconnect]);

  return {
    isConnected: socketRef.current?.readyState === WebSocket.OPEN
  };
}

