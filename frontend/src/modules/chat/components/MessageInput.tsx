/**
 * Input de mensagem com upload
 */
import React, { useState, useRef } from 'react';
import { api } from '@/lib/api';
import { useChatStore } from '../store/chatStore';
import { Paperclip, Send, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export function MessageInput() {
  const [content, setContent] = useState('');
  const [uploading, setUploading] = useState(false);
  const [attachmentPreview, setAttachmentPreview] = useState<{
    url: string;
    filename: string;
    size: number;
  } | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const { activeConversation, addMessage } = useChatStore();

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validar tamanho (50MB)
    if (file.size > 50 * 1024 * 1024) {
      toast.error('Arquivo muito grande (máx 50MB)');
      return;
    }

    try {
      setUploading(true);
      
      const formData = new FormData();
      formData.append('file', file);

      const response = await api.post('/api/chat/attachments/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setAttachmentPreview({
        url: response.data.url,
        filename: response.data.filename,
        size: response.data.size
      });

      toast.success('Arquivo carregado! ✅');
    } catch (error: any) {
      console.error('Erro no upload:', error);
      toast.error(error.response?.data?.error || 'Erro ao fazer upload');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSend = async () => {
    if (!activeConversation) return;
    if (!content.trim() && !attachmentPreview) {
      toast.warning('Digite uma mensagem ou anexe um arquivo');
      return;
    }

    try {
      const payload: any = {
        conversation: activeConversation.id,
        content: content.trim(),
      };

      if (attachmentPreview) {
        payload.attachment_urls = [attachmentPreview.url];
      }

      const response = await api.post('/api/chat/messages/', payload);
      
      addMessage(response.data);
      
      // Limpar
      setContent('');
      setAttachmentPreview(null);
      
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }

    } catch (error: any) {
      console.error('Erro ao enviar:', error);
      toast.error(error.response?.data?.error || 'Erro ao enviar mensagem');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    
    // Auto-resize
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  if (!activeConversation) return null;

  return (
    <div className="p-4 bg-[#1f262e] border-t border-gray-800">
      {/* Preview de anexo */}
      {attachmentPreview && (
        <div className="mb-3 p-3 bg-[#2b2f36] rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Paperclip className="w-4 h-4 text-green-500 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{attachmentPreview.filename}</p>
              <p className="text-xs text-gray-400">
                {(attachmentPreview.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <button
            onClick={() => setAttachmentPreview(null)}
            className="p-1 hover:bg-gray-700 rounded transition-colors"
          >
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      )}

      {/* Input */}
      <div className="flex items-end gap-2">
        {/* Botão de anexo */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="p-3 hover:bg-[#2b2f36] rounded-lg transition-colors disabled:opacity-50"
          title="Anexar arquivo"
        >
          {uploading ? (
            <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
          ) : (
            <Paperclip className="w-5 h-5 text-gray-400" />
          )}
        </button>
        
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileSelect}
          className="hidden"
          accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip,.rar"
        />

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleTextareaChange}
          onKeyPress={handleKeyPress}
          placeholder="Digite uma mensagem..."
          rows={1}
          className="flex-1 px-4 py-3 bg-[#2b2f36] border border-gray-700 rounded-lg text-white placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-green-600 max-h-[120px]"
        />

        {/* Botão enviar */}
        <button
          onClick={handleSend}
          disabled={!content.trim() && !attachmentPreview}
          className="p-3 bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Enviar (Enter)"
        >
          <Send className="w-5 h-5 text-white" />
        </button>
      </div>

      <p className="mt-2 text-xs text-gray-500">
        Enter para enviar • Shift+Enter para quebra de linha
      </p>
    </div>
  );
}

