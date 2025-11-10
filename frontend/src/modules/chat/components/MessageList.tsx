/**
 * Lista de mensagens - Estilo WhatsApp Web com UX Moderna
 * ✅ PERFORMANCE: Componente memoizado para evitar re-renders desnecessários
 */
import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { Check, CheckCheck, Clock, Download, FileText, Image as ImageIcon, Video, Music, Smile } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { format } from 'date-fns';
import type { MessageAttachment, MessageReaction } from '../types';
import { AttachmentPreview } from './AttachmentPreview';
import { useUserAccess } from '@/hooks/useUserAccess';
import { sortMessagesByTimestamp } from '../utils/messageUtils';
import { EmojiPicker } from './EmojiPicker';
import { useAuthStore } from '@/stores/authStore';
import { MessageContextMenu } from './MessageContextMenu';
import type { Message } from '../types';

type ReactionsSummary = NonNullable<Message['reactions_summary']>;

const cloneReactions = (reactions?: MessageReaction[] | null): MessageReaction[] =>
  reactions
    ? reactions.map((reaction) => ({
        ...reaction,
        user_data: reaction.user_data ? { ...reaction.user_data } : undefined,
      }))
    : [];

const buildSummaryFromReactions = (reactions: MessageReaction[]): ReactionsSummary => {
  return reactions.reduce((acc, reaction) => {
    if (!acc[reaction.emoji]) {
      acc[reaction.emoji] = { count: 0, users: [] };
    }

    acc[reaction.emoji].count += 1;
    acc[reaction.emoji].users.push({
      id: reaction.user,
      email: reaction.user_data?.email || '',
      first_name: reaction.user_data?.first_name,
      last_name: reaction.user_data?.last_name,
    });

    return acc;
  }, {} as ReactionsSummary);
};

