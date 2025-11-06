/**
 * Menu de contexto para mensagens - Estilo WhatsApp
 * 
 * Opções:
 * - Dados da mensagem (Info)
 * - Responder
 * - Copiar
 * - Reagir (Emoji)
 * - Baixar (se tiver anexo)
 * - Encaminhar
 * - Fixar
 * - Favoritar
 * - Apagar
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Info,
  Reply,
  Copy,
  Smile,
  Download,
  Forward,
  Pin,
  Star,
  Trash2,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { EmojiPicker } from './EmojiPicker';
import type { Message } from '../types';

interface MessageContextMenuProps {
  message: Message;
  position: { x: number; y: number };
  onClose: () => void;
}

export function MessageContextMenu({ message, position, onClose }: MessageContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const { activeConversation, setMessages, messages } = useChatStore();

  // Fechar menu ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Ajustar posição do menu para não sair da tela
  const [adjustedPosition, setAdjustedPosition] = useState(position);
  useEffect(() => {
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      const windowWidth = window.innerWidth;
      const windowHeight = window.innerHeight;

      let x = position.x;
      let y = position.y;

      // Ajustar horizontalmente
      if (x + rect.width > windowWidth) {
        x = windowWidth - rect.width - 10;
      }
      if (x < 10) {
        x = 10;
      }

      // Ajustar verticalmente
      if (y + rect.height > windowHeight) {
        y = windowHeight - rect.height - 10;
      }
      if (y < 10) {
        y = 10;
      }

      setAdjustedPosition({ x, y });
    }
  }, [position]);

  // Verificar se mensagem tem anexos para mostrar opção de baixar
  const hasAttachments = message.attachments && message.attachments.length > 0;

  // Copiar mensagem
  const handleCopy = async () => {
    try {
      if (message.content) {
        await navigator.clipboard.writeText(message.content);
        toast.success('Mensagem copiada!');
      } else {
        toast.error('Mensagem sem conteúdo para copiar');
      }
      onClose();
    } catch (error) {
      console.error('❌ Erro ao copiar mensagem:', error);
      toast.error('Erro ao copiar mensagem');
    }
  };

  // Reagir (mostrar emoji picker)
  const handleReact = () => {
    setShowEmojiPicker(true);
  };

  // Adicionar reação
  const handleAddReaction = async (emoji: string) => {
    try {
      await api.post('/chat/reactions/add/', {
        message_id: message.id,
        emoji: emoji
      });
      setShowEmojiPicker(false);
      onClose();
    } catch (error) {
      console.error('❌ Erro ao adicionar reação:', error);
      toast.error('Erro ao adicionar reação');
    }
  };

  // Baixar anexo
  const handleDownload = async () => {
    if (!hasAttachments) {
      toast.error('Mensagem sem anexos para baixar');
      return;
    }

    try {
      // Baixar todos os anexos
      for (const attachment of message.attachments || []) {
        if (attachment.file_url) {
          const link = document.createElement('a');
          link.href = attachment.file_url;
          link.download = attachment.original_filename || `anexo-${attachment.id}`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        } else {
          toast.warning(`Anexo ${attachment.original_filename} ainda não está disponível`);
        }
      }
      onClose();
    } catch (error) {
      console.error('❌ Erro ao baixar anexo:', error);
      toast.error('Erro ao baixar anexo');
    }
  };

  // Encaminhar mensagem
  const handleForward = () => {
    // TODO: Implementar modal de encaminhamento
    toast.info('Funcionalidade de encaminhar em desenvolvimento');
    onClose();
  };

  // Fixar mensagem
  const handlePin = async () => {
    try {
      // TODO: Implementar endpoint de fixar mensagem
      toast.info('Funcionalidade de fixar em desenvolvimento');
      onClose();
    } catch (error) {
      console.error('❌ Erro ao fixar mensagem:', error);
      toast.error('Erro ao fixar mensagem');
    }
  };

  // Favoritar mensagem
  const handleFavorite = async () => {
    try {
      // TODO: Implementar endpoint de favoritar mensagem
      toast.info('Funcionalidade de favoritar em desenvolvimento');
      onClose();
    } catch (error) {
      console.error('❌ Erro ao favoritar mensagem:', error);
      toast.error('Erro ao favoritar mensagem');
    }
  };

  // Apagar mensagem
  const handleDelete = async () => {
    if (!confirm('Tem certeza que deseja apagar esta mensagem?')) {
      return;
    }

    try {
      // TODO: Implementar endpoint de apagar mensagem
      toast.info('Funcionalidade de apagar em desenvolvimento');
      onClose();
    } catch (error) {
      console.error('❌ Erro ao apagar mensagem:', error);
      toast.error('Erro ao apagar mensagem');
    }
  };

  // Dados da mensagem
  const handleInfo = () => {
    // TODO: Implementar modal com informações da mensagem
    toast.info('Funcionalidade de informações em desenvolvimento');
    onClose();
  };

  // Responder mensagem
  const handleReply = () => {
    // TODO: Implementar resposta a mensagem
    toast.info('Funcionalidade de responder em desenvolvimento');
    onClose();
  };

  return (
    <>
      <div
        ref={menuRef}
        className="fixed bg-white rounded-lg shadow-xl border border-gray-200 py-1 z-50 min-w-[200px]"
        style={{
          left: `${adjustedPosition.x}px`,
          top: `${adjustedPosition.y}px`,
        }}
      >
        {/* Dados da mensagem */}
        <button
          onClick={handleInfo}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Info className="w-4 h-4 text-gray-500" />
          <span>Dados da mensagem</span>
        </button>

        {/* Responder */}
        <button
          onClick={handleReply}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Reply className="w-4 h-4 text-gray-500" />
          <span>Responder</span>
        </button>

        {/* Copiar */}
        {message.content && (
          <button
            onClick={handleCopy}
            className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
          >
            <Copy className="w-4 h-4 text-gray-500" />
            <span>Copiar</span>
          </button>
        )}

        {/* Reagir */}
        <button
          onClick={handleReact}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Smile className="w-4 h-4 text-gray-500" />
          <span>Reagir</span>
        </button>

        {/* Baixar (apenas se tiver anexos) */}
        {hasAttachments && (
          <button
            onClick={handleDownload}
            className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
          >
            <Download className="w-4 h-4 text-gray-500" />
            <span>Baixar</span>
          </button>
        )}

        {/* Encaminhar */}
        <button
          onClick={handleForward}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Forward className="w-4 h-4 text-gray-500" />
          <span>Encaminhar</span>
        </button>

        {/* Fixar */}
        <button
          onClick={handlePin}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Pin className="w-4 h-4 text-gray-500" />
          <span>Fixar</span>
        </button>

        {/* Favoritar */}
        <button
          onClick={handleFavorite}
          className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
        >
          <Star className="w-4 h-4 text-gray-500" />
          <span>Favoritar</span>
        </button>

        {/* Apagar */}
        <button
          onClick={handleDelete}
          className="w-full px-4 py-2.5 text-left hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-3 text-sm text-red-600 dark:text-red-400"
        >
          <Trash2 className="w-4 h-4 text-red-500" />
          <span>Apagar</span>
        </button>
      </div>

      {/* Emoji Picker (quando Reagir é clicado) */}
      {showEmojiPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => setShowEmojiPicker(false)}>
          <div 
            className="bg-white rounded-lg shadow-lg border border-gray-300 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '320px',
              height: '280px'
            }}
          >
            <EmojiPicker
              onSelect={handleAddReaction}
              onClose={() => setShowEmojiPicker(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}

