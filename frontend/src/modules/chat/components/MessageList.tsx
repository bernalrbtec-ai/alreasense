/**
 * Lista de mensagens (bolhas estilo WhatsApp)
 */
import React, { useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { StatusIcon } from './StatusIcon';
import { Loader2, Download, FileText, Image as ImageIcon, Video, Music } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Message } from '../types';

export function MessageList() {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = React.useState(true);
  
  const {
    activeConversation,
    messages,
    setMessages,
    typing,
    typingUser
  } = useChatStore();

  // Carregar mensagens quando conversa mudar
  useEffect(() => {
    if (!activeConversation) return;

    const fetchMessages = async () => {
      try {
        setLoading(true);
        const response = await api.get('/api/chat/messages/', {
          params: {
            conversation: activeConversation.id,
            ordering: 'created_at'
          }
        });
        
        const msgs = response.data.results || response.data;
        setMessages(msgs);
        
        console.log('✅ Mensagens carregadas:', msgs.length);
      } catch (error) {
        console.error('❌ Erro ao carregar mensagens:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [activeConversation, setMessages]);

  // Auto-scroll para última mensagem
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (!activeConversation) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-[#0e1115] text-gray-500">
        <MessageCircleIcon className="w-16 h-16 mb-4 text-gray-700" />
        <p className="text-lg">Selecione uma conversa</p>
        <p className="text-sm">Escolha uma conversa da lista para começar</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-[#0e1115]">
        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0e1115] space-y-4">
      {messages.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>Nenhuma mensagem ainda. Comece a conversar!</p>
        </div>
      ) : (
        messages.map((message, index) => {
          const showDateSeparator = index === 0 || 
            !isSameDay(messages[index - 1].created_at, message.created_at);
          
          return (
            <React.Fragment key={message.id}>
              {showDateSeparator && (
                <DateSeparator date={message.created_at} />
              )}
              <MessageBubble message={message} />
            </React.Fragment>
          );
        })
      )}

      {/* Indicador de digitando */}
      {typing && (
        <div className="flex items-center gap-2 px-4 py-2 bg-[#2b2f36] rounded-lg w-fit">
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-xs text-gray-400">
            {typingUser || 'Alguém'} está digitando...
          </span>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
}

function MessageBubble({ message }: MessageBubbleProps) {
  const isOutgoing = message.direction === 'outgoing';
  const isInternal = message.is_internal;

  return (
    <div className={`flex ${isOutgoing ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`
        max-w-[75%] rounded-lg px-4 py-2 shadow-lg
        ${isInternal 
          ? 'bg-yellow-900/30 border border-yellow-700/50' 
          : isOutgoing 
            ? 'bg-[#2f7d32]' 
            : 'bg-[#2b2f36]'
        }
      `}>
        {/* Remetente (se incoming) */}
        {!isOutgoing && message.sender_data && (
          <p className="text-xs text-gray-400 mb-1">
            {message.sender_data.first_name || message.sender_data.email}
          </p>
        )}

        {/* Nota interna badge */}
        {isInternal && (
          <span className="inline-block px-2 py-0.5 bg-yellow-700 text-yellow-100 text-xs rounded mb-2">
            📝 Nota Interna
          </span>
        )}

        {/* Anexos */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mb-2 space-y-2">
            {message.attachments.map((attachment) => (
              <AttachmentPreview key={attachment.id} attachment={attachment} />
            ))}
          </div>
        )}

        {/* Conteúdo */}
        {message.content && (
          <p className="text-white text-sm whitespace-pre-wrap break-words">
            {message.content}
          </p>
        )}

        {/* Footer: hora + status */}
        <div className="flex items-center justify-end gap-1 mt-1">
          <span className="text-xs text-gray-400">
            {format(new Date(message.created_at), 'HH:mm', { locale: ptBR })}
          </span>
          {isOutgoing && !isInternal && (
            <StatusIcon status={message.status} />
          )}
        </div>
      </div>
    </div>
  );
}

function AttachmentPreview({ attachment }: { attachment: any }) {
  const getIcon = () => {
    if (attachment.is_image) return <ImageIcon className="w-4 h-4" />;
    if (attachment.is_video) return <Video className="w-4 h-4" />;
    if (attachment.is_audio) return <Music className="w-4 h-4" />;
    return <FileText className="w-4 h-4" />;
  };

  return (
    <a
      href={attachment.file_url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-2 p-2 bg-black/20 rounded hover:bg-black/30 transition-colors"
    >
      {getIcon()}
      <span className="text-xs text-gray-300 flex-1 truncate">
        {attachment.original_filename}
      </span>
      <Download className="w-3 h-3 text-gray-400" />
    </a>
  );
}

function DateSeparator({ date }: { date: string }) {
  const formatted = format(new Date(date), "d 'de' MMMM", { locale: ptBR });
  
  return (
    <div className="flex items-center justify-center my-4">
      <span className="px-4 py-1 bg-[#1f262e] text-gray-400 text-xs rounded-full">
        {formatted}
      </span>
    </div>
  );
}

function isSameDay(date1: string, date2: string): boolean {
  const d1 = new Date(date1);
  const d2 = new Date(date2);
  return d1.toDateString() === d2.toDateString();
}

function MessageCircleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  );
}

