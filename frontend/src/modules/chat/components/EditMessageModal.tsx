/**
 * Modal para editar mensagem enviada
 */
import React, { useState, useEffect } from 'react';
import { X, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { useChatStore } from '../store/chatStore';
import type { Message } from '../types';

interface EditMessageModalProps {
  message: Message;
  onClose: () => void;
}

export function EditMessageModal({ message, onClose }: EditMessageModalProps) {
  const [newContent, setNewContent] = useState(message.content || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { updateMessage, activeConversation } = useChatStore();

  useEffect(() => {
    // Focar no textarea ao abrir
    const textarea = document.querySelector('textarea[data-edit-message]') as HTMLTextAreaElement;
    if (textarea) {
      textarea.focus();
      // Mover cursor para o final
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newContent.trim()) {
      toast.error('Novo conteúdo não pode estar vazio');
      return;
    }
    
    if (newContent.trim() === message.content?.trim()) {
      toast.error('Novo conteúdo deve ser diferente do atual');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Chamar endpoint de edição
      await api.post(`/chat/messages/${message.id}/edit/`, {
        new_content: newContent.trim()
      });
      
      toast.success('Mensagem editada com sucesso!');
      
      // Atualizar mensagem no store (será atualizada via WebSocket também)
      if (activeConversation) {
        updateMessage(activeConversation.id, {
          ...message,
          content: newContent.trim()
        });
      }
      
      onClose();
    } catch (error: any) {
      console.error('❌ Erro ao editar mensagem:', error);
      const errorMessage = error.response?.data?.error || error.response?.data?.detail || 'Erro ao editar mensagem';
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter para enviar
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e);
    }
    // Escape para fechar
    if (e.key === 'Escape') {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Editar mensagem
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4">
          <textarea
            data-edit-message
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Digite o novo conteúdo da mensagem..."
            className="w-full min-h-[120px] px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            disabled={isSubmitting}
            autoFocus
          />
          
          <div className="mt-3 text-xs text-gray-500 dark:text-gray-400">
            <p>Pressione Ctrl/Cmd + Enter para salvar, ou Escape para cancelar</p>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
              disabled={isSubmitting}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !newContent.trim() || newContent.trim() === message.content?.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Salvando...</span>
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  <span>Salvar</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

