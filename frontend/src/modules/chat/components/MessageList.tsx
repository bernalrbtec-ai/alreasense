/**
 * Lista de mensagens - Estilo WhatsApp Web com UX Moderna
 * ✅ PERFORMANCE: Componente memoizado para evitar re-renders desnecessários
 */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Check, CheckCheck, Clock, Download, FileText, Image as ImageIcon, Video, Music, Reply, AlertCircle, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import { format } from 'date-fns';
import type { MessageAttachment, MessageReaction } from '../types';
import { AttachmentPreview } from './AttachmentPreview';
import { useUserAccess } from '@/hooks/useUserAccess';
import { sortMessagesByTimestamp } from '../utils/messageUtils';
import { useAuthStore } from '@/stores/authStore';
import { MessageContextMenu } from './MessageContextMenu';
import type { Message } from '../types';
import ContactModal from '@/components/contacts/ContactModal';
import { MentionRenderer } from './MentionRenderer';
import { SharedContactCard } from './SharedContactCard';
import { LocationCard } from './LocationCard';
import { MessageInfoModal } from './MessageInfoModal';
import { ForwardMessageModal } from './ForwardMessageModal';
import { EditMessageModal } from './EditMessageModal';
import { formatWhatsAppTextWithLinks } from '../utils/whatsappFormatter';
import { EmojiPicker } from './EmojiPicker';
import { parseMessageSignature } from '../utils/signatureParser';

type ReactionsSummary = NonNullable<Message['reactions_summary']>;

// ✅ CORREÇÃO: Renomear reaction para reactionItem para evitar conflito de minificação
const cloneReactions = (reactions?: MessageReaction[] | null): MessageReaction[] =>
  reactions
    ? reactions.map((reactionItem) => ({
        ...reactionItem,
        user_data: reactionItem.user_data ? { ...reactionItem.user_data } : undefined,
      }))
    : [];

/** Normaliza ID para comparação (string, lowercase, trim) */
function normalizeMessageId(id: string | undefined | null): string {
  if (id == null) return '';
  return String(id).trim().toLowerCase();
}

/**
 * ✅ NOVO: Componente para preview de mensagem respondida (reply)
 * Busca automaticamente a mensagem original se não estiver na lista ou sem conteúdo
 */
function ReplyPreview({ replyToId, messages }: { replyToId: string; messages: Message[] }) {
  const replyIdNorm = normalizeMessageId(replyToId);
  const [repliedMessage, setRepliedMessage] = useState<Message | null>(() => {
    const found = messages.find((m) => normalizeMessageId(m.id) === replyIdNorm);
    return found || null;
  });
  const [isLoadingOriginal, setIsLoadingOriginal] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);
  const { addMessage } = useChatStore();

  // Reset quando muda a mensagem sendo respondida (ex.: troca de conversa). Não resetar se id vazio.
  useEffect(() => {
    if (!replyIdNorm) return;
    const found = messages.find((m) => normalizeMessageId(m.id) === replyIdNorm);
    setRepliedMessage(found || null);
    setHasFetched(false);
  }, [replyIdNorm]);

  const needsFetch =
    !isLoadingOriginal &&
    (!repliedMessage || ((repliedMessage.content == null || repliedMessage.content === '') && !repliedMessage.attachments?.length));

  // Buscar mensagem original se não estiver na lista ou se estiver sem conteúdo (ex.: mensagem vinda do WS sem content)
  useEffect(() => {
    if (!needsFetch || hasFetched || !replyToId?.trim()) return;
    setHasFetched(true);
    setIsLoadingOriginal(true);
    api
      .get(`/chat/messages/${replyToId.trim()}/`)
      .then((response) => {
        const originalMsg = response.data;
        setRepliedMessage(originalMsg);
        if (!messages.find((m) => normalizeMessageId(m.id) === normalizeMessageId(originalMsg.id))) {
          addMessage(originalMsg);
        }
      })
      .catch((error) => {
        console.error('❌ [REPLY] Erro ao buscar mensagem original:', error);
        setHasFetched(false);
      })
      .finally(() => {
        setIsLoadingOriginal(false);
      });
  }, [replyToId, needsFetch, hasFetched, messages, addMessage]);

  // Atualizar repliedMessage quando a lista tiver a mensagem com conteúdo e nós ainda não tivermos conteúdo
  useEffect(() => {
    if (!replyIdNorm) return;
    const hasContent = repliedMessage?.content != null && repliedMessage.content !== '';
    if (hasContent) return;
    const fromList = messages.find((m) => normalizeMessageId(m.id) === replyIdNorm);
    if (fromList && (fromList.content != null && fromList.content !== '' || (fromList.attachments?.length ?? 0) > 0)) {
      setRepliedMessage(fromList);
    }
  }, [messages, replyIdNorm, repliedMessage?.content]);

  // Id vazio: não buscar nem mostrar preview completo (após todos os hooks para não quebrar regras do React)
  if (!replyIdNorm) {
    return (
      <div className="mb-2 pl-3 border-l-4 border-l-gray-400 bg-gray-50 dark:bg-gray-800 rounded-r-lg py-1.5">
        <p className="text-xs text-gray-500 dark:text-gray-400">Resposta</p>
      </div>
    );
  }

  if (isLoadingOriginal) {
    return (
      <div className="mb-2 pl-3 border-l-4 border-l-gray-300 bg-gray-50 dark:bg-gray-800 rounded-r-lg py-1.5">
        <div className="flex items-center gap-1 mb-0.5">
          <Reply className="w-3 h-3 text-gray-400 animate-pulse" />
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">
            Carregando mensagem original...
          </p>
        </div>
      </div>
    );
  }
  
  if (!repliedMessage) {
    // ✅ FALLBACK: Se mensagem não encontrada, mostrar mensagem genérica
    return (
      <div className="mb-2 pl-3 border-l-4 border-l-gray-400 bg-gray-50 dark:bg-gray-800 rounded-r-lg py-1.5">
        <div className="flex items-center gap-1 mb-0.5">
          <Reply className="w-3 h-3 text-gray-500" />
          <p className="text-xs font-medium text-gray-600 dark:text-gray-400">
            Mensagem não encontrada
          </p>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-500 italic">
          A mensagem original pode ter sido removida
        </p>
      </div>
    );
  }
  
  // ✅ CORREÇÃO: Verificar se mensagem foi apagada
  if (repliedMessage.is_deleted) {
    return (
      <div className="mb-2 pl-3 border-l-4 border-l-gray-400 bg-gray-50 dark:bg-gray-800 rounded-r-lg py-1.5">
        <div className="flex items-center gap-1 mb-0.5">
          <Reply className="w-3 h-3 text-gray-500" />
          <p className="text-xs font-medium text-gray-600 dark:text-gray-400">
            Mensagem apagada
          </p>
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-500 italic">
          Esta mensagem foi apagada e não pode ser visualizada
        </p>
      </div>
    );
  }
  
  // Scroll até mensagem original (tentar replyToId e replyIdNorm por diferença de casing no DOM)
  const scrollToOriginal = () => {
    const originalElement =
      document.querySelector<HTMLElement>(`[data-message-id="${replyToId}"]`) ??
      document.querySelector<HTMLElement>(`[data-message-id="${replyIdNorm}"]`);
    if (originalElement) {
      originalElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Destacar mensagem original brevemente
      originalElement.classList.add('ring-2', 'ring-blue-400', 'ring-opacity-75');
      setTimeout(() => {
        originalElement.classList.remove('ring-2', 'ring-blue-400', 'ring-opacity-75');
      }, 2000);
    } else {
      // ✅ Se mensagem não está visível, tentar carregar mensagens antigas
      console.log('📜 [REPLY] Mensagem original não visível, pode precisar carregar histórico');
    }
  };
  
  // ✅ MELHORIA: Detectar tipo de anexo
  const getAttachmentType = () => {
    if (repliedMessage.metadata?.location_message) return '📍 Localização';
    if (!repliedMessage.attachments || repliedMessage.attachments.length === 0) return null;
    const attachment = repliedMessage.attachments[0];
    if (attachment.is_image) return '🖼️ Imagem';
    if (attachment.is_video) return '🎥 Vídeo';
    if (attachment.is_audio) return '🎵 Áudio';
    if (attachment.is_document) return '📄 Documento';
    return '📎 Anexo';
  };
  
  const attachmentType = getAttachmentType();
  const displayContent = repliedMessage.content 
    ? (repliedMessage.content.length > 80 
        ? repliedMessage.content.substring(0, 80) + '...' 
        : repliedMessage.content)
    : (attachmentType || 'Mensagem');
  
  return (
    <div 
      className="mb-2 pl-3 border-l-4 border-l-blue-500 bg-gray-50 dark:bg-gray-800 rounded-r-lg py-1.5 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      onClick={scrollToOriginal}
      title="Clique para ver a mensagem original"
    >
      <div className="flex items-center gap-1 mb-0.5">
        <Reply className="w-3 h-3 text-blue-500 flex-shrink-0" />
        <p className="text-xs font-medium text-blue-600 dark:text-blue-400">
          {repliedMessage.direction === 'incoming' 
            ? (repliedMessage.sender_name || repliedMessage.sender_phone || 'Contato')
            : 'Você'}
        </p>
      </div>
      <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 break-words">
        {displayContent}
      </p>
    </div>
  );
}

