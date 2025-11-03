/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, Paperclip, PenTool } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import { VoiceRecorder } from './VoiceRecorder';
import { EmojiPicker } from './EmojiPicker';
import { FileUploader } from './FileUploader';
import { AttachmentThumbnail } from './AttachmentThumbnail';
import { api } from '@/lib/api';

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
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement>(null);

  // Limpar timeout de digitando ao desmontar
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
        sendTyping(false);
      }
    };
  }, [sendTyping]);

  // Fechar emoji picker ao clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (emojiPickerRef.current && !emojiPickerRef.current.contains(event.target as Node)) {
        setShowEmojiPicker(false);
      }
    }
    
    if (showEmojiPicker) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showEmojiPicker]);

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

  const handleSend = async () => {
    // Validar condições: precisa ter texto OU arquivo selecionado
    const hasText = message.trim().length > 0;
    const hasFile = selectedFile !== null;
    
    if ((!hasText && !hasFile) || !activeConversation || sending || !isConnected || uploadingFile) {
      return;
    }

    try {
      setSending(true);
      
      // Parar "digitando" antes de enviar
      sendTyping(false);
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }

      // 1️⃣ Se houver arquivo selecionado, enviar primeiro
      if (selectedFile) {
        console.log('📤 [SEND] Enviando arquivo primeiro:', selectedFile.name);
        await handleFileUpload(selectedFile);
        // Arquivo será limpo no onUploadComplete
      }

      // 2️⃣ Se houver texto, enviar mensagem
      if (hasText) {
        const success = sendMessage(message.trim(), includeSignature);
        
        if (success) {
          setMessage('');
          if (!selectedFile) {
            // Só mostrar toast se não teve arquivo (arquivo já mostra seu próprio toast)
            toast.success('Mensagem enviada!', {
              duration: 2000,
              position: 'bottom-right'
            });
          }
        } else {
          toast.error('Erro ao enviar mensagem. WebSocket desconectado.', {
            duration: 4000,
            position: 'bottom-right'
          });
        }
      } else if (selectedFile) {
        // Se só tinha arquivo (sem texto), toast já foi mostrado no handleFileUpload
        console.log('✅ [SEND] Apenas arquivo enviado');
      }
    } catch (error: any) {
      console.error('Erro ao enviar mensagem/arquivo:', error);
      toast.error('Erro ao enviar');
    } finally {
      setSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    // ✅ Permitir Enter para enviar se houver texto OU arquivo
    const hasText = message.trim().length > 0;
    const hasFile = selectedFile !== null;
    
    if (e.key === 'Enter' && !e.shiftKey && (hasText || hasFile)) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleEmojiSelect = (emoji: string) => {
    setMessage(prev => prev + emoji);
    setShowEmojiPicker(false);
  };

  const handleFileUpload = async (file: File) => {
    if (!file || !activeConversation || uploadingFile) return;

    setUploadingFile(true);

    try {
      console.log('📤 [FILE] Iniciando upload...', file.name, file.size, 'bytes');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/messages/upload-presigned-url/', {
        conversation_id: activeConversation.id,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [FILE] Presigned URL obtida');

      // 2️⃣ Upload S3
      const xhr = new XMLHttpRequest();
      
      await new Promise<void>((resolve, reject) => {
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload falhou: ${xhr.status}`));
          }
        });

        xhr.addEventListener('error', () => {
          reject(new Error('Erro de rede'));
        });

        xhr.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            console.log(`📤 [FILE] Upload progress: ${percent.toFixed(1)}%`);
          }
        });

        xhr.open('PUT', presignedData.upload_url);
        xhr.setRequestHeader('Content-Type', file.type);
        xhr.send(file);
      });

      console.log('✅ [FILE] Upload S3 completo');

      // 3️⃣ Confirmar backend
      const { data: confirmData } = await api.post('/chat/messages/confirm-upload/', {
        conversation_id: activeConversation.id,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      console.log('✅ [FILE] Arquivo enviado com sucesso!');

      toast.success('Arquivo enviado!', {
        duration: 2000,
        position: 'bottom-right'
      });
    } catch (error: any) {
      console.error('❌ [FILE] Erro ao enviar arquivo:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar arquivo';
      toast.error(errorMsg);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
  };

  if (!activeConversation) {
    return null;
  }

  return (
    <div className="relative">
      {/* Thumbnail preview acima do input */}
      {selectedFile && (
        <div className="px-4 pt-2 pb-1 bg-[#f0f2f5] border-t border-gray-300">
          <AttachmentThumbnail
            file={selectedFile}
            onRemove={handleRemoveFile}
            onUpload={handleFileUpload}
            isUploading={uploadingFile}
          />
        </div>
      )}

      {/* Input area */}
      <div className="flex items-end gap-2 px-4 py-3 bg-[#f0f2f5] border-t border-gray-300 relative shadow-sm">
      {/* Toggle de Assinatura - ao lado esquerdo */}
      <button
        onClick={() => setIncludeSignature(!includeSignature)}
        className={`
          p-2 rounded-full transition-all duration-150 flex-shrink-0
          shadow-sm hover:shadow-md active:scale-95
          ${includeSignature 
            ? 'text-green-600 hover:bg-green-100 bg-green-50' 
            : 'text-gray-500 hover:bg-gray-200'
          }
        `}
        title={includeSignature ? 'Assinatura ativada - clique para desativar' : 'Assinatura desativada - clique para ativar'}
      >
        <PenTool className="w-5 h-5" />
      </button>

      {/* File Uploader */}
      <div className="relative">
        <FileUploader
          conversationId={activeConversation.id}
          selectedFile={selectedFile}
          onFileSelect={setSelectedFile}
          onUpload={handleFileUpload}
          onUploadComplete={() => {
            console.log('✅ Arquivo enviado! WebSocket vai atualizar UI');
            setSelectedFile(null);
          }}
          disabled={sending || !isConnected}
          isUploading={uploadingFile}
        />
      </div>

      {/* Emoji button */}
      <div className="relative" ref={emojiPickerRef}>
        <button
          onClick={() => setShowEmojiPicker(!showEmojiPicker)}
          className={`
            p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md
            ${showEmojiPicker ? 'bg-gray-200 shadow-md' : ''}
          `}
          title="Emoji"
        >
          <Smile className="w-6 h-6 text-gray-600" />
        </button>
        
        {/* Emoji Picker */}
        {showEmojiPicker && (
          <div className="animate-scale-in">
            <EmojiPicker
              onSelect={handleEmojiSelect}
              onClose={() => setShowEmojiPicker(false)}
            />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex-1 bg-white rounded-2xl shadow-md transition-all duration-200 hover:shadow-lg focus-within:shadow-lg focus-within:ring-2 focus-within:ring-[#00a884]/20">
        <textarea
          value={message}
          onChange={(e) => handleMessageChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Digite uma mensagem"
          rows={1}
          className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 placeholder-gray-500 transition-all duration-200"
          style={{
            maxHeight: '120px',
            minHeight: '44px',
            transition: 'height 0.2s ease-out'
          }}
          disabled={sending}
        />
      </div>

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
        disabled={(!message.trim() && !selectedFile) || sending || !isConnected || uploadingFile}
        className={`
          p-2 rounded-full transition-all duration-150 flex-shrink-0
          shadow-md hover:shadow-lg active:scale-95
          ${(message.trim() || selectedFile) && !sending && !uploadingFile && isConnected
            ? 'bg-[#00a884] hover:bg-[#008f6f]'
            : 'bg-gray-300 cursor-not-allowed opacity-50'
          }
        `}
        title={
          !isConnected 
            ? "Conectando..." 
            : uploadingFile 
            ? "Enviando arquivo..." 
            : (message.trim() || selectedFile) 
            ? "Enviar" 
            : "Digite uma mensagem ou selecione um arquivo"
        }
      >
        <Send className={`w-6 h-6 ${(message.trim() || selectedFile) && !sending && !uploadingFile && isConnected ? 'text-white' : 'text-gray-500'}`} />
      </button>
      </div>
    </div>
  );
}
