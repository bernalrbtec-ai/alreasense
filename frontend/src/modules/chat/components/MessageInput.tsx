/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, Paperclip, User } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import { VoiceRecorder } from './VoiceRecorder';

interface MessageInputProps {
  sendMessage: (content: string, includeSignature?: boolean) => boolean;
  sendTyping: (isTyping: boolean) => void;
  isConnected: boolean;
}

export function MessageInput({ sendMessage, sendTyping, isConnected }: MessageInputProps) {
  const { activeConversation } = useChatStore();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [includeSignature, setIncludeSignature] = useState(true); // ✅ Assinatura habilitada por padrão
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
      
      const success = sendMessage(message.trim(), includeSignature);
      
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
      {/* Attach button (placeholder) */}
      <button
        className="p-2 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
        title="Anexar arquivo"
      >
        <Paperclip className="w-6 h-6 text-gray-600" />
      </button>

      {/* Emoji button */}
      <button
        className="p-2 hover:bg-gray-200 rounded-full transition-colors flex-shrink-0"
        title="Emoji"
      >
        <Smile className="w-6 h-6 text-gray-600" />
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

      {/* Toggle de Assinatura */}
      <button
        onClick={() => setIncludeSignature(!includeSignature)}
        className={`
          p-2 rounded-full transition-colors flex-shrink-0
          ${includeSignature 
            ? 'text-green-600 hover:bg-green-100 bg-green-50' 
            : 'text-gray-500 hover:bg-gray-200'
          }
        `}
        title={includeSignature ? 'Assinatura ativada - clique para desativar' : 'Assinatura desativada - clique para ativar'}
      >
        <User className="w-5 h-5" />
      </button>

      {/* Voice Recorder button - ao lado do Send */}
      <VoiceRecorder
        conversationId={activeConversation.id}
        onRecordingComplete={() => {
          console.log('✅ Áudio enviado! WebSocket vai atualizar UI');
        }}
      />

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