// ✅ CORREÇÃO CRÍTICA: Garantir que buildSummaryFromReactions sempre retorna objeto válido
const buildSummaryFromReactions = (reactions: MessageReaction[]): ReactionsSummary => {
  // ✅ CORREÇÃO: Verificar se reactions é array válido antes de usar
  if (!Array.isArray(reactions) || reactions.length === 0) {
    return {};
  }
  
  // ✅ CORREÇÃO: Renomear reaction para reactionItem para evitar conflito de minificação
  return reactions.reduce((accumulator, reactionItem) => {
    // ✅ CORREÇÃO: Verificar se reactionItem e reactionItem.emoji existem antes de usar
    if (!reactionItem || !reactionItem.emoji) {
      return accumulator;
    }
    
    if (!accumulator[reactionItem.emoji]) {
      accumulator[reactionItem.emoji] = { count: 0, users: [] };
    }

    accumulator[reactionItem.emoji].count += 1;
    
    // ✅ CORREÇÃO: Verificar se users é array antes de fazer push
    if (!Array.isArray(accumulator[reactionItem.emoji].users)) {
      accumulator[reactionItem.emoji].users = [];
    }
    
    accumulator[reactionItem.emoji].users.push({
      id: reactionItem.user || '',
      email: reactionItem.user_data?.email || '',
      first_name: reactionItem.user_data?.first_name || undefined,
      last_name: reactionItem.user_data?.last_name || undefined,
    });

    return accumulator;
  }, {} as ReactionsSummary);
};

