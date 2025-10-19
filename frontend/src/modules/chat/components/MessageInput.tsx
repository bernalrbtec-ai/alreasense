/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState } from 'react';
import { Send, Smile, Paperclip } from 'lucide-react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';

export function MessageInput() {
  const { activeConversation } = useChatStore();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!message.trim() || !activeConversation || sending) return;

    try {
      setSending(true);
      
      await api.post(`/chat/conversations/${activeConversation.id}/messages/`, {
        content: message.trim(),
        direction: 'outgoing'
      });

      setMessage('');
    } catch (error: any) {
      console.error('Erro ao enviar mensagem:', error);
      toast.error(error.response?.data?.error || 'Erro ao enviar mensagem');
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!activeConversation) {
    return null;
  }

  return (
    <div className="flex items-end gap-2 px-4 py-3 bg-[#f0f2f5] border-t border-gray-300">
      {/* Emoji button */}
      <button
        className="p-2 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
        title="Emoji"
      >
        <Smile className="w-6 h-6 text-gray-600" />
      </button>

      {/* Attach button */}
      <button
        className="p-2 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
        title="Anexar"
      >
        <Paperclip className="w-6 h-6 text-gray-600" />
      </button>

      {/* Input */}
      <div className="flex-1 bg-white rounded-lg shadow-sm">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Digite uma mensagem"
          rows={1}
          className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 placeholder-gray-500"
          style={{
            maxHeight: '120px',
            minHeight: '44px'
          }}
          disabled={sending}
        />
      </div>

      {/* Send button */}
      <button
        onClick={handleSend}
        disabled={!message.trim() || sending}
        className="p-2 bg-[#00a884] hover:bg-[#008f6f] rounded-full transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        title="Enviar"
      >
        <Send className="w-6 h-6 text-white" />
      </button>
    </div>
  );
}