export function MessageList() {
  const {
    activeConversation,
    messages,
    setMessages,
    typing,
    typingUser,
    updateMessageReactions,
  } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesStartRef = useRef<HTMLDivElement>(null); // ✅ NOVO: Ref para topo (lazy loading)
  const { canAccess: hasFlowAI } = useUserAccess('flow-ai');
  const [visibleMessages, setVisibleMessages] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false); // ✅ NOVO: Paginação
  const [loadingOlder, setLoadingOlder] = useState(false); // ✅ NOVO: Loading mensagens antigas
  const [contextMenu, setContextMenu] = useState<{ message: Message; position: { x: number; y: number } } | null>(null);

  useEffect(() => {
    if (!activeConversation?.id) return;

    const fetchMessages = async () => {
      try {
        setIsLoading(true);
        setVisibleMessages(new Set()); // Reset visibilidade ao trocar conversa
        
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
        
        // ✅ FIX: Ordenar mensagens por timestamp antes de fazer merge
        // Isso garante que mensagens fora de ordem sejam ordenadas corretamente
        const sortedMsgs = sortMessagesByTimestamp(msgs);
        
        // ✅ MELHORIA: Ao invés de setMessages (sobrescreve), fazer merge inteligente
        // para preservar attachments que foram atualizados via WebSocket
        const { messages: currentMessages } = useChatStore.getState();
        const mergedMessages = sortedMsgs.map(serverMsg => {
          const existingMsg = currentMessages.find(m => m.id === serverMsg.id);
          if (existingMsg && existingMsg.attachments && existingMsg.attachments.length > 0) {
            // Se mensagem existente tem attachments atualizados, preservar
            const serverAttachments = serverMsg.attachments || [];
            const mergedAttachments = existingMsg.attachments.map(existingAtt => {
              const serverAtt = serverAttachments.find(a => a.id === existingAtt.id);
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
            const existingAttachmentIds = new Set(mergedAttachments.map(a => a.id));
            serverAttachments.forEach(serverAtt => {
              if (!existingAttachmentIds.has(serverAtt.id)) {
                mergedAttachments.push(serverAtt);
              }
            });
            
            return { ...serverMsg, attachments: mergedAttachments };
          }
          return serverMsg; // Nova mensagem ou sem attachments, usar do servidor
        });
        
        setMessages(mergedMessages);
        
        // ✅ PERFORMANCE: Animar mensagens em batch (mais rápido)
        // Reduzido delay de 20ms para 10ms e limita animação a 15 mensagens
        setTimeout(() => {
          const messagesToAnimate = mergedMessages.slice(-15); // Apenas últimas 15 para não demorar muito
          messagesToAnimate.forEach((msg, index) => {
            setTimeout(() => {
              setVisibleMessages(prev => new Set([...prev, msg.id]));
            }, index * 10); // ✅ Reduzido de 20ms para 10ms
          });
          
          // Adicionar mensagens restantes imediatamente (sem animação)
          if (mergedMessages.length > 15) {
            const restMessages = mergedMessages.slice(0, -15);
            restMessages.forEach(msg => {
              setVisibleMessages(prev => new Set([...prev, msg.id]));
            });
          }
        }, 50);
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
        
        // ✅ FIX CRÍTICO: Se conversa não tem mensagens e foi criada recentemente (< 60s), 
        // fazer múltiplos re-fetches para pegar mensagem que pode estar sendo processada
        if (mergedMessages.length === 0 && activeConversation.created_at) {
          const createdDate = new Date(activeConversation.created_at);
          const now = new Date();
          const ageInSeconds = (now.getTime() - createdDate.getTime()) / 1000;
          
          if (ageInSeconds < 60) {
            console.log(`🔄 [MessageList] Conversa nova sem mensagens (${Math.round(ageInSeconds)}s), fazendo re-fetches...`);
            
            // ✅ FIX: Fazer múltiplos retries com intervalos crescentes
            const retryDelays = [1000, 2000, 3000, 5000]; // 1s, 2s, 3s, 5s
            
            retryDelays.forEach((delay, index) => {
              setTimeout(async () => {
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
                    setMessages(retryMsgs);
                    setHasMoreMessages(retryData.has_more || false);
                    
                    // Scroll to bottom
                    setTimeout(() => {
                      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
                    }, 100);
                    
                    // Parar outros retries
                    return;
                  } else if (index === retryDelays.length - 1) {
                    console.log(`⚠️ [MessageList] Nenhum retry encontrou mensagens após ${retryDelays.length} tentativas`);
                  }
                } catch (error) {
                  console.error(`❌ [MessageList] Erro no re-fetch #${index + 1}:`, error);
                }
              }, delay);
            });
          }
        }
      } catch (error) {
        console.error('❌ Erro ao carregar mensagens:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMessages();
  }, [activeConversation?.id, activeConversation?.created_at, setMessages]);

  // Auto-scroll quando novas mensagens chegam + fade-in para novas mensagens
  useEffect(() => {
    if (messages.length === 0) return;
    
    // Identificar novas mensagens (não visíveis ainda)
    const newMessages = messages.filter(msg => !visibleMessages.has(msg.id));
    
    if (newMessages.length > 0) {
      // Adicionar fade-in para novas mensagens
      newMessages.forEach((msg, index) => {
        setTimeout(() => {
          setVisibleMessages(prev => new Set([...prev, msg.id]));
        }, index * 50); // 50ms entre cada nova mensagem
      });
    }
    
    // Scroll suave ao final
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, [messages, visibleMessages]);

  // ✅ PERFORMANCE: Memoizar funções para evitar recriação a cada render
  const getStatusIcon = useCallback((status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-400 animate-pulse" />;
      case 'sent':
        return <Check className="w-4 h-4 text-gray-400" />;
      case 'delivered':
        return <CheckCheck className="w-4 h-4 text-gray-500" />;
      case 'seen':
        return <CheckCheck className="w-4 h-4 text-blue-500" />;
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
          <p className="text-sm font-medium truncate">
            {attachment.original_filename}
          </p>
          <p className="text-xs text-gray-500">
            {isDownloading ? 'Baixando...' : formatFileSize(attachment.size_bytes)}
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
      ) : messages.length === 0 ? (
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
                      // Adicionar mensagens antigas no início
                      setMessages([...olderMsgs.reverse(), ...messages]);
                      setHasMoreMessages(data.has_more || false);
                      
                      // Manter scroll na posição atual (sem pular para o topo)
                      const container = messagesStartRef.current?.parentElement;
                      if (container) {
                        const scrollHeightBefore = container.scrollHeight;
                        setTimeout(() => {
                          const scrollHeightAfter = container.scrollHeight;
                          const scrollDiff = scrollHeightAfter - scrollHeightBefore;
                          container.scrollTop += scrollDiff;
                        }, 0);
                      }
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
          
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'} ${
                visibleMessages.has(msg.id) 
                  ? 'opacity-100 translate-y-0' 
                  : 'opacity-0 translate-y-2'
              } transition-all duration-300 ease-out group`}
            >
              <div
                className={`
                  max-w-[65%] md:max-w-md rounded-2xl px-4 py-2.5 shadow-md
                  transform transition-all duration-200 hover:shadow-lg cursor-pointer
                  ${msg.direction === 'outgoing'
                    ? 'bg-[#d9fdd3] text-gray-900'
                    : 'bg-white text-gray-900'
                  }
                `}
                onContextMenu={(e) => {
                  e.preventDefault();
                  setContextMenu({
                    message: msg,
                    position: { x: e.clientX, y: e.clientY }
                  });
                }}
              >
                {/* Nome do remetente (apenas para GRUPOS e mensagens RECEBIDAS) */}
                {activeConversation.conversation_type === 'group' && msg.direction === 'incoming' && (msg.sender_name || msg.sender_phone) && (
                  <p className="text-xs font-semibold text-green-600 mb-1">
                    {msg.sender_name || msg.sender_phone}
                  </p>
                )}
                
                {/* Anexos - renderizar ANTES do texto */}
                {msg.attachments && msg.attachments.length > 0 && (
                  <div className="message-attachments mb-2 space-y-2">
                    {msg.attachments.map((attachment) => (
                      <AttachmentPreview
                        key={attachment.id}
                        attachment={attachment}
                        showAI={hasFlowAI}
                      />
                    ))}
                  </div>
                )}

                {/* Texto (se houver) - mostrar mesmo se só tiver anexos */}
                {/* ✅ FIX: Sanitizar conteúdo para prevenir XSS */}
                {msg.content && msg.content.trim() && (
                  <p 
                    className="text-sm whitespace-pre-wrap break-words mb-1"
                    dangerouslySetInnerHTML={{ 
                      __html: msg.content
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;')
                        .replace(/"/g, '&quot;')
                        .replace(/'/g, '&#039;')
                    }}
                  />
                )}
                
                <div className={`flex items-center gap-1 justify-end mt-1 ${msg.direction === 'outgoing' ? '' : 'opacity-60'}`}>
                  <span className="text-xs text-gray-600">
                    {formatTime(msg.created_at)}
                  </span>
                  {msg.direction === 'outgoing' && (
                    <span className="flex-shrink-0">
                      {getStatusIcon(msg.status)}
                    </span>
                  )}
                </div>
                
                {/* ✅ NOVO: Reações de mensagem */}
                <MessageReactions message={msg} />
              </div>
            </div>
          ))}
          
          {/* Indicador de digitando - Melhorado */}
          {typing && (
            <div className="flex justify-start animate-fade-in">
              <div className="bg-white rounded-2xl px-4 py-3 shadow-md">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1 px-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                  {typingUser && (
                    <span className="text-xs text-gray-500">{typingUser} está digitando...</span>
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
const MessageReactions = React.memo(function MessageReactions({ message }: { message: any }) {
  const { user } = useAuthStore();
  const { messages, setMessages } = useChatStore();
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [hoveredEmoji, setHoveredEmoji] = useState<string | null>(null);
  const [processingEmoji, setProcessingEmoji] = useState<string | null>(null); // ✅ CORREÇÃO: Loading state
  const pickerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Fechar picker ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        pickerRef.current &&
        !pickerRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setShowEmojiPicker(false);
      }
    };

    if (showEmojiPicker) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showEmojiPicker]);

  // Reações agrupadas por emoji
  const reactionsSummary = message.reactions_summary || {};
  const hasReactions = Object.keys(reactionsSummary).length > 0;

  // Verificar se usuário já reagiu com cada emoji
  const getUserReaction = (emoji: string): MessageReaction | null => {
    if (!message.reactions || !user) return null;
    return message.reactions.find((r: MessageReaction) => r.emoji === emoji && r.user === user.id) || null;
  };

  // Adicionar reação
  const handleAddReaction = async (emoji: string) => {
    if (!user || processingEmoji) return; // ✅ CORREÇÃO: Prevenir duplo clique
    
    setProcessingEmoji(emoji); // ✅ CORREÇÃO: Feedback visual
    
    const currentStoreMessage = useChatStore
      .getState()
      .messages.find((m) => m.id === message.id);
    const previousReactions = cloneReactions(currentStoreMessage?.reactions);
    const optimisticReaction: MessageReaction = {
      id: `optimistic-${user.id}-${emoji}-${Date.now()}`,
      message: message.id,
      user: String(user.id),
      user_data: {
        id: String(user.id),
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
      },
      emoji,
      created_at: new Date().toISOString(),
    };

    const optimisticReactions = [
      ...previousReactions.filter(
        (reaction) => !(reaction.user === String(user.id) && reaction.emoji === emoji)
      ),
      optimisticReaction,
    ];

    const optimisticSummary = buildSummaryFromReactions(optimisticReactions);

    updateMessageReactions(message.id, optimisticReactions, optimisticSummary);

    try {
      const response = await api.post('/chat/reactions/add/', {
        message_id: message.id,
        emoji: emoji,
      });

      if (response.data?.message) {
        updateMessageReactions(
          response.data.message.id,
          cloneReactions(response.data.message.reactions),
          response.data.message.reactions_summary || {}
        );
      }
      setShowEmojiPicker(false);
    } catch (error) {
      console.error('❌ Erro ao adicionar reação:', error);
      updateMessageReactions(
        message.id,
        previousReactions,
        buildSummaryFromReactions(previousReactions)
      );
    } finally {
      setProcessingEmoji(null); // ✅ CORREÇÃO: Remover loading state
    }
  };

  // Remover reação
  const handleRemoveReaction = async (emoji: string) => {
    if (!user || processingEmoji) return; // ✅ CORREÇÃO: Prevenir duplo clique
    
    setProcessingEmoji(emoji); // ✅ CORREÇÃO: Feedback visual
    
    const currentStoreMessage = useChatStore
      .getState()
      .messages.find((m) => m.id === message.id);
    const previousReactions = cloneReactions(currentStoreMessage?.reactions);

    const optimisticReactions = previousReactions.filter(
      (reaction) => !(reaction.emoji === emoji && reaction.user === String(user.id))
    );
    const optimisticSummary = buildSummaryFromReactions(optimisticReactions);

    updateMessageReactions(message.id, optimisticReactions, optimisticSummary);

    try {
      await api.post('/chat/reactions/remove/', {
        message_id: message.id,
        emoji: emoji,
      });
    } catch (error) {
      console.error('❌ Erro ao remover reação:', error);
      updateMessageReactions(
        message.id,
        previousReactions,
        buildSummaryFromReactions(previousReactions)
      );
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

  if (!hasReactions && !showEmojiPicker) {
    // Mostrar apenas botão de adicionar reação se não houver reações
    return (
      <div className="mt-2 flex items-center gap-1">
        <div className="relative">
          <button
            ref={buttonRef}
            onClick={() => setShowEmojiPicker(!showEmojiPicker)}
            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors opacity-0 group-hover:opacity-100"
            title="Adicionar reação"
          >
            <Smile className="w-4 h-4 text-gray-500" />
          </button>
          {showEmojiPicker && (
            <div ref={pickerRef} className="absolute bottom-full left-0 mb-2 z-50">
              <EmojiPicker
                onSelect={(emoji) => {
                  handleAddReaction(emoji);
                  setShowEmojiPicker(false);
                }}
                onClose={() => setShowEmojiPicker(false)}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 flex items-center gap-1 flex-wrap">
      {/* Reações existentes */}
      {Object.entries(reactionsSummary).map(([emoji, data]: [string, any]) => {
        const userReaction = getUserReaction(emoji);
        const isUserReaction = !!userReaction;
        
        return (
          <button
            key={emoji}
            onClick={() => handleToggleReaction(emoji)}
            onMouseEnter={() => setHoveredEmoji(emoji)}
            onMouseLeave={() => setHoveredEmoji(null)}
            disabled={processingEmoji === emoji} // ✅ CORREÇÃO: Desabilitar durante processamento
            className={`
              px-2 py-1 rounded-full text-xs flex items-center gap-1.5 transition-all
              ${processingEmoji === emoji ? 'opacity-50 cursor-wait' : ''}
              ${isUserReaction
                ? 'bg-blue-100 dark:bg-blue-900 border border-blue-300 dark:border-blue-700'
                : 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600'
              }
            `}
            title={`${data.count} ${data.count === 1 ? 'reação' : 'reações'}: ${data.users.map((u: any) => u.email).join(', ')}`}
          >
            <span className="text-base">{emoji}</span>
            <span className={`text-xs font-medium ${isUserReaction ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
              {processingEmoji === emoji ? '...' : data.count} {/* ✅ CORREÇÃO: Feedback visual */}
            </span>
          </button>
        );
      })}
      
      {/* Botão de adicionar reação */}
      <div className="relative">
        <button
          ref={buttonRef}
          onClick={() => setShowEmojiPicker(!showEmojiPicker)}
          className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full transition-colors"
          title="Adicionar reação"
        >
          <Smile className="w-4 h-4 text-gray-500" />
        </button>
        {showEmojiPicker && (
          <div ref={pickerRef} className="absolute bottom-full left-0 mb-2 z-50">
            <EmojiPicker
              onSelect={(emoji) => {
                handleAddReaction(emoji);
                setShowEmojiPicker(false);
              }}
              onClose={() => setShowEmojiPicker(false)}
            />
          </div>
        )}
      </div>
    </div>
  );
}); // ✅ CORREÇÃO: Fechar React.memo
