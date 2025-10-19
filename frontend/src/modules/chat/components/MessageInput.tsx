/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, Paperclip } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';

interface MessageInputProps {
  sendMessage: (content: string) => boolean;
  sendTyping: (isTyping: boolean) => void;
  isConnected: boolean;
}

export function MessageInput({ sendMessage, sendTyping, isConnected }: MessageInputProps) {
  const { activeConversation } = useChatStore();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Limpar timeout de digitando ao desmontar
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        sendTyping(false);
      }
    };
  }, [sendTyping]);

  const handleMessageChange = useCallback((value: string) => {
    setMessage(value);
    
    // Enviar "digitando" quando começa a digitar
    if (value.length > 0 && isConnected) {
      sendTyping(true);
      
      // Limpar timeout anterior
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
      // Parar de enviar "digitando" após 3 segundos de inatividade
      typingTimeoutRef.current = setTimeout(() => {
        sendTyping(false);
      }, 3000);
    } else if (value.length === 0) {
      // Parar de enviar "digitando" quando apaga tudo
      sendTyping(false);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    }
  }, [isConnected, sendTyping]);

  const handleSend = () => {
    if (!message.trim() || !activeConversation || sending || !isConnected) return;

    try {
      setSending(true);
      
      // Parar "digitando" antes de enviar
      sendTyping(false);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
      const success = sendMessage(message.trim());
      
      if (success) {
        setMessage('');
      } else {
        toast.error('Erro ao enviar mensagem. WebSocket desconectado.');
      }
    } catch (error: any) {
      console.error('Erro ao enviar mensagem:', error);
      toast.error('Erro ao enviar mensagem');
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
          onChange={(e) => handleMessageChange(e.target.value)}
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
        disabled={!message.trim() || sending || !isConnected}
        className="p-2 bg-[#00a884] hover:bg-[#008f6f] rounded-full transition-colors flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        title={isConnected ? "Enviar" : "Conectando..."}
      >
        <Send className="w-6 h-6 text-white" />
      </button>
    </div>
  );
}
