/**
 * Lista de mensagens - Estilo WhatsApp Web
 */
import React, { useEffect, useRef } from 'react';
import { Check, CheckCheck, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { format } from 'date-fns';

export function MessageList() {
  const { activeConversation, messages, setMessages } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!activeConversation) return;

    const fetchMessages = async () => {
      try {
        const response = await api.get(`/chat/conversations/${activeConversation.id}/messages/`, {
          params: { ordering: 'created_at' }
        });
        const msgs = response.data.results || response.data;
        setMessages(msgs);
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      } catch (error) {
        console.error('❌ Erro ao carregar mensagens:', error);
      }
    };

    fetchMessages();
  }, [activeConversation, setMessages]);

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

  if (!activeConversation) {
    return null;
  }

  return (
    <div 
      className="h-full overflow-y-auto p-4 space-y-2"
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
                <p className="text-sm whitespace-pre-wrap break-words">
                  {msg.content}
                </p>
                
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
          <div ref={messagesEndRef} />
        </>
      )}
    </div>
  );
}
