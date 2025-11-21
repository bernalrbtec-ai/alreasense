/**
 * Lista de mensagens - Estilo WhatsApp Web com UX Moderna
 * ✅ PERFORMANCE: Componente memoizado para evitar re-renders desnecessários
 */
import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { Check, CheckCheck, Clock, Download, FileText, Image as ImageIcon, Video, Music, Smile, Reply, User, Phone, Plus } from 'lucide-react';
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
import ContactModal from '@/components/contacts/ContactModal';

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
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactToAdd, setContactToAdd] = useState<{ name: string; phone: string } | null>(null);
  const updateMessageReactions = useChatStore((state) => state.updateMessageReactions);
  const { activeConversation, messages, setMessages, typing, typingUser } = useChatStore((state) => ({
    activeConversation: state.activeConversation,
    messages: state.messages,
    setMessages: state.setMessages,
    typing: state.typing,
    typingUser: state.typingUser,
  }));
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

    const fetchMessages = async (retryCount = 0) => {
      try {
        setIsLoading(true);
        setVisibleMessages(new Set()); // Reset visibilidade ao trocar conversa
        
        // ✅ CORREÇÃO: Se conversa é muito nova (< 5s), aguardar um pouco antes de buscar
        // Isso evita erro 404 quando conversa ainda está sendo criada no backend
        if (activeConversation.created_at && retryCount === 0) {
          const createdDate = new Date(activeConversation.created_at);
          const now = new Date();
          const ageInSeconds = (now.getTime() - createdDate.getTime()) / 1000;
          
          if (ageInSeconds < 5) {
            const waitTime = (5 - ageInSeconds) * 1000; // Aguardar até completar 5s
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
      } catch (error: any) {
        console.error('❌ Erro ao carregar mensagens:', error);
        
        // ✅ CORREÇÃO: Se erro 404 e conversa é nova, fazer retry com backoff exponencial
        // Isso trata o caso onde conversa ainda está sendo criada no backend
        if (error?.response?.status === 404 && retryCount < 3) {
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
        if (error?.response?.status === 404) {
          const { messages: wsMessages } = useChatStore.getState();
          const messagesFromConversation = wsMessages.filter(m => 
            (m.conversation === activeConversation.id) || 
            (typeof m.conversation === 'object' && m.conversation?.id === activeConversation.id)
          );
          
          if (messagesFromConversation.length > 0) {
            console.log(`✅ [MessageList] Usando ${messagesFromConversation.length} mensagem(ns) do WebSocket (conversa não encontrada na API)`);
            const sortedMsgs = sortMessagesByTimestamp(messagesFromConversation);
            setMessages(sortedMsgs);
            setHasMoreMessages(false);
            
            // Scroll to bottom
            setTimeout(() => {
              messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
            }, 100);
            return;
          }
        }
      } finally {
        if (retryCount === 0) {
          setIsLoading(false);
        }
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

  // ✅ Função para converter URLs em links clicáveis que abrem em nova aba
  const linkifyText = useCallback((text: string): string => {
    if (!text) return '';
    
    // Regex para detectar URLs (http, https, www, ou sem protocolo)
    const urlRegex = /(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}[^\s]*)/gi;
    
    // Primeiro, escapar HTML para segurança
    let escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
    
    // Converter URLs em links
    return escaped.replace(urlRegex, (url) => {
      // Adicionar https:// se não tiver protocolo
      let href = url;
      if (!url.match(/^https?:\/\//i)) {
        href = url.startsWith('www.') ? `https://${url}` : `https://${url}`;
      }
      
      // Validar URL antes de criar link
      try {
        new URL(href);
        return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline break-all">${url}</a>`;
      } catch {
        // Se não for URL válida, retornar texto original
        return url;
      }
    });
  }, []);

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
              className={`flex flex-col ${msg.direction === 'outgoing' ? 'items-end' : 'items-start'} ${
                visibleMessages.has(msg.id) 
                  ? 'opacity-100 translate-y-0' 
                  : 'opacity-0 translate-y-2'
              } transition-all duration-300 ease-out group group/message`}
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

                {/* ✅ NOVO: Preview de mensagem respondida (reply_to) */}
                {msg.metadata?.reply_to && (() => {
                  const replyToId = msg.metadata.reply_to;
                  const repliedMessage = messages.find(m => m.id === replyToId);
                  
                  if (repliedMessage) {
                    return (
                      <div className="mb-2 pl-3 border-l-4 border-l-blue-500 bg-gray-50 rounded-r-lg py-1.5">
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className="w-3 h-3 text-blue-500" />
                          <p className="text-xs font-medium text-blue-600">
                            {repliedMessage.direction === 'incoming' 
                              ? (repliedMessage.sender_name || repliedMessage.sender_phone || 'Contato')
                              : 'Você'}
                          </p>
                        </div>
                        <p className="text-xs text-gray-600 line-clamp-1">
                          {repliedMessage.content || (repliedMessage.attachments && repliedMessage.attachments.length > 0 ? '📎 Anexo' : 'Mensagem')}
                        </p>
                      </div>
                    );
                  }
                  return null;
                })()}
                
                {/* ✅ NOVO: Contato compartilhado */}
                {msg.metadata?.contact_message && (() => {
                  const contactData = msg.metadata.contact_message;
                  const phone = contactData.phone || '';
                  const name = contactData.name || contactData.display_name || 'Contato';
                  
                  // Formatar telefone para exibição
                  const formatPhone = (phone: string) => {
                    if (!phone) return '';
                    const clean = phone.replace(/\D/g, '');
                    if (clean.startsWith('55') && clean.length >= 12) {
                      const ddd = clean.substring(2, 4);
                      const num = clean.substring(4);
                      if (num.length === 9) {
                        return `(${ddd}) ${num.substring(0, 5)}-${num.substring(5)}`;
                      } else if (num.length === 8) {
                        return `(${ddd}) ${num.substring(0, 4)}-${num.substring(4)}`;
                      }
                    }
                    return phone;
                  };
                  
                  const formattedPhone = formatPhone(phone);
                  const whatsappLink = phone ? `https://wa.me/${phone.replace(/\+/g, '')}` : null;
                  
                  // ✅ Capturar setContactToAdd e setShowContactModal do escopo do componente
                  const handleAddContact = () => {
                    setContactToAdd({ name, phone });
                    setShowContactModal(true);
                  };
                  
                  return (
                    <div className="mb-2 border border-gray-200 rounded-lg p-3 bg-white shadow-sm">
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <User className="w-5 h-5 text-blue-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-gray-500 mb-1">📇 Contato compartilhado</div>
                          <div className="font-medium text-gray-900 mb-1">{name}</div>
                          {formattedPhone && (
                            <div className="text-sm text-gray-600 mb-2">{formattedPhone}</div>
                          )}
                          <div className="flex gap-2">
                            {whatsappLink && (
                              <a
                                href={whatsappLink}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-md transition-colors"
                              >
                                <Phone className="w-3 h-3" />
                                Iniciar conversa
                              </a>
                            )}
                            {phone && (
                              <button
                                onClick={handleAddContact}
                                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                              >
                                <Plus className="w-3 h-3" />
                                Adicionar
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })()}
                
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
                {/* ✅ FIX: Sanitizar conteúdo e converter URLs em links clicáveis */}
                {msg.content && msg.content.trim() && (
                  <p 
                    className="text-sm whitespace-pre-wrap break-words mb-1"
                    dangerouslySetInnerHTML={{ 
                      __html: linkifyText(msg.content)
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
              </div>
              
              {/* ✅ MELHORIA UX: Reações posicionadas como WhatsApp (ao final da mensagem, fora do card, alinhadas) */}
              <MessageReactions message={msg} direction={msg.direction} />
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
const MessageReactions = React.memo(function MessageReactions({ message, direction }: { message: any; direction: 'incoming' | 'outgoing' }) {
  const { user } = useAuthStore();
  const { messages, setMessages, updateMessageReactions } = useChatStore();
  const [hoveredEmoji, setHoveredEmoji] = useState<string | null>(null);
  const [processingEmoji, setProcessingEmoji] = useState<string | null>(null); // ✅ CORREÇÃO: Loading state


  // Reações agrupadas por emoji
  const reactionsSummary = message.reactions_summary || {};
  const hasReactions = Object.keys(reactionsSummary).length > 0;

  // Verificar se usuário já reagiu com cada emoji
  const getUserReaction = (emoji: string): MessageReaction | null => {
    if (!message.reactions || !user) return null;
    return message.reactions.find((r: MessageReaction) => r.emoji === emoji && r.user === user.id) || null;
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
    if (!user || processingEmoji) return; // ✅ CORREÇÃO: Prevenir duplo clique
    
    // ✅ CORREÇÃO: Validar emoji antes de enviar
    if (!validateEmoji(emoji)) {
      console.warn('⚠️ [REACTION] Emoji inválido:', emoji);
      return;
    }
    
    setProcessingEmoji(emoji); // ✅ CORREÇÃO: Feedback visual
    
    const currentStoreMessage = useChatStore
      .getState()
      .messages.find((m) => m.id === message.id);
    const previousReactions = cloneReactions(currentStoreMessage?.reactions);
    
    // ✅ CORREÇÃO CRÍTICA: Verificar se usuário já reagiu com este emoji
    const userReaction = previousReactions.find(
      (reaction) => reaction.user === String(user.id) && reaction.emoji === emoji
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
      (reaction) => reaction.user === String(user.id) && reaction.emoji !== emoji
    );
    
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

    // ✅ CORREÇÃO: Remover reação antiga do usuário (se existir) e adicionar nova
    const optimisticReactions = [
      ...previousReactions.filter(
        (reaction) => reaction.user !== String(user.id) // Remover TODAS as reações do usuário
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
          {Object.entries(reactionsSummary).map(([emoji, data]: [string, any]) => {
            const userReaction = getUserReaction(emoji);
            const isUserReaction = !!userReaction;
            
            return (
              <button
                key={emoji}
                onClick={() => handleToggleReaction(emoji)}
                onMouseEnter={() => setHoveredEmoji(emoji)}
                onMouseLeave={() => setHoveredEmoji(null)}
                disabled={processingEmoji === emoji}
                className={`
                  px-2 py-0.5 rounded-full text-xs flex items-center gap-1 transition-all
                  ${processingEmoji === emoji ? 'opacity-50 cursor-wait' : 'cursor-pointer'}
                  ${isUserReaction
                    ? 'bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-700'
                    : 'bg-gray-100 dark:bg-gray-700/50 hover:bg-gray-200 dark:hover:bg-gray-600/50'
                  }
                `}
                title={`${data.count} ${data.count === 1 ? 'reação' : 'reações'}: ${data.users.map((u: any) => u.email || u.first_name || 'Usuário').join(', ')}`}
              >
                <span className="text-sm">{emoji}</span>
                <span className={`text-xs font-medium ${isUserReaction ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}`}>
                  {processingEmoji === emoji ? '...' : data.count}
                </span>
              </button>
            );
          })}
        </div>
      )}
      
      {/* ✅ REMOVIDO: Botão de reação abaixo da mensagem - usar apenas botão direito */}
      
      {/* Modal para adicionar contato compartilhado */}
      {showContactModal && contactToAdd && (
        <ContactModal
          isOpen={showContactModal}
          onClose={() => {
            setShowContactModal(false);
            setContactToAdd(null);
          }}
          initialName={contactToAdd.name}
          initialPhone={contactToAdd.phone}
          onSuccess={() => {
            setShowContactModal(false);
            setContactToAdd(null);
          }}
        />
      )}
    </div>
  );
}
