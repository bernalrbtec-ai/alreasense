/**
 * Lista de mensagens - Estilo WhatsApp Web
 */
import React, { useEffect, useRef } from 'react';
import { Check, CheckCheck, Clock, Download, FileText, Image as ImageIcon, Video, Music } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { format } from 'date-fns';
import type { MessageAttachment } from '../types';
import { AttachmentPreview } from './AttachmentPreview';
import { useUserAccess } from '@/hooks/useUserAccess';

export function MessageList() {
  const { activeConversation, messages, setMessages, typing, typingUser } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { canAccess: hasFlowAI } = useUserAccess('flow-ai');

  useEffect(() => {
    if (!activeConversation?.id) return;

    const fetchMessages = async () => {
      try {
        const response = await api.get(`/chat/conversations/${activeConversation.id}/messages/`, {
          params: { ordering: 'created_at' }
        });
        const msgs = response.data.results || response.data;
        
        // ✅ MELHORIA: Ao invés de setMessages (sobrescreve), fazer merge inteligente
        // para preservar attachments que foram atualizados via WebSocket
        const { messages: currentMessages } = useChatStore.getState();
        const mergedMessages = msgs.map(serverMsg => {
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
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } catch (error) {
        console.error('❌ Erro ao carregar mensagens:', error);
      }
    };

    fetchMessages();
  }, [activeConversation?.id, setMessages]);

  // Auto-scroll quando novas mensagens chegam
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-400" />;
      case 'sent':
        return <Check className="w-4 h-4 text-gray-400" />;
      case 'delivered':
        return <CheckCheck className="w-4 h-4 text-gray-400" />;
      case 'seen':
        return <CheckCheck className="w-4 h-4 text-blue-500" />;
      default:
        return null;
    }
  };

  const formatTime = (dateString: string) => {
    try {
      return format(new Date(dateString), 'HH:mm');
    } catch {
      return '';
    }
  };

  const getAttachmentIcon = (attachment: MessageAttachment) => {
    if (attachment.is_image) return <ImageIcon className="w-5 h-5" />;
    if (attachment.is_video) return <Video className="w-5 h-5" />;
    if (attachment.is_audio) return <Music className="w-5 h-5" />;
    return <FileText className="w-5 h-5" />;
  };

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
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full">
          <p className="text-sm text-gray-500">Nenhuma mensagem ainda. Comece a conversa!</p>
        </div>
      ) : (
        <>
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`
                  max-w-[65%] md:max-w-md rounded-lg px-3 py-2 shadow-sm
                  ${msg.direction === 'outgoing'
                    ? 'bg-[#d9fdd3] text-gray-900'
                    : 'bg-white text-gray-900'
                  }
                `}
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
                {msg.content && msg.content.trim() && (
                  <p className="text-sm whitespace-pre-wrap break-words mb-1">
                    {msg.content}
                  </p>
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
            </div>
          ))}
          
          {/* Indicador de digitando */}
          {typing && (
            <div className="flex justify-start">
              <div className="bg-white rounded-lg px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                  {typingUser && (
                    <span className="text-xs text-gray-500 ml-2">{typingUser} está digitando...</span>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
}