export function MessageList() {
  console.log('🔄 [MessageList] Componente iniciando renderização...');
  
  // ✅ CORREÇÃO CRÍTICA: Inicializar estados ANTES de usar seletores que dependem de activeConversation
  console.log('📝 [MessageList] Inicializando estados...');
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactToAdd, setContactToAdd] = useState<{ name: string; phone: string } | null>(null);
  const [visibleMessages, setVisibleMessages] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ message: Message; position: { x: number; y: number } } | null>(null);
  const [showMessageInfo, setShowMessageInfo] = useState<Message | null>(null);
  const [emojiPickerMessage, setEmojiPickerMessage] = useState<Message | null>(null);
  const [forwardMessage, setForwardMessage] = useState<Message | null>(null);
  const [editMessage, setEditMessage] = useState<Message | null>(null);
  const [retryingMessageId, setRetryingMessageId] = useState<string | null>(null);
  
  console.log('✅ [MessageList] Estados inicializados');
  
  // ✅ CORREÇÃO: Capturar activeConversation ANTES de usar em outros seletores
  console.log('🔍 [MessageList] Capturando activeConversation do store...');
  const activeConversation = useChatStore((state) => state.activeConversation);
  console.log('✅ [MessageList] activeConversation capturado:', {
    hasActiveConversation: !!activeConversation,
    activeConversationId: activeConversation?.id,
    conversationType: activeConversation?.conversation_type
  });
  
  // ✅ CORREÇÃO: Capturar conversationId de forma segura antes de usar
  const conversationId = activeConversation?.id;
  console.log('✅ [MessageList] conversationId extraído:', conversationId);
  
  // ✅ CORREÇÃO CRÍTICA: Usar chave normalizada (lowercase) para coincidir com o store
  const conversationKey = conversationId ? String(conversationId).trim().toLowerCase() : '';
  // ✅ Selector que reage a byId e byConversationId da conversa ativa
  const messages = useChatStore((state) => {
    if (!conversationKey) return [];
    const messageIds = state.messages.byConversationId[conversationKey] || [];
    return messageIds
      .map((id) => state.messages.byId[String(id)])
      .filter(Boolean);
  });
  
  console.log('🔍 [MessageList] Capturando outras funções do store...');
  const updateMessageReactions = useChatStore((state) => state.updateMessageReactions);
  const setMessages = useChatStore((state) => state.setMessages);
  const typing = useChatStore((state) => state.typing);
  const typingUser = useChatStore((state) => state.typingUser);
  const getMessagesArray = useChatStore((state) => state.getMessagesArray);
  console.log('✅ [MessageList] Funções do store capturadas');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesStartRef = useRef<HTMLDivElement>(null); // ✅ NOVO: Ref para topo (lazy loading)
  const lastMessageIdRef = useRef<string | null>(null); // ✅ NOVO: Rastrear última mensagem para detectar novas vs antigas
  const retryTimeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]); // ✅ MELHORIA: Ref para armazenar timeouts de retry
  
  // ✅ CORREÇÃO: Usar hooks DEPOIS de inicializar estados e capturar conversationId
  // ✅ CORREÇÃO CRÍTICA: useUserAccess agora é seguro e sempre retorna valores válidos
  console.log('🔍 [MessageList] Capturando useUserAccess...');
  const { hasProductAccess } = useUserAccess();
  console.log('✅ [MessageList] useUserAccess capturado:', {
    hasHasProductAccess: !!hasProductAccess,
    hasProductAccessType: typeof hasProductAccess
  });
  
  // ✅ CORREÇÃO: Verificar se hasProductAccess existe antes de chamar
  console.log('🔍 [MessageList] Calculando hasFlowAI...');
  let hasFlowAI = false;
  try {
    if (hasProductAccess && typeof hasProductAccess === 'function') {
      const flowAIAccess = hasProductAccess('flow-ai');
      hasFlowAI = flowAIAccess?.canAccess || false;
      console.log('✅ [MessageList] hasFlowAI calculado:', { hasFlowAI, flowAIAccess });
    } else {
      console.warn('⚠️ [MessageList] hasProductAccess não é uma função válida:', hasProductAccess);
    }
  } catch (error) {
    console.error('❌ [MessageList] ERRO ao calcular hasFlowAI:', error);
    hasFlowAI = false;
  }

  const [aiSettings, setAiSettings] = useState<{ ai_enabled: boolean; audio_transcription_enabled: boolean } | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.get('/ai/settings/')
      .then((response) => {
        if (!isMounted) return;
        const data = response.data || {};
        setAiSettings({
          ai_enabled: !!data.ai_enabled,
          audio_transcription_enabled: !!data.audio_transcription_enabled,
        });
      })
      .catch(() => {
        if (!isMounted) return;
        setAiSettings(null);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const showTranscription = !!(aiSettings?.ai_enabled && aiSettings?.audio_transcription_enabled);

  useEffect(() => {
    if (!activeConversation?.id) {
      // ✅ CORREÇÃO: Limpar mensagens quando não há conversa ativa
      setMessages([], '');
      setIsLoading(false); // ✅ MELHORIA: Resetar loading quando não há conversa
      setHasMoreMessages(false); // ✅ MELHORIA: Resetar flag de mais mensagens
      setVisibleMessages(new Set()); // ✅ MELHORIA: Limpar mensagens visíveis
      return;
    }

    // ✅ CORREÇÃO CRÍTICA: Verificar se já temos mensagens no store antes de fazer fetch
    // Isso evita fetch desnecessário se mensagens já foram carregadas via WebSocket
    const { getMessagesArray } = useChatStore.getState();
    const existingMessages = getMessagesArray(activeConversation.id);
    
    // Se já temos mensagens no store, usar elas (mas ainda fazer fetch para garantir sincronização)
    if (existingMessages.length > 0) {
      console.log(`✅ [MessageList] Já temos ${existingMessages.length} mensagem(ns) no store, usando elas enquanto busca atualizações...`);
      setMessages(existingMessages, activeConversation.id);
    }

    const fetchMessages = async (retryCount = 0) => {
      let error: any = null; // ✅ MELHORIA: Declarar error no escopo correto para usar no finally
      
      try {
        setIsLoading(true);
        setVisibleMessages(new Set()); // Reset visibilidade ao trocar conversa
        
        // ✅ CORREÇÃO: Se conversa é muito nova (< 1.5s), aguardar um pouco antes de buscar
        // Isso evita erro 404 quando conversa ainda está sendo criada no backend (reduzido de 5s para 1.5s - UX)
        const NEW_CONVERSATION_MAX_WAIT_SEC = 1.5;
        if (activeConversation.created_at && retryCount === 0) {
          const createdDate = new Date(activeConversation.created_at);
          const now = new Date();
          const ageInSeconds = (now.getTime() - createdDate.getTime()) / 1000;
          
          if (ageInSeconds < NEW_CONVERSATION_MAX_WAIT_SEC) {
            const waitTime = (NEW_CONVERSATION_MAX_WAIT_SEC - ageInSeconds) * 1000;
            console.log(`⏳ [MessageList] Conversa muito nova (${Math.round(ageInSeconds)}s), aguardando ${Math.round(waitTime)}ms antes de buscar mensagens...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
          }
        }
        
        // ✅ PERFORMANCE: Paginação - carregar apenas últimas 15 mensagens
        const response = await api.get(`/chat/conversations/${activeConversation.id}/messages/`, {
          params: { 
            limit: 15,
            offset: 0
          }
        });
        
        // API retorna { results, count, has_more, ... }
        const data = response.data;
        const msgs = data.results || data;
        setHasMoreMessages(data.has_more || false); // ✅ NOVO: Salvar se tem mais mensagens
        
        // ✅ FIX: Ordenar mensagens por timestamp (mais recentes primeiro)
        // Isso garante que mensagens fora de ordem sejam ordenadas corretamente
        const sortedMsgs = sortMessagesByTimestamp(msgs);
        
        // ✅ MELHORIA: Ao invés de setMessages (sobrescreve), fazer merge inteligente
        // para preservar attachments que foram atualizados via WebSocket
        const { getMessagesArray, activeConversation: currentActiveConversation } = useChatStore.getState();
        const currentMessages = currentActiveConversation ? getMessagesArray(currentActiveConversation.id) : [];
        const mergedMessages = sortedMsgs.map((serverMsg) => {
          const existingMsg = currentMessages.find((messageItem) => normalizeMessageId(messageItem.id) === normalizeMessageId(serverMsg.id));
          if (existingMsg && existingMsg.attachments && existingMsg.attachments.length > 0) {
            // Se mensagem existente tem attachments atualizados, preservar
            const serverAttachments = serverMsg.attachments || [];
            const mergedAttachments = existingMsg.attachments.map((existingAtt) => {
              const serverAtt = serverAttachments.find((attachmentItem) => attachmentItem.id === existingAtt.id);
              if (serverAtt) {
                // Priorizar attachment com file_url válido
                const existingHasUrl = existingAtt.file_url && existingAtt.file_url.trim() &&
                                      !existingAtt.file_url.includes('whatsapp.net') &&
                                      !existingAtt.file_url.includes('evo.');
                const serverHasUrl = serverAtt.file_url && serverAtt.file_url.trim() &&
                                    !serverAtt.file_url.includes('whatsapp.net') &&
                                    !serverAtt.file_url.includes('evo.');
                
                if (existingHasUrl && !serverHasUrl) {
                  return existingAtt; // Manter attachment atualizado do WebSocket
                }
                return serverAtt; // Usar server se não há conflito ou server tem URL válida
              }
              return existingAtt; // Manter attachment que não vem do servidor
            });
            
            // Adicionar novos attachments do servidor
            const existingAttachmentIds = new Set(mergedAttachments.map((attachmentItem) => attachmentItem.id));
            serverAttachments.forEach((serverAtt) => {
              if (!existingAttachmentIds.has(serverAtt.id)) {
                mergedAttachments.push(serverAtt);
              }
            });
            
            return { ...serverMsg, attachments: mergedAttachments };
          }
          return serverMsg; // Nova mensagem ou sem attachments, usar do servidor
        });
        
        setMessages(mergedMessages, activeConversation.id);
        
        // ✅ MELHORIA: Resetar loading imediatamente após setMessages (antes dos retries)
        // Isso garante que loading seja resetado mesmo se houver retries pendentes
        setIsLoading(false);
        
        // ✅ PERFORMANCE: Animar mensagens em batch (mais rápido)
        // Reduzido delay de 20ms para 10ms e limita animação a 15 mensagens
        setTimeout(() => {
          const messagesToAnimate = mergedMessages.slice(-15); // Apenas últimas 15 para não demorar muito
          messagesToAnimate.forEach((messageItem, index) => {
            setTimeout(() => {
              setVisibleMessages(prev => new Set([...prev, messageItem.id]));
            }, index * 10); // ✅ Reduzido de 20ms para 10ms
          });
          
          // Adicionar mensagens restantes imediatamente (sem animação)
          if (mergedMessages.length > 15) {
            const restMessages = mergedMessages.slice(0, -15);
            restMessages.forEach((messageItem) => {
              setVisibleMessages(prev => new Set([...prev, messageItem.id]));
            });
          }
        }, 50);
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
        
        // ✅ MELHORIA: Se conversa não tem mensagens e foi criada recentemente (< 30s), 
        // fazer re-fetches para pegar mensagem que pode estar sendo processada
        // Reduzido de 60s para 30s e melhorado controle de retries
        if (mergedMessages.length === 0 && activeConversation.created_at) {
          const createdDate = new Date(activeConversation.created_at);
          const now = new Date();
          const ageInSeconds = (now.getTime() - createdDate.getTime()) / 1000;
          
          // ✅ MELHORIA: Reduzir tempo de retry para 30s (conversas muito novas)
          if (ageInSeconds < 30) {
            console.log(`🔄 [MessageList] Conversa nova sem mensagens (${Math.round(ageInSeconds)}s), fazendo re-fetches...`);
            
            // ✅ MELHORIA: Limpar retries anteriores antes de criar novos
            retryTimeoutsRef.current.forEach(t => clearTimeout(t));
            retryTimeoutsRef.current = [];
            
            // ✅ MELHORIA: Fazer retries com intervalos crescentes (2 tentativas para conversa vazia - UX)
            const retryDelays = [1000, 2000]; // 1s, 2s
            
            retryDelays.forEach((delay, index) => {
              const timeoutId = setTimeout(async () => {
                // ✅ MELHORIA: Verificar se ainda é a mesma conversa antes de fazer retry
                const { activeConversation: currentActiveConversation } = useChatStore.getState();
                if (currentActiveConversation?.id !== activeConversation.id) {
                  console.log(`⚠️ [MessageList] Conversa mudou durante retry, cancelando...`);
                  setIsLoading(false);
                  return;
                }
                
                try {
                  console.log(`🔄 [MessageList] Re-fetch #${index + 1} após ${delay}ms...`);
                  const retryResponse = await api.get(`/chat/conversations/${activeConversation.id}/messages/`, {
                    params: { 
                      limit: 15,
                      offset: 0
                    }
                  });
                  const retryData = retryResponse.data;
                  const retryMsgs = retryData.results || retryData;
                  
                  if (retryMsgs.length > 0) {
                    console.log(`✅ [MessageList] Re-fetch #${index + 1} encontrou ${retryMsgs.length} mensagem(ns)!`);
                    setMessages(retryMsgs, activeConversation.id);
                    setHasMoreMessages(retryData.has_more || false);
                    setIsLoading(false);
                    
                    // ✅ MELHORIA: Cancelar outros retries pendentes
                    retryTimeoutsRef.current.forEach(t => clearTimeout(t));
                    retryTimeoutsRef.current = [];
                    
                    // Scroll to bottom
                    setTimeout(() => {
                      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                    }, 100);
                    return;
                  } else if (index === retryDelays.length - 1) {
                    console.log(`⚠️ [MessageList] Nenhum retry encontrou mensagens após ${retryDelays.length} tentativas`);
                    setIsLoading(false); // ✅ CORREÇÃO: Resetar loading ao final de todos os retries
                  }
                } catch (err) {
                  console.error(`❌ [MessageList] Erro no re-fetch #${index + 1}:`, err);
                  // ✅ MELHORIA: Resetar loading mesmo em caso de erro no último retry
                  if (index === retryDelays.length - 1) {
                    setIsLoading(false);
                  }
                }
              }, delay);
              retryTimeoutsRef.current.push(timeoutId);
            });
          }
        }
      } catch (err: any) {
        error = err; // ✅ MELHORIA: Salvar error para usar no finally
        console.error('❌ Erro ao carregar mensagens:', err);
        
        // ✅ CORREÇÃO: Se erro 404 e conversa é nova, fazer retry com backoff exponencial
        // Isso trata o caso onde conversa ainda está sendo criada no backend
        if (err?.response?.status === 404 && retryCount < 3) {
          const createdDate = activeConversation.created_at ? new Date(activeConversation.created_at) : null;
          const now = new Date();
          const isNewConversation = createdDate && (now.getTime() - createdDate.getTime()) < 30000; // < 30s
          
          if (isNewConversation) {
            const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 5000); // 1s, 2s, 4s (max 5s)
            console.log(`🔄 [MessageList] Conversa nova ainda não criada (404), retry #${retryCount + 1} em ${retryDelay}ms...`);
            
            setTimeout(() => {
              fetchMessages(retryCount + 1);
            }, retryDelay);
            return; // Não fazer setIsLoading(false) ainda, vai tentar novamente
          }
        }
        
        // ✅ CORREÇÃO: Se erro 404 e não é conversa nova, verificar se há mensagens no WebSocket
        if (err?.response?.status === 404) {
          const { getMessagesArray, activeConversation: currentActiveConversation } = useChatStore.getState();
          const wsMessages = currentActiveConversation ? getMessagesArray(currentActiveConversation.id) : [];
          
          if (wsMessages.length > 0) {
            console.log(`✅ [MessageList] Usando ${wsMessages.length} mensagem(ns) do WebSocket (conversa não encontrada na API)`);
            const sortedMsgs = sortMessagesByTimestamp(wsMessages);
            setMessages(sortedMsgs, activeConversation.id);
            setHasMoreMessages(false);
            setIsLoading(false); // ✅ MELHORIA: Resetar loading quando usar mensagens do WebSocket
            
            // Scroll to bottom
            setTimeout(() => {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            }, 100);
            return;
          }
        }
      } finally {
        // ✅ CORREÇÃO MELHORADA: Sempre resetar loading no finally, exceto se for retry de 404 para conversa nova
        // Isso garante que loading seja resetado mesmo em caso de erro ou quando não há mensagens
        const shouldKeepLoading = error?.response?.status === 404 && 
                                  retryCount < 3 && 
                                  activeConversation.created_at && 
                                  (new Date().getTime() - new Date(activeConversation.created_at).getTime()) < 30000;
        
        if (!shouldKeepLoading) {
          setIsLoading(false);
        }
      }
    };

    // ✅ CORREÇÃO: Resetar ref da última mensagem ao trocar de conversa
    lastMessageIdRef.current = null;
    
    fetchMessages();
    
    // ✅ MELHORIA: Cleanup - resetar loading, limpar estados e cancelar retries quando conversa mudar ou componente desmontar
    return () => {
      setIsLoading(false);
      setHasMoreMessages(false);
      setVisibleMessages(new Set());
      // ✅ MELHORIA: Cancelar todos os retries pendentes
      retryTimeoutsRef.current.forEach(t => clearTimeout(t));
      retryTimeoutsRef.current = [];
    };
  }, [activeConversation?.id, activeConversation?.created_at, setMessages]);

  // Auto-scroll quando novas mensagens chegam + fade-in para novas mensagens
  useEffect(() => {
    if (messages.length === 0) return;
    
    // ✅ CORREÇÃO: Identificar se última mensagem mudou (nova mensagem chegou) vs primeira mudou (mensagens antigas carregadas)
    const currentLastMessageId = messages.length > 0 ? messages[messages.length - 1]?.id : null;
    const lastMessageChanged = currentLastMessageId && currentLastMessageId !== lastMessageIdRef.current;
    
    // ✅ CORREÇÃO: Só fazer scroll se última mensagem mudou (nova mensagem chegou) E não está carregando mensagens antigas
    const shouldScrollToBottom = lastMessageChanged && !loadingOlder;
    
    // Identificar novas mensagens (não visíveis ainda)
    const newMessages = messages.filter((messageItem) => !visibleMessages.has(messageItem.id));
    
    if (newMessages.length > 0) {
      // Adicionar fade-in para novas mensagens
      newMessages.forEach((messageItem, index) => {
        setTimeout(() => {
          setVisibleMessages(prev => new Set([...prev, messageItem.id]));
        }, index * 50); // 50ms entre cada nova mensagem
      });
    }
    
    // ✅ CORREÇÃO: Scroll suave ao final APENAS se nova mensagem chegou (não ao carregar antigas)
    if (shouldScrollToBottom) {
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
    
    // ✅ Atualizar ref da última mensagem
    if (currentLastMessageId) {
      lastMessageIdRef.current = currentLastMessageId;
    }
  }, [messages, visibleMessages, loadingOlder]);

  // ✅ PERFORMANCE: Memoizar funções para evitar recriação a cada render
  const getStatusIcon = useCallback((status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-400 animate-pulse" title="Enviando..." />;
      case 'sent':
        return <Check className="w-4 h-4 text-gray-400" title="Enviada" />;
      case 'delivered':
        return <CheckCheck className="w-4 h-4 text-gray-500" title="Entregue" />;
      case 'seen':
        return <CheckCheck className="w-4 h-4 text-blue-500" title="Vista" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" title="Falha no envio" />;
      default:
        return null;
    }
  }, []);

  const formatTime = useCallback((dateString: string) => {
    try {
      return format(new Date(dateString), 'HH:mm');
    } catch {
      return '';
    }
  }, []);

  const getAttachmentIcon = useCallback((attachment: MessageAttachment) => {
    if (attachment.is_image) return <ImageIcon className="w-5 h-5" />;
    if (attachment.is_video) return <Video className="w-5 h-5" />;
    if (attachment.is_audio) return <Music className="w-5 h-5" />;
    return <FileText className="w-5 h-5" />;
  }, []);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };


  const renderAttachment = (attachment: MessageAttachment) => {
    const isDownloading = !attachment.file_url || attachment.file_url === '';
    
    // Imagem
    if (attachment.is_image && !isDownloading) {
      return (
        <a
          href={attachment.file_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block mb-2"
        >
          <img
            src={attachment.file_url}
            alt={attachment.original_filename}
            className="max-w-full rounded-lg max-h-64 object-contain"
            loading="lazy"
          />
        </a>
      );
    }

    // Arquivo (qualquer tipo) ou baixando
    return (
      <div className="flex items-center gap-3 p-3 bg-white/50 dark:bg-black/20 rounded-lg mb-2">
        <div className="flex-shrink-0 p-2 bg-white dark:bg-gray-700 rounded-full">
          {isDownloading ? (
            <Download className="w-5 h-5 animate-pulse text-gray-400" />
          ) : (
            getAttachmentIcon(attachment)
          )}
        </div>
        <div className="flex-1 min-w-0">
          {/* ✅ MELHORIA: Mostrar nome do arquivo quando disponível */}
          {!isDownloading && attachment.original_filename && (
            <p className="text-xs font-medium text-gray-700 truncate mb-0.5" title={attachment.original_filename}>
              {attachment.original_filename}
            </p>
          )}
          <p className="text-xs text-gray-500">
            {isDownloading ? 'Baixando...' : (
              attachment.size_bytes > 0 
                ? formatFileSize(attachment.size_bytes) 
                : (attachment.file_url && !attachment.file_url.includes('whatsapp.net') && !attachment.file_url.includes('evo.') && attachment.file_url.includes('/api/chat/media-proxy'))
                  ? formatFileSize(0) // URL válida mas tamanho ainda não disponível
                  : 'Processando...'
            )}
          </p>
        </div>
        {!isDownloading && (
          <a
            href={attachment.file_url}
            download={attachment.original_filename}
            className="flex-shrink-0 p-2 hover:bg-white/50 dark:hover:bg-black/30 rounded-full transition-colors"
            title="Baixar arquivo"
          >
            <Download className="w-4 h-4" />
          </a>
        )}
      </div>
    );
  };

  if (!activeConversation) {
    return null;
  }

  // ✅ CORREÇÃO CRÍTICA: Usar useMemo para garantir que safeMessages seja calculado de forma segura
  // Isso evita problemas de inicialização com minificação
  // IMPORTANTE: Este useMemo deve estar DEPOIS de todos os hooks para evitar problemas de ordem
  const safeMessages = useMemo(() => {
    try {
      console.log('🔄 [MessageList] useMemo calculando safeMessages:', {
        messagesIsArray: Array.isArray(messages),
        messagesType: typeof messages,
        messagesLength: messages?.length || 0,
        messagesValue: messages
      });
      
      // ✅ CORREÇÃO: Verificar se messages existe e é array antes de usar
      if (!messages) {
        console.warn('⚠️ [MessageList] messages é null/undefined, retornando array vazio');
        return [];
      }
      
      if (!Array.isArray(messages)) {
        console.warn('⚠️ [MessageList] messages não é array, retornando array vazio:', {
          messagesType: typeof messages,
          messagesValue: messages
        });
        return [];
      }
      
      // ✅ CORREÇÃO: Filtrar valores inválidos de forma segura
      const safe = messages.filter((messageItem: any) => {
        if (!messageItem || typeof messageItem !== 'object') {
          return false;
        }
        return Boolean(messageItem.id); // Garantir que tem id válido
      });
      
      console.log('✅ [MessageList] safeMessages calculado:', {
        originalLength: messages.length,
        safeLength: safe.length
      });
      
      return safe;
    } catch (error) {
      console.error('❌ [MessageList] ERRO ao calcular safeMessages:', error);
      return [];
    }
  }, [messages]);

  console.log('✅ [MessageList] safeMessages pronto para renderizar:', {
    safeMessagesLength: safeMessages.length,
    safeMessagesIsArray: Array.isArray(safeMessages)
  });

  return (
    <div 
      className="h-full overflow-y-auto custom-scrollbar p-3 sm:p-4 space-y-2"
      style={{
        backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'100\' height=\'100\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M0 0h100v100H0z\' fill=\'%23e5ddd5\'/%3E%3Cpath d=\'M20 10h60v2H20zm0 15h60v2H20zm0 15h40v2H20z\' fill=\'%23ffffff\' opacity=\'0.1\'/%3E%3C/svg%3E")',
      }}
    >
      {isLoading ? (
        <div className="flex items-center justify-center h-full">
          <div className="flex flex-col items-center gap-3">
            <div className="flex gap-2">
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
            <p className="text-sm text-gray-500">Carregando mensagens...</p>
          </div>
        </div>
      ) : safeMessages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full p-8">
          <div className="w-32 h-32 mb-4 opacity-20">
            <svg viewBox="0 0 303 172" fill="currentColor" className="text-gray-400 w-full h-full">
              <path d="M229.003 146.214c-18.832-35.882-34.954-69.436-38.857-96.056-4.154-28.35 4.915-49.117 35.368-59.544 30.453-10.426 60.904 4.154 71.33 34.607 10.427 30.453-4.154 60.904-34.607 71.33-15.615 5.346-32.123 4.58-47.234-.337zM3.917 63.734C14.344 33.281 44.795 18.7 75.248 29.127c30.453 10.426 45.034 40.877 34.607 71.33-10.426 30.453-40.877 45.034-71.33 34.607C7.972 124.638-6.61 94.187 3.917 63.734z"/>
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-700 mb-2">Nenhuma mensagem ainda</h3>
          <p className="text-sm text-gray-500 text-center max-w-xs">
            Comece a conversa enviando uma mensagem!
          </p>
        </div>
      ) : (
        <>
          {/* ✅ NOVO: Botão para carregar mensagens antigas */}
          {hasMoreMessages && !loadingOlder && (
            <div className="flex justify-center mb-2">
              <button
                onClick={async () => {
                  if (!activeConversation?.id || loadingOlder) return;
                  
                  setLoadingOlder(true);
                  try {
                    const currentCount = messages.length;
                    const response = await api.get(`/chat/conversations/${activeConversation.id}/messages/`, {
                      params: { 
                        limit: 15,
                        offset: currentCount
                      }
                    });
                    
                    const data = response.data;
                    const olderMsgs = data.results || data;
                    
                    if (olderMsgs.length > 0) {
                      // ✅ CORREÇÃO: Salvar scroll position antes de adicionar mensagens
                      const container = messagesStartRef.current?.parentElement as HTMLElement | null;
                      const scrollHeightBefore = container?.scrollHeight || 0;
                      const scrollTopBefore = container?.scrollTop || 0;
                      
                      // Adicionar mensagens antigas no início
                      setMessages([...olderMsgs.reverse(), ...messages], activeConversation.id);
                      setHasMoreMessages(data.has_more || false);
                      
                      // ✅ CORREÇÃO: Manter scroll na posição visual após adicionar mensagens antigas
                      // Usar requestAnimationFrame para garantir que DOM foi atualizado
                      requestAnimationFrame(() => {
                        if (container) {
                          const scrollHeightAfter = container.scrollHeight;
                          const scrollDiff = scrollHeightAfter - scrollHeightBefore;
                          // Ajustar scroll para manter a mesma posição visual
                          container.scrollTop = scrollTopBefore + scrollDiff;
                        }
                      });
                    } else {
                      setHasMoreMessages(false);
                    }
                  } catch (error) {
                    console.error('❌ Erro ao carregar mensagens antigas:', error);
                  } finally {
                    setLoadingOlder(false);
                  }
                }}
                className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm font-medium transition-colors"
                aria-label="Carregar mensagens antigas"
              >
                Carregar mensagens antigas
              </button>
            </div>
          )}
          
          {loadingOlder && (
            <div className="flex justify-center mb-2">
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                Carregando mensagens antigas...
              </div>
            </div>
          )}
          
          <div ref={messagesStartRef} /> {/* ✅ NOVO: Ref para topo */}
          
          {safeMessages.map((messageItem) => {
            // ✅ CORREÇÃO CRÍTICA: Renomear msg para messageItem para evitar conflito de minificação
            // A variável msg pode estar sendo minificada como 'm', causando o erro
            console.log('🔍 [MessageList] Renderizando mensagem:', {
              messageId: messageItem?.id,
              hasMessageItem: !!messageItem,
              messageItemType: typeof messageItem
            });
            
            // ✅ CORREÇÃO: Verificar se messageItem é válido antes de renderizar
            if (!messageItem || !messageItem.id) {
              console.warn('⚠️ [MessageList] messageItem inválido, pulando:', messageItem);
              return null;
            }
            
            // ✅ FASE 1: Key composta para evitar reutilização incorreta de componentes entre conversas
            const messageKey = messageItem.conversation_id 
              ? `${messageItem.conversation_id}-${messageItem.id}`
              : (typeof messageItem.conversation === 'string' 
                  ? `${messageItem.conversation}-${messageItem.id}`
                  : (typeof messageItem.conversation === 'object' && messageItem.conversation?.id
                      ? `${messageItem.conversation.id}-${messageItem.id}`
                      : messageItem.id));
            
            return (
            <div
              key={messageKey}
              data-message-id={messageItem.id}
              className={`flex flex-col ${messageItem.direction === 'outgoing' ? 'items-end' : 'items-start'} ${
                visibleMessages.has(messageItem.id) 
                  ? 'opacity-100 translate-y-0' 
                  : 'opacity-0 translate-y-2'
              } transition-all duration-300 ease-out group group/message`}
            >
              <div
                className={`
                  max-w-[65%] md:max-w-md rounded-2xl px-4 py-2.5 shadow-md
                  transform transition-all duration-200 hover:shadow-lg cursor-pointer
                  ${messageItem.direction === 'outgoing'
                    ? 'bg-[#d9fdd3] dark:bg-green-900/30 text-gray-900 dark:text-gray-100'
                    : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                  }
                `}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setContextMenu({
                    message: messageItem,
                    position: { x: e.clientX, y: e.clientY }
                  });
                }}
              >
                {/* Nome do remetente (apenas para GRUPOS e mensagens RECEBIDAS) */}
                {/* ✅ CORREÇÃO CRÍTICA: Usar optional chaining para evitar erro de inicialização */}
                {/* ✅ NOVO: Cabeçalho aparece também para mensagens de mídia (vídeo/áudio/imagem) */}
                {activeConversation?.conversation_type === 'group' && messageItem.direction === 'incoming' && (messageItem.sender_name || messageItem.sender_phone) && (
                  <p className="text-xs font-semibold text-green-600 mb-1">
                    {messageItem.sender_name || messageItem.sender_phone}
                  </p>
                )}

                {/* ✅ NOVO: Badge "Fora de Horário" para mensagens recebidas fora do horário de atendimento */}
                {messageItem.direction === 'incoming' && messageItem.metadata?.is_after_hours_auto && (
                  <div className="mb-2 flex items-center gap-1.5 px-2 py-1 bg-amber-50 border border-amber-200 rounded-lg">
                    <Clock className="w-3.5 h-3.5 text-amber-600" />
                    <span className="text-xs font-medium text-amber-700">
                      Mensagem recebida fora do horário de atendimento
                    </span>
                  </div>
                )}

                {/* ✅ NOVO: Preview de mensagem respondida (reply_to) */}
                {messageItem.metadata?.reply_to && (
                  <ReplyPreview replyToId={messageItem.metadata.reply_to} messages={safeMessages} />
                )}
                
                {/* ✅ NOVO: Mensagem apagada */}
                {messageItem.is_deleted && (
                  <div className="mb-2 flex items-center gap-2 text-gray-400 italic text-sm py-2 px-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                    <Trash2 className="w-4 h-4 flex-shrink-0" />
                    <span>Esta mensagem foi apagada</span>
                  </div>
                )}
                
                {/* ✅ NOVO: Contato compartilhado */}
                {(messageItem.metadata?.contact_message || messageItem.content?.includes('📇') || messageItem.content?.includes('Compartilhou contato')) && (
                  <SharedContactCard
                    contactData={messageItem.metadata?.contact_message || {}}
                    content={messageItem.content}
                    onAddContact={(contactItem) => {
                      setContactToAdd(contactItem);
                      setShowContactModal(true);
                    }}
                  />
                )}
                
                {/* ✅ NOVO: Localização compartilhada */}
                {messageItem.metadata?.location_message && (
                  <LocationCard
                    locationData={messageItem.metadata.location_message}
                    content={messageItem.content}
                  />
                )}
                
                {/* Anexos - renderizar ANTES do texto (apenas se não estiver apagada) */}
                {/* ✅ CORREÇÃO: Renomear attachment para attachmentItem para evitar conflito de minificação */}
                {/* ✅ NOVO: Cabeçalho já aparece antes dos anexos (linha 861), então mídia terá cabeçalho igual ao texto */}
                {!messageItem.is_deleted && messageItem.attachments && messageItem.attachments.length > 0 && (
                  <div className="message-attachments mb-2 space-y-2">
                    {messageItem.attachments.map((attachmentItem) => (
                      <AttachmentPreview
                        key={attachmentItem.id}
                        attachment={attachmentItem}
                        showAI={hasFlowAI}
                        showTranscription={showTranscription}
                      />
                    ))}
                  </div>
                )}

                {/* Texto (se houver) - mostrar mesmo se só tiver anexos (apenas se não estiver apagada) */}
                {/* ✅ FIX: Ocultar conteúdo se for contato ou localização (já exibido no card acima) */}
                {/* ✅ FIX: Sanitizar conteúdo e converter URLs em links clicáveis */}
                {/* ✅ NOVO: Renderizar menções se houver */}
                {/* ✅ NOVO: Formatação WhatsApp (negrito, itálico, riscado, monoespaçado) */}
                {/* ✅ NOVO: Renderizar assinatura 'Nome disse:' como cabeçalho separado */}
                {!messageItem.is_deleted && messageItem.content && messageItem.content.trim() &&
                 !/^\[(document|image|video|audio)\]$/i.test(messageItem.content.trim()) &&
                 !(messageItem.metadata?.contact_message || messageItem.content?.includes('📇') || messageItem.content?.includes('Compartilhou contato')) &&
                 !messageItem.metadata?.location_message && (
                  <>
                    {/* ✅ NOVO: Renderizar assinatura como cabeçalho separado (apenas para mensagens enviadas) */}
                    {messageItem.direction === 'outgoing' && (() => {
                      const parsed = parseMessageSignature(messageItem.content);
                      if (parsed.signature) {
                        return (
                          <div className="mb-1">
                            <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
                              {parsed.signature}
                            </p>
                            <p className="text-sm whitespace-pre-wrap break-words mb-1">
                              {messageItem.metadata?.mentions && Array.isArray(messageItem.metadata.mentions) && messageItem.metadata.mentions.length > 0 ? (
                                <MentionRenderer 
                                  content={parsed.content} 
                                  mentions={messageItem.metadata.mentions}
                                />
                              ) : (
                                <span dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(parsed.content) }} />
                              )}
                            </p>
                          </div>
                        );
                      }
                      // Sem assinatura, renderizar normalmente
                      return (
                        <p className="text-sm whitespace-pre-wrap break-words mb-1">
                          {messageItem.metadata?.mentions && Array.isArray(messageItem.metadata.mentions) && messageItem.metadata.mentions.length > 0 ? (
                            <MentionRenderer 
                              content={messageItem.content} 
                              mentions={messageItem.metadata.mentions}
                            />
                          ) : (
                            <span dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(messageItem.content) }} />
                          )}
                        </p>
                      );
                    })()}
                    
                    {/* Mensagens recebidas (sem assinatura) */}
                    {messageItem.direction === 'incoming' && (
                      <p className="text-sm whitespace-pre-wrap break-words mb-1">
                        {messageItem.metadata?.mentions && Array.isArray(messageItem.metadata.mentions) && messageItem.metadata.mentions.length > 0 ? (
                          <MentionRenderer 
                            content={messageItem.content} 
                            mentions={messageItem.metadata.mentions}
                          />
                        ) : (
                          <span dangerouslySetInnerHTML={{ __html: formatWhatsAppTextWithLinks(messageItem.content) }} />
                        )}
                      </p>
                    )}
                  </>
                )}
                
                <div className={`flex items-center gap-1 justify-end mt-1 ${messageItem.direction === 'outgoing' ? '' : 'opacity-60'}`}>
                  {messageItem.is_edited && (
                    <span className="text-xs text-gray-500 italic">
                      Editada
                    </span>
                  )}
                  <span className="text-xs text-gray-600">
                    {formatTime(messageItem.created_at)}
                  </span>
                  {messageItem.direction === 'outgoing' && (
                    <span className="flex-shrink-0">
                      {getStatusIcon(messageItem.status)}
                    </span>
                  )}
                </div>
                {messageItem.direction === 'outgoing' && messageItem.status === 'failed' && messageItem.metadata?.can_use_fallback && (
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-200/50">
                    <span className="text-xs text-amber-700 flex-1">
                      {messageItem.metadata?.unavailable_instance_friendly_name
                        ? `A instância ${messageItem.metadata.unavailable_instance_friendly_name} está indisponível.`
                        : 'A instância desta conversa está indisponível.'}
                      {messageItem.metadata?.fallback_instance_friendly_name
                        ? ` Enviar por outra instância (ex.: ${messageItem.metadata.fallback_instance_friendly_name})?`
                        : ' Enviar por outra instância?'}
                    </span>
                    <div className="flex gap-1">
                      <button
                        type="button"
                        disabled={retryingMessageId === messageItem.id}
                        onClick={async () => {
                          setRetryingMessageId(messageItem.id);
                          try {
                            await api.post(`/chat/messages/${messageItem.id}/retry-send/`, { use_fallback: true });
                            toast.success('Mensagem reenviada por outra instância');
                          } catch (e: any) {
                            toast.error(e.response?.data?.error || 'Erro ao reenviar');
                          } finally {
                            setRetryingMessageId(null);
                          }
                        }}
                        className="text-xs px-2 py-1 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        {retryingMessageId === messageItem.id ? 'Enviando...' : 'Sim'}
                      </button>
                      <button
                        type="button"
                        disabled={retryingMessageId === messageItem.id}
                        onClick={() => {}}
                        className="text-xs px-2 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                      >
                        Não
                      </button>
                    </div>
                  </div>
                )}
              </div>
              
              {/* ✅ MELHORIA UX: Reações posicionadas como WhatsApp (ao final da mensagem, fora do card, alinhadas) */}
              <MessageReactions message={messageItem} direction={messageItem.direction} />
            </div>
            );
          })}
          
          {/* Indicador de digitando - Melhorado */}
          {typing && (
            <div className="flex justify-start animate-fade-in">
              <div className="bg-white dark:bg-gray-800 rounded-2xl px-4 py-3 shadow-md">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1 px-1">
                    <span className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                  {typingUser && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">{typingUser} está digitando...</span>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </>
      )}

      {/* ✅ NOVO: Menu de contexto para mensagens */}
      {contextMenu && (
        <MessageContextMenu
          message={contextMenu.message}
          position={contextMenu.position}
          onClose={() => setContextMenu(null)}
          onShowInfo={(message) => {
            setContextMenu(null);
            setShowMessageInfo(message);
          }}
          onShowEmojiPicker={(message) => {
            setContextMenu(null);
            setEmojiPickerMessage(message);
          }}
          onShowForward={(message) => {
            setContextMenu(null);
            setForwardMessage(message);
          }}
          onShowEdit={(message) => {
            setContextMenu(null);
            setEditMessage(message);
          }}
        />
      )}

      {/* Modal de Encaminhar (renderizado no MessageList para não ser desmontado) */}
      {forwardMessage && (
        <ForwardMessageModal
          message={forwardMessage}
          onClose={() => setForwardMessage(null)}
          onSuccess={() => {
            setForwardMessage(null);
            // Opcional: atualizar lista de mensagens
          }}
        />
      )}

      {/* Emoji Picker (renderizado no MessageList para não ser desmontado) */}
      {emojiPickerMessage && (
        <div 
          className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/20" 
          onClick={() => setEmojiPickerMessage(null)}
          style={{ zIndex: 10000 }}
        >
          <div 
            className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-300 dark:border-gray-700 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '320px',
              height: '280px',
              maxWidth: '90vw',
              maxHeight: '90vh',
              zIndex: 10001
            }}
          >
            <EmojiPicker
              onSelect={async (emoji: string) => {
                try {
                  await api.post('/chat/reactions/add/', {
                    message_id: emojiPickerMessage.id,
                    emoji: emoji
                  });
                  setEmojiPickerMessage(null);
                } catch (error) {
                  console.error('❌ Erro ao adicionar reação:', error);
                  toast.error('Erro ao adicionar reação');
                }
              }}
              onClose={() => setEmojiPickerMessage(null)}
            />
          </div>
        </div>
      )}

      {/* Modal de Informações da Mensagem */}
      {showMessageInfo && (
        <MessageInfoModal
          message={showMessageInfo}
          onClose={() => setShowMessageInfo(null)}
        />
      )}

      {/* Modal para adicionar contato compartilhado - z-[9999] para aparecer acima do chat */}
      {showContactModal && contactToAdd && (
        <ContactModal
          isOpen={showContactModal}
          onClose={() => {
            setShowContactModal(false);
            setContactToAdd(null);
          }}
          initialName={contactToAdd.name}
          initialPhone={contactToAdd.phone}
          overlayClassName="z-[9999]"
          onSuccess={() => {
            setShowContactModal(false);
            setContactToAdd(null);
          }}
        />
      )}

      {/* Modal de Editar Mensagem */}
      {editMessage && (
        <EditMessageModal
          message={editMessage}
          onClose={() => setEditMessage(null)}
        />
      )}
    </div>
  );
}

