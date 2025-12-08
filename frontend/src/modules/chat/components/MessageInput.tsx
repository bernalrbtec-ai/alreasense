/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, PenTool, Reply, X } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import { VoiceRecorder } from './VoiceRecorder';
import { EmojiPicker } from './EmojiPicker';
import { FileUploader } from './FileUploader';
import { AttachmentThumbnail } from './AttachmentThumbnail';
import { MentionInput } from './MentionInput';
import { api } from '@/lib/api';

interface MessageInputProps {
  sendMessage: (content: string, includeSignature?: boolean, isInternal?: boolean, replyToMessageId?: string, mentions?: string[], mentionEveryone?: boolean) => boolean;
  sendTyping: (isTyping: boolean) => void;
  isConnected: boolean;
  conversationId?: string;
  conversationType?: 'individual' | 'group' | 'broadcast';
}

export function MessageInput({ sendMessage, sendTyping, isConnected, conversationId: propConversationId, conversationType: propConversationType }: MessageInputProps) {
  const { activeConversation, replyToMessage, clearReply } = useChatStore();
  // ✅ CORREÇÃO CRÍTICA: Usar props se disponíveis, senão usar do store com validação
  const conversationId = propConversationId || activeConversation?.id;
  const conversationType = propConversationType || activeConversation?.conversation_type || 'individual';
  const [message, setMessage] = useState('');
  const [mentions, setMentions] = useState<string[]>([]); // ✅ NOVO: Lista de números mencionados
  const [sending, setSending] = useState(false);
  const [includeSignature, setIncludeSignature] = useState(true); // ✅ Assinatura habilitada por padrão
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement>(null);
  
  // ✅ NOVO: Armazenar texto por conversa (persistir entre mudanças de chat)
  const messageByConversationRef = useRef<Map<string, { text: string; mentions: string[] }>>(new Map());
  const previousConversationIdRef = useRef<string | undefined>(conversationId);
  
  // ✅ NOVO: Refs para acessar valores atuais sem causar re-renders
  const messageRef = useRef(message);
  const mentionsRef = useRef(mentions);
  
  // Atualizar refs quando valores mudam
  useEffect(() => {
    messageRef.current = message;
    mentionsRef.current = mentions;
  }, [message, mentions]);

  // ✅ NOVO: Salvar e restaurar texto quando conversa muda
  useEffect(() => {
    const currentConvId = conversationId;
    const previousConvId = previousConversationIdRef.current;
    
    // Se a conversa mudou
    if (currentConvId !== previousConvId) {
      // Salvar texto da conversa anterior usando refs (valores atuais)
      if (previousConvId) {
        const currentText = messageRef.current;
        const currentMentions = mentionsRef.current;
        
        // Só salvar se houver conteúdo
        if (currentText.trim() || currentMentions.length > 0) {
          messageByConversationRef.current.set(previousConvId, {
            text: currentText,
            mentions: [...currentMentions]
          });
          console.log('💾 [MessageInput] Texto salvo para conversa:', previousConvId, {
            textLength: currentText.length,
            mentionsCount: currentMentions.length
          });
        }
      }
      
      // Restaurar texto da nova conversa (ou vazio se não houver)
      if (currentConvId) {
        const savedData = messageByConversationRef.current.get(currentConvId);
        if (savedData) {
          setMessage(savedData.text);
          setMentions(savedData.mentions);
          console.log('📖 [MessageInput] Texto restaurado para conversa:', currentConvId, {
            textLength: savedData.text.length,
            mentionsCount: savedData.mentions.length
          });
        } else {
          // Nova conversa ou sem texto salvo - limpar
          setMessage('');
          setMentions([]);
          console.log('🆕 [MessageInput] Nova conversa ou sem texto salvo, limpando input');
        }
      } else {
        // Sem conversa ativa - limpar
        setMessage('');
        setMentions([]);
      }
      
      // Atualizar referência
      previousConversationIdRef.current = currentConvId;
    }
  }, [conversationId]); // ✅ CRÍTICO: Só executar quando conversationId mudar
  
  // ✅ NOVO: Salvar texto atual periodicamente (para não perder ao mudar conversa rapidamente)
  useEffect(() => {
    if (conversationId && (message.trim() || mentions.length > 0)) {
      messageByConversationRef.current.set(conversationId, {
        text: message,
        mentions: [...mentions]
      });
    }
  }, [message, mentions, conversationId]);

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

  // ✅ NOVO: Handler para colar imagens do clipboard (Ctrl+V / Cmd+V)
  const handlePaste = useCallback(async (e: React.ClipboardEvent) => {
    // Verificar se há arquivos/imagens no clipboard
    const items = e.clipboardData.items;
    
    if (!items || items.length === 0) {
      return; // Não há nada no clipboard ou é texto puro
    }

    // Procurar por imagens no clipboard
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      
      // Verificar se é uma imagem
      if (item.type.indexOf('image') !== -1) {
        e.preventDefault(); // Prevenir colar texto se houver imagem
        
        const file = item.getAsFile();
        if (!file) {
          console.warn('⚠️ [PASTE] Arquivo de imagem não pôde ser obtido do clipboard');
          return;
        }

        // Validar tamanho e tipo
        try {
          const { validateFileSize, validateFileType } = await import('../utils/messageUtils');
          const allowedTypes = ['image/*'];
          
          const sizeValidation = validateFileSize(file, 50);
          if (!sizeValidation.valid) {
            toast.error(sizeValidation.error || 'Imagem muito grande. Máximo: 50MB');
            return;
          }

          const typeValidation = validateFileType(file, allowedTypes);
          if (!typeValidation.valid) {
            toast.error(typeValidation.error || 'Tipo de imagem não permitido');
            return;
          }

          // Se já houver um arquivo selecionado, substituir
          if (selectedFile) {
            toast.info('Imagem anterior substituída', { duration: 2000 });
          }

          // Adicionar imagem como arquivo selecionado
          setSelectedFile(file);
          
          toast.success('Imagem colada! Clique em enviar para anexar.', {
            duration: 3000,
            position: 'bottom-right'
          });
        } catch (error) {
          console.error('❌ [PASTE] Erro ao processar imagem do clipboard:', error);
          toast.error('Erro ao processar imagem colada');
        }
        
        return; // Processar apenas a primeira imagem encontrada
      }
    }
  }, [selectedFile]);

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
        // ✅ Arquivo será limpo automaticamente no handleFileUpload após sucesso
      }

      // 2️⃣ Se houver texto, enviar mensagem
      if (hasText) {
        const replyToId = replyToMessage?.id;
        // ✅ LOG CRÍTICO: Verificar se reply_to está sendo passado
        console.log('📤 [MESSAGE INPUT] Preparando envio de mensagem:');
        console.log('   Content:', message.trim().substring(0, 50));
        console.log('   replyToMessage:', replyToMessage);
        console.log('   replyToId:', replyToId);
        console.log('   includeSignature:', includeSignature);
        
        // ✅ NOVO: Detectar @everyone no texto (case-insensitive)
        const messageText = message.trim();
        const hasEveryone = /@everyone\b/i.test(messageText);
        
        // ✅ NOVO: Enviar mentions apenas se for grupo e tiver menções OU @everyone
        const mentionsToSend = activeConversation?.conversation_type === 'group' && (mentions.length > 0 || hasEveryone) ? mentions : undefined;
        const mentionEveryone = activeConversation?.conversation_type === 'group' && hasEveryone;
        
        console.log('   mentionsToSend:', mentionsToSend);
        console.log('   mentionEveryone:', mentionEveryone);
        const success = sendMessage(message.trim(), includeSignature, false, replyToId, mentionsToSend, mentionEveryone);
        console.log('📤 [MESSAGE INPUT] Resultado do sendMessage:', success);
        
        if (success) {
          setMessage('');
          setMentions([]); // ✅ Limpar mentions após enviar
          // ✅ NOVO: Limpar texto salvo para esta conversa (já foi enviado)
          if (conversationId) {
            messageByConversationRef.current.delete(conversationId);
            console.log('🗑️ [MessageInput] Texto salvo removido após envio para conversa:', conversationId);
          }
          // ✅ Limpar reply após enviar mensagem
          if (replyToMessage) {
            clearReply();
          }
          // ✅ Removido toast "Mensagem enviada" - desnecessário e polui a interface
        } else {
          toast.error('Erro ao enviar mensagem. WebSocket desconectado.', {
            duration: 4000,
            position: 'bottom-right'
          });
        }
      } else if (selectedFile) {
        // Se só tinha arquivo (sem texto), toast já foi mostrado no handleFileUpload
        console.log('✅ [SEND] Apenas arquivo enviado');
        // ✅ Limpar reply após enviar arquivo também
        if (replyToMessage) {
          clearReply();
        }
      }
    } catch (error: any) {
      console.error('Erro ao enviar mensagem/arquivo:', error);
      toast.error('Erro ao enviar');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // ✅ Enter = enviar mensagem
    // ✅ Shift+Enter = nova linha
    const hasText = message.trim().length > 0;
    const hasFile = selectedFile !== null;
    
    if (e.key === 'Enter' && !e.shiftKey && (hasText || hasFile)) {
      // Verificar se não está dentro de um MentionInput com sugestões abertas
      const target = e.target as HTMLElement;
      const isMentionInput = target.closest('[data-mention-input]');
      const hasSuggestions = target.closest('[data-mention-suggestions]');
      
      // Se não está em MentionInput ou não tem sugestões, enviar mensagem
      if (!isMentionInput || !hasSuggestions) {
        e.preventDefault();
        handleSend();
      }
      // Se está em MentionInput com sugestões, deixar o MentionInput processar
    }
    // Shift+Enter não precisa de tratamento - comportamento padrão do textarea já faz nova linha
  };

  const handleEmojiSelect = (emoji: string) => {
    setMessage(prev => prev + emoji);
    setShowEmojiPicker(false);
  };

  const handleFileUpload = async (file: File) => {
    if (!file || !activeConversation || uploadingFile) return;

    // ✅ FIX: Validar tamanho de arquivo antes de iniciar upload
    const { validateFileSize } = await import('../utils/messageUtils');
    const sizeValidation = validateFileSize(file, 50);
    if (!sizeValidation.valid) {
      toast.error(sizeValidation.error || 'Arquivo muito grande. Máximo: 50MB');
      return;
    }

    setUploadingFile(true);

    try {
      console.log('📤 [FILE] Iniciando upload...', file.name, file.size, 'bytes');

      // 1️⃣ Obter presigned URL
      const { data: presignedData } = await api.post('/chat/upload-presigned-url/', {
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
      await api.post('/chat/confirm-upload/', {
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

      // ✅ IMPORTANTE: Limpar arquivo após upload bem-sucedido
      // Isso garante que o card desapareça mesmo quando chamado via handleSend
      if (selectedFile === file) {
        setSelectedFile(null);
      }
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
      {/* ✅ NOVO: Preview de mensagem respondida */}
      {replyToMessage && (
        <div className="px-4 pt-2 pb-1 bg-[#f0f2f5] border-t border-gray-300">
          <div className="bg-white rounded-lg border-l-4 border-l-blue-500 shadow-sm p-2.5 flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1">
                <Reply className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                <span className="text-xs font-semibold text-blue-600">
                  {replyToMessage.direction === 'incoming' 
                    ? (replyToMessage.sender_name || replyToMessage.sender_phone || 'Contato')
                    : 'Você'}
                </span>
              </div>
              <p className="text-xs text-gray-600 line-clamp-2 break-words">
                {replyToMessage.content 
                  ? (replyToMessage.content.length > 100 
                      ? replyToMessage.content.substring(0, 100) + '...' 
                      : replyToMessage.content)
                  : (replyToMessage.attachments && replyToMessage.attachments.length > 0
                      ? `📎 ${replyToMessage.attachments[0].original_filename || 'Anexo'}`
                      : 'Mensagem')}
              </p>
            </div>
            <button
              onClick={clearReply}
              className="p-1 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
              title="Cancelar resposta"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      )}

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
        {conversationType === 'group' ? (
          <MentionInput
            value={message}
            onChange={handleMessageChange}
            onMentionsChange={setMentions}
            conversationId={conversationId}
            conversationType={conversationType as 'individual' | 'group' | 'broadcast'}
            placeholder="Digite uma mensagem (use @ para mencionar)"
            className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 placeholder-gray-500 transition-all duration-200"
            disabled={sending}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
          />
        ) : (
          <textarea
            value={message}
            onChange={(e) => handleMessageChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder="Digite uma mensagem (Enter para enviar, Shift+Enter para nova linha)"
            rows={1}
            className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 placeholder-gray-500 transition-all duration-200"
            style={{
              maxHeight: '120px',
              minHeight: '44px',
              transition: 'height 0.2s ease-out'
            }}
            disabled={sending}
          />
        )}
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
