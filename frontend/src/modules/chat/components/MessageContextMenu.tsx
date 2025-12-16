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
  Trash2,
  Edit,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { MessageInfoModal } from './MessageInfoModal';
import type { Message } from '../types';

interface MessageContextMenuProps {
  message: Message;
  position: { x: number; y: number };
  onClose: () => void;
  onShowInfo?: (message: Message) => void;
  onShowEmojiPicker?: (message: Message) => void;
  onShowForward?: (message: Message) => void;
  onShowEdit?: (message: Message) => void;
}

export function MessageContextMenu({ message, position, onClose, onShowInfo, onShowEmojiPicker, onShowForward, onShowEdit }: MessageContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [showInfoModal, setShowInfoModal] = useState(false);
  const { activeConversation, setMessages, getMessagesArray, setReplyToMessage } = useChatStore();
  const messages = activeConversation ? getMessagesArray(activeConversation.id) : [];

  // Validar position e usar valores padrão se inválida - DEFINIR PRIMEIRO
  const DEFAULT_POSITION = { x: 0, y: 0 };
  
  // Calcular safePosition de forma segura
  const getSafePosition = (pos: { x: number; y: number } | undefined | null): { x: number; y: number } => {
    if (!pos) return DEFAULT_POSITION;
    if (typeof pos.x !== 'number' || typeof pos.y !== 'number') {
      return DEFAULT_POSITION;
    }
    return { x: pos.x, y: pos.y };
  };

  // Ajustar posição do menu para não sair da tela - INICIALIZAR COM VALOR SEGURO
  const [adjustedPosition, setAdjustedPosition] = useState<{ x: number; y: number }>(() => {
    // Garantir que sempre retornamos um objeto válido
    const safe = getSafePosition(position);
    return { x: safe.x, y: safe.y };
  });

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
  
  useEffect(() => {
    // Recalcular safePosition sempre que position mudar
    const currentSafePosition = getSafePosition(position);
    
    // Verificação robusta antes de acessar propriedades
    if (typeof currentSafePosition.x !== 'number' || typeof currentSafePosition.y !== 'number') {
      setAdjustedPosition(DEFAULT_POSITION);
      return;
    }
    
    if (!menuRef.current) {
      // Se ainda não temos ref, usar posição segura diretamente
      setAdjustedPosition(currentSafePosition);
      return;
    }
    
    const rect = menuRef.current.getBoundingClientRect();
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;

    // Declarar x e y ANTES de usar - garantir inicialização explícita
    let x: number = currentSafePosition.x;
    let y: number = currentSafePosition.y;

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
  }, [position]);

  // Verificar se mensagem tem anexos para mostrar opção de baixar
  const hasAttachments = message.attachments && message.attachments.length > 0;
  
  // ✅ NOVO: Verificar se mensagem pode ser editada
  const canEdit = (() => {
    // Apenas mensagens enviadas (outgoing)
    if (message.direction !== 'outgoing') return false;
    
    // Deve ter message_id (foi enviada com sucesso)
    if (!message.message_id) return false;
    
    // Não pode ter anexos
    if (hasAttachments) return false;
    
    // Deve ter menos de 15 minutos desde o envio
    if (message.created_at) {
      const createdDate = new Date(message.created_at);
      const now = new Date();
      const minutesSinceSent = (now.getTime() - createdDate.getTime()) / (1000 * 60);
      if (minutesSinceSent > 15) return false;
    }
    
    return true;
  })();
  
  // Editar mensagem
  const handleEdit = () => {
    if (onShowEdit) {
      onShowEdit(message);
    }
    onClose();
  };

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
    if (onShowEmojiPicker) {
      // ✅ Usar callback do pai (MessageList) para renderizar picker fora do menu
      onShowEmojiPicker(message);
    }
    onClose();
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
    console.log('📤 [FORWARD] handleForward chamado');
    if (onShowForward) {
      // ✅ CORREÇÃO: Usar callback do pai (MessageList) para renderizar modal fora do menu
      onShowForward(message);
    }
    onClose();
  };


  // Apagar mensagem
  const handleDelete = async () => {
    if (!confirm('Tem certeza que deseja apagar esta mensagem?')) {
      return;
    }

    try {
      // ✅ IMPLEMENTADO: Endpoint de apagar mensagem
      await api.post(`/chat/messages/${message.id}/delete/`);
      toast.success('Mensagem apagada com sucesso');
      
      // Atualizar store para marcar como apagada
      const { updateMessageDeleted } = useChatStore.getState();
      updateMessageDeleted(message.id);
      
      onClose();
    } catch (error: any) {
      console.error('❌ Erro ao apagar mensagem:', error);
      const errorMessage = error.response?.data?.error || error.response?.data?.detail || 'Erro ao apagar mensagem';
      toast.error(errorMessage);
    }
  };

  // Dados da mensagem
  const handleInfo = () => {
    if (onShowInfo) {
      // Se tem callback do pai, usar ele (preferido)
      onShowInfo(message);
    } else {
      // Fallback: usar estado local
      setShowInfoModal(true);
    }
    onClose();
  };

  // Responder mensagem
  const handleReply = () => {
    setReplyToMessage(message);
    onClose();
    // ✅ Scroll para o input (será feito automaticamente pelo foco)
    setTimeout(() => {
      const input = document.querySelector('textarea[placeholder="Digite uma mensagem"]') as HTMLTextAreaElement;
      if (input) {
        input.focus();
        input.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }, 100);
  };

  return (
    <>
      <div
        ref={menuRef}
        className="fixed bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 z-[9999] min-w-[200px]"
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

        {/* Editar (apenas se pode editar) */}
        {canEdit && (
          <button
            onClick={handleEdit}
            className="w-full px-4 py-2.5 text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300"
          >
            <Edit className="w-4 h-4 text-gray-500" />
            <span>Editar</span>
          </button>
        )}

        {/* Apagar */}
        <button
          onClick={handleDelete}
          className="w-full px-4 py-2.5 text-left hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-3 text-sm text-red-600 dark:text-red-400"
        >
          <Trash2 className="w-4 h-4 text-red-500" />
          <span>Apagar</span>
        </button>
      </div>


      {/* Modal de Informações da Mensagem */}
      {showInfoModal && (
        <MessageInfoModal
          message={message}
          onClose={() => setShowInfoModal(false)}
        />
      )}

    </>
  );
}