/**
 * Componente de Reações de Mensagem
 * Mostra reações existentes e permite adicionar/remover
 */
// ✅ CORREÇÃO: Memoização de componente de reações para evitar re-renders desnecessários
const MessageReactions = React.memo(function MessageReactions({ message, direction }: { message: any; direction: 'incoming' | 'outgoing' }) {
  console.log('🔍 [MessageReactions] Componente renderizado:', {
    messageId: message?.id,
    hasMessage: !!message,
    hasReactionsSummary: !!message?.reactions_summary,
    reactionsSummaryType: typeof message?.reactions_summary
  });
  
  // ✅ CORREÇÃO CRÍTICA: Capturar user de forma segura para evitar problemas de minificação
  console.log('🔍 [MessageReactions] Capturando user do useAuthStore...');
  const authStoreState = useAuthStore();
  const currentUser = authStoreState?.user || null;
  console.log('✅ [MessageReactions] currentUser capturado:', {
    hasUser: !!currentUser,
    userId: currentUser?.id
  });
  
  const { getMessagesArray, setMessages, updateMessageReactions, activeConversation } = useChatStore();
  const messages = activeConversation ? getMessagesArray(activeConversation.id) : [];
  const [hoveredEmoji, setHoveredEmoji] = useState<string | null>(null);
  const [processingEmoji, setProcessingEmoji] = useState<string | null>(null); // ✅ CORREÇÃO: Loading state

  // ✅ CORREÇÃO CRÍTICA: Garantir que reactionsSummary está sempre inicializado corretamente
  // Verificar se message.reactions_summary existe e é um objeto válido
  console.log('🔍 [MessageReactions] Verificando reactions_summary:', {
    hasMessage: !!message,
    hasReactionsSummary: !!message?.reactions_summary,
    reactionsSummaryType: typeof message?.reactions_summary,
    isObject: message?.reactions_summary && typeof message.reactions_summary === 'object' && message.reactions_summary !== null
  });
  
  const reactionsSummary: ReactionsSummary = (message.reactions_summary && typeof message.reactions_summary === 'object' && message.reactions_summary !== null) 
    ? message.reactions_summary 
    : {};
  const hasReactions = Object.keys(reactionsSummary).length > 0;
  
  console.log('✅ [MessageReactions] reactionsSummary inicializado:', {
    hasReactions,
    reactionsCount: Object.keys(reactionsSummary).length,
    reactionsKeys: Object.keys(reactionsSummary)
  });

  // Verificar se usuário já reagiu com cada emoji
  const getUserReaction = (emoji: string): MessageReaction | null => {
    if (!message.reactions || !currentUser) return null;
    // ✅ CORREÇÃO: Renomear r para reactionItem para evitar conflito de minificação
    return message.reactions.find((reactionItem: MessageReaction) => reactionItem.emoji === emoji && reactionItem.user === currentUser.id) || null;
  };

  // ✅ CORREÇÃO: Validação de emoji no frontend
  const validateEmoji = (emoji: string): boolean => {
    if (!emoji || emoji.trim().length === 0) return false;
    if (emoji.length > 10) return false; // Limite de caracteres
    
    // Verificar se é emoji válido (regex básico para emojis Unicode)
    // Emojis Unicode geralmente começam em U+1F300 ou são caracteres especiais
    const emojiRegex = /[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{1F900}-\u{1F9FF}]|[\u{1FA00}-\u{1FA6F}]|[\u{1FA70}-\u{1FAFF}]|[\u{2190}-\u{21FF}]|[\u{2300}-\u{23FF}]|[\u{2B50}-\u{2B55}]|[\u{3030}-\u{303F}]|[\u{3297}-\u{3299}]/u;
    
    // Permitir também alguns emojis compostos (com zero-width joiner)
    if (emoji.includes('\u200D')) {
      return true; // Emoji composto (ex: 👨‍👩‍👧‍👦)
    }
    
    return emojiRegex.test(emoji);
  };

  // ✅ CORREÇÃO: Adicionar ou remover reação (comportamento WhatsApp)
  const handleAddReaction = async (emoji: string) => {
    if (!currentUser || processingEmoji) return; // ✅ CORREÇÃO: Prevenir duplo clique
    
    // ✅ CORREÇÃO: Validar emoji antes de enviar
    if (!validateEmoji(emoji)) {
      console.warn('⚠️ [REACTION] Emoji inválido:', emoji);
      return;
    }
    
    setProcessingEmoji(emoji); // ✅ CORREÇÃO: Feedback visual
    
    // ✅ CORREÇÃO: Lookup por id normalizado (byId usa chave normalizada)
    const { messages: normalizedMessages } = useChatStore.getState();
    const currentStoreMessage = normalizedMessages.byId[normalizeMessageId(message.id)];
    const previousReactions = cloneReactions(currentStoreMessage?.reactions);
    
    // ✅ CORREÇÃO CRÍTICA: Verificar se usuário já reagiu com este emoji
    const userReaction = previousReactions.find(
      (reaction) => reaction.user === String(currentUser?.id) && reaction.emoji === emoji
    );
    
    // ✅ CORREÇÃO: Se já reagiu com este emoji, remover (toggle off)
    if (userReaction) {
      // Optimistic update: remover reação
      const optimisticReactions = previousReactions.filter(
        (reaction) => reaction.id !== userReaction.id
      );
      const optimisticSummary = buildSummaryFromReactions(optimisticReactions);
      updateMessageReactions(message.id, optimisticReactions, optimisticSummary);
      
      try {
        const response = await api.post('/chat/reactions/remove/', {
          message_id: message.id,
          emoji: emoji,
        });
        
        if (!response.data?.success) {
          throw new Error('Resposta inválida do servidor');
        }
        
        return; // ✅ Sair após remover
      } catch (error: any) {
        console.error('❌ Erro ao remover reação:', error);
        const errorMessage = error?.response?.data?.error || 'Erro ao remover reação';
        
        // Rollback
        updateMessageReactions(
          message.id,
          previousReactions,
          buildSummaryFromReactions(previousReactions)
        );
        
        if (typeof window !== 'undefined' && (window as any).toast) {
          (window as any).toast.error(errorMessage);
        }
      } finally {
        setProcessingEmoji(null);
      }
      return;
    }
    
    // ✅ CORREÇÃO: Se usuário já reagiu com outro emoji, substituir (remover antiga)
    const otherUserReaction = previousReactions.find(
      (reaction) => reaction.user === String(currentUser?.id) && reaction.emoji !== emoji
    );
    
    const optimisticReaction: MessageReaction = {
      id: `optimistic-${currentUser?.id || 'unknown'}-${emoji}-${Date.now()}`,
      message: message.id,
      user: String(currentUser?.id || ''),
      user_data: currentUser ? {
        id: String(currentUser.id),
        email: currentUser.email || '',
        first_name: currentUser.first_name,
        last_name: currentUser.last_name,
      } : undefined,
      emoji,
      created_at: new Date().toISOString(),
    };

    // ✅ CORREÇÃO: Remover reação antiga do usuário (se existir) e adicionar nova
    const optimisticReactions = [
      ...previousReactions.filter(
        (reaction) => reaction.user !== String(currentUser?.id) // Remover TODAS as reações do usuário
      ),
      optimisticReaction, // Adicionar nova reação
    ];

    const optimisticSummary = buildSummaryFromReactions(optimisticReactions);

    updateMessageReactions(message.id, optimisticReactions, optimisticSummary);

    try {
      const response = await api.post('/chat/reactions/add/', {
        message_id: message.id,
        emoji: emoji,
      });

      // ✅ CORREÇÃO: Verificar se resposta tem dados válidos antes de atualizar
      if (response.data) {
        // Se resposta tem message com reactions, atualizar
        if (response.data.message) {
          updateMessageReactions(
            response.data.message.id,
            cloneReactions(response.data.message.reactions),
            response.data.message.reactions_summary || {}
          );
        } else if (response.data.emoji) {
          // Se resposta tem apenas emoji (reação criada), manter optimistic update
          // O WebSocket vai atualizar com dados completos
          console.log('✅ [REACTION] Reação adicionada, aguardando broadcast WebSocket');
        }
      }
    } catch (error: any) {
      console.error('❌ Erro ao adicionar reação:', error);
      
      // ✅ CORREÇÃO: Mostrar erro específico ao usuário
      const errorMessage = error?.response?.data?.error || 'Erro ao adicionar reação';
      console.error('   Erro detalhado:', errorMessage);
      
      // Rollback do optimistic update
      updateMessageReactions(
        message.id,
        previousReactions,
        buildSummaryFromReactions(previousReactions)
      );
      
      // ✅ CORREÇÃO: Mostrar toast de erro (se disponível)
      if (typeof window !== 'undefined' && (window as any).toast) {
        (window as any).toast.error(errorMessage);
      }
    } finally {
      setProcessingEmoji(null); // ✅ CORREÇÃO: Remover loading state
    }
  };

  // Remover reação
  const handleRemoveReaction = async (emoji: string) => {
    if (!currentUser || processingEmoji) return; // ✅ CORREÇÃO: Prevenir duplo clique
    
    setProcessingEmoji(emoji); // ✅ CORREÇÃO: Feedback visual
    
    // ✅ CORREÇÃO: Lookup por id normalizado (byId usa chave normalizada)
    const { messages: normalizedMessages } = useChatStore.getState();
    const currentStoreMessage = normalizedMessages.byId[normalizeMessageId(message.id)];
    const previousReactions = cloneReactions(currentStoreMessage?.reactions);

    const optimisticReactions = previousReactions.filter(
      (reaction) => !(reaction.emoji === emoji && reaction.user === String(currentUser?.id))
    );
    const optimisticSummary = buildSummaryFromReactions(optimisticReactions);

    updateMessageReactions(message.id, optimisticReactions, optimisticSummary);

    try {
      const response = await api.post('/chat/reactions/remove/', {
        message_id: message.id,
        emoji: emoji,
      });
      
      // ✅ CORREÇÃO: Verificar resposta antes de considerar sucesso
      if (!response.data?.success) {
        throw new Error('Resposta inválida do servidor');
      }
    } catch (error: any) {
      console.error('❌ Erro ao remover reação:', error);
      
      // ✅ CORREÇÃO: Mostrar erro específico ao usuário
      const errorMessage = error?.response?.data?.error || 'Erro ao remover reação';
      console.error('   Erro detalhado:', errorMessage);
      
      // Rollback do optimistic update
      updateMessageReactions(
        message.id,
        previousReactions,
        buildSummaryFromReactions(previousReactions)
      );
      
      // ✅ CORREÇÃO: Mostrar toast de erro (se disponível)
      if (typeof window !== 'undefined' && (window as any).toast) {
        (window as any).toast.error(errorMessage);
      }
    } finally {
      setProcessingEmoji(null); // ✅ CORREÇÃO: Remover loading state
    }
  };

  // Toggle reação (adicionar se não existe, remover se existe)
  const handleToggleReaction = async (emoji: string) => {
    const userReaction = getUserReaction(emoji);
    if (userReaction) {
      await handleRemoveReaction(emoji);
    } else {
      await handleAddReaction(emoji);
    }
  };

  // ✅ MELHORIA UX: Estilo WhatsApp - reações ao final da mensagem, botão sempre visível ao passar mouse
  // Alinhar à direita para mensagens enviadas, à esquerda para recebidas
  // ✅ CORREÇÃO: Usar group-hover/message (grupo está no elemento pai da mensagem)
  return (
    <div className={`flex items-center gap-1.5 mt-0.5 ${direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}>
      {/* Reações existentes */}
      {hasReactions && (
        <div className="flex items-center gap-1 flex-wrap">
          {Object.entries(reactionsSummary).map(([emojiKey, reactionDataValue]: [string, any]) => {
            // ✅ CORREÇÃO CRÍTICA: Renomear variáveis de desestruturação para evitar conflito de minificação
            // A variável 'data' pode estar sendo minificada como 'd' e causando conflito
            // ✅ CORREÇÃO: Usar emojiKey ao invés de emoji (que não está definido)
            const reactionData = reactionDataValue;
            
            console.log('🔍 [MessageReactions] Processando reação:', {
              emojiKey,
              hasData: !!reactionData,
              dataType: typeof reactionData,
              isObject: reactionData && typeof reactionData === 'object',
              hasUsers: !!(reactionData?.users),
              usersType: typeof reactionData?.users,
              isUsersArray: Array.isArray(reactionData?.users),
              usersLength: Array.isArray(reactionData?.users) ? reactionData.users.length : 'N/A'
            });
            
            // ✅ CORREÇÃO CRÍTICA: Verificar se reactionData existe e tem propriedades válidas antes de usar
            if (!reactionData || typeof reactionData !== 'object') {
              console.warn('⚠️ [MessageReactions] reactionData inválido, pulando:', { emojiKey, reactionData });
              return null;
            }
            
            const userReaction = getUserReaction(emojiKey);
            const isUserReaction = !!userReaction;
            
            // ✅ CORREÇÃO CRÍTICA: Garantir que reactionData.users é um array válido antes de usar
            console.log('🔍 [MessageReactions] Verificando reactionData.users ANTES do map:', {
              emojiKey,
              hasReactionData: !!reactionData,
              hasUsers: !!(reactionData?.users),
              usersType: typeof reactionData?.users,
              isArray: Array.isArray(reactionData?.users),
              usersValue: reactionData?.users
            });
            
            const users = Array.isArray(reactionData?.users) ? reactionData.users : [];
            console.log('👥 [MessageReactions] Users extraídos:', {
              emojiKey,
              usersCount: users.length,
              usersIsArray: Array.isArray(users),
              usersType: typeof users,
              usersValue: users
            });
            
            let usersText = '';
            if (users.length > 0) {
              console.log('🔄 [MessageReactions] Iniciando map de users:', {
                emojiKey,
                usersLength: users.length
              });
              
              try {
                // ✅ CORREÇÃO CRÍTICA: Renomear u para reactionUserItem para evitar conflito de minificação
                // A variável u pode estar sendo minificada causando erro "Cannot access 'u' before initialization"
                usersText = users.map((reactionUserItem: any, index: number) => {
                  console.log(`🔍 [MessageReactions] Processando user[${index}]:`, {
                    emojiKey,
                    index,
                    hasReactionUserItem: !!reactionUserItem,
                    reactionUserItemType: typeof reactionUserItem,
                    reactionUserItemValue: reactionUserItem,
                    reactionUserItemKeys: reactionUserItem ? Object.keys(reactionUserItem) : [],
                    email: reactionUserItem?.email,
                    firstName: reactionUserItem?.first_name
                  });
                  
                  if (!reactionUserItem || typeof reactionUserItem !== 'object') {
                    console.warn(`⚠️ [MessageReactions] User[${index}] inválido:`, reactionUserItem);
                    return 'Usuário';
                  }
                  
                  const email = reactionUserItem?.email || '';
                  const firstName = reactionUserItem?.first_name || '';
                  const result = email || firstName || 'Usuário';
                  
                  console.log(`✅ [MessageReactions] User[${index}] processado:`, {
                    emojiKey,
                    index,
                    result
                  });
                  
                  return result;
                }).join(', ');
                
                console.log('✅ [MessageReactions] usersText gerado:', {
                  emojiKey,
                  usersText,
                  usersTextLength: usersText.length
                });
              } catch (mapError) {
                console.error('❌ [MessageReactions] ERRO no map de users:', {
                  emojiKey,
                  error: mapError,
                  errorMessage: (mapError as Error).message,
                  errorStack: (mapError as Error).stack,
                  users
                });
                usersText = '';
              }
            } else {
              console.log('⚠️ [MessageReactions] Nenhum user para processar:', { emojiKey });
            }
            
            const count = typeof reactionData?.count === 'number' ? reactionData.count : 0;
            
            console.log('✅ [MessageReactions] Reação processada com sucesso:', {
              emojiKey,
              count,
              usersTextLength: usersText.length,
              isUserReaction
            });
            
            return (
              <button
                key={emojiKey}
                onClick={() => handleToggleReaction(emojiKey)}
                onMouseEnter={() => setHoveredEmoji(emojiKey)}
                onMouseLeave={() => setHoveredEmoji(null)}
                disabled={processingEmoji === emojiKey}
                className={`
                  px-2 py-0.5 rounded-full text-xs flex items-center gap-1 transition-all
                  ${processingEmoji === emojiKey ? 'opacity-50 cursor-wait' : 'cursor-pointer'}
                  ${isUserReaction
                    ? 'bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700'
                    : 'bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-600/50'
                  }
                `}
                title={`${count} ${count === 1 ? 'reação' : 'reações'}${usersText ? `: ${usersText}` : ''}`}
              >
                <span className="text-sm">{emojiKey}</span>
                <span className={`text-xs font-medium ${isUserReaction ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
                  {processingEmoji === emojiKey ? '...' : count}
                </span>
              </button>
            );
          })}
        </div>
      )}
      
      {/* ✅ REMOVIDO: Botão de reação abaixo da mensagem - usar apenas botão direito */}
    </div>
  );
});
