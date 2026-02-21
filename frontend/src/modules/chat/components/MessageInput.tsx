/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, PenTool, Reply, X, FileText } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { toast } from 'sonner';
import { VoiceRecorder } from './VoiceRecorder';
import { EmojiPicker } from './EmojiPicker';
import { FileUploader } from './FileUploader';
import { AttachmentThumbnail } from './AttachmentThumbnail';
import { MentionInput } from './MentionInput';
import { QuickRepliesButton } from './QuickRepliesButton';
import { TemplatePickerModal } from './TemplatePickerModal';
import { api } from '@/lib/api';

interface MessageInputProps {
  sendMessage: (content: string, includeSignature?: boolean, isInternal?: boolean, replyToMessageId?: string, mentions?: string[], mentionEveryone?: boolean) => boolean;
  sendMessageAsTemplate?: (conversationId: string, waTemplateId: string, bodyParameters: string[]) => boolean;
  sendTyping: (isTyping: boolean) => void;
  isConnected: boolean;
  conversationId?: string;
  conversationType?: 'individual' | 'group' | 'broadcast';
}

export function MessageInput({ sendMessage, sendMessageAsTemplate, sendTyping, isConnected, conversationId: propConversationId, conversationType: propConversationType }: MessageInputProps) {
  const { activeConversation, replyToMessage, clearReply, addMessage } = useChatStore();
  // ✅ CORREÇÃO CRÍTICA: Usar props se disponíveis, senão usar do store com validação
  const conversationId = propConversationId || activeConversation?.id;
  const conversationType = propConversationType || activeConversation?.conversation_type || 'individual';
  const isGroupInputBlocked = conversationType === 'group' && !!activeConversation?.group_metadata?.instance_removed;
  const [message, setMessage] = useState('');
  const [mentions, setMentions] = useState<string[]>([]); // ✅ NOVO: Lista de números mencionados
  const [sending, setSending] = useState(false);
  const [includeSignature, setIncludeSignature] = useState(true); // ✅ Assinatura habilitada por padrão
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadingFile, setUploadingFile] = useState(false);
  const MAX_FILES = 10;
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

          // Adicionar à lista (respeitando limite)
          setSelectedFiles(prev => {
            const next = [...prev, file];
            if (next.length > MAX_FILES) {
              toast.info(`Máximo ${MAX_FILES} arquivos. A imagem foi adicionada.`, { duration: 2000 });
              return next.slice(0, MAX_FILES);
            }
            return next;
          });

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
  }, [MAX_FILES]);

  const handleMessageChange = useCallback((value: string) => {
    if (isGroupInputBlocked) {
      return;
    }
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
  }, [isConnected, sendTyping, isGroupInputBlocked]);

  const handleSend = async () => {
    const hasText = message.trim().length > 0;
    const hasFiles = selectedFiles.length > 0;

    if (isGroupInputBlocked || (!hasText && !hasFiles) || !activeConversation || sending || !isConnected || uploadingFile) {
      return;
    }

    // Meta fora da janela 24h: orientar a usar o botão Template (não abrir modal ao enviar)
    if (activeConversation?.requires_template_to_message && (hasText || hasFiles)) {
      toast.info('Fora da janela 24h. Use o botão "Template" ao lado para enviar uma mensagem.', {
        duration: 5000,
        position: 'bottom-right',
      });
      return;
    }

    if (replyToMessage?.is_deleted) {
      toast.error('Não é possível responder a uma mensagem que foi apagada');
      clearReply();
      return;
    }

    try {
      setSending(true);
      sendTyping(false);
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);

      if (hasFiles) {
        if (selectedFiles.length === 1) {
          await handleFileUpload(selectedFiles[0]);
        } else {
          await handleBatchUpload(selectedFiles, hasText ? message.trim() : '');
        }
        setSelectedFiles([]);
        if (replyToMessage) clearReply();
        if (hasText) {
          setMessage('');
          setMentions([]);
          if (conversationId) messageByConversationRef.current.delete(conversationId);
        }
        if (!hasText) {
          console.log('✅ [SEND] Apenas arquivo(s) enviado(s)');
        }
        return;
      }

      if (hasText) {
        const replyToId = replyToMessage?.id;
        const messageText = message.trim();
        const hasEveryone = /@everyone\b/i.test(messageText);
        const mentionsToSend = activeConversation?.conversation_type === 'group' && (mentions.length > 0 || hasEveryone) ? mentions : undefined;
        const mentionEveryone = activeConversation?.conversation_type === 'group' && hasEveryone;
        const success = sendMessage(messageText, includeSignature, false, replyToId, mentionsToSend, mentionEveryone);
        if (success) {
          setMessage('');
          setMentions([]);
          if (conversationId) messageByConversationRef.current.delete(conversationId);
          if (replyToMessage) clearReply();
        } else {
          toast.error('Erro ao enviar mensagem. WebSocket desconectado.', { duration: 4000, position: 'bottom-right' });
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
    const hasText = message.trim().length > 0;
    const hasFiles = selectedFiles.length > 0;
    if (e.key === 'Enter' && !e.shiftKey && (hasText || hasFiles)) {
      // Verificar se não está dentro de um MentionInput com sugestões abertas
      const target = e.target as HTMLElement;
      const isMentionInput = target.closest('[data-mention-input]');
      const hasSuggestions = target.closest('[data-mention-suggestions]');
      
      // Se não está em MentionInput ou não tem sugestões, enviar mensagem
      if (!isMentionInput || !hasSuggestions) {
        e.preventDefault();
        if (!isGroupInputBlocked) {
          handleSend();
        }
      }
      // Se está em MentionInput com sugestões, deixar o MentionInput processar
    }
    // Shift+Enter não precisa de tratamento - comportamento padrão do textarea já faz nova linha
  };

  const handleEmojiSelect = (emoji: string) => {
    setMessage(prev => prev + emoji);
    setShowEmojiPicker(false);
  };

  // ✅ Handler para respostas rápidas
  const handleQuickReplySelect = useCallback((content: string) => {
    setMessage(prev => prev + (prev ? ' ' : '') + content);
    // Focar no input após inserir
    setTimeout(() => {
      const textarea = document.querySelector('textarea');
      textarea?.focus();
    }, 0);
  }, []);

  // ✅ Atalho de teclado "/" para abrir respostas rápidas
  useEffect(() => {
    const handleSlashKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInInput = target.tagName === 'TEXTAREA' || target.closest('[data-mention-input]');
      // Só funciona se estiver no input, não tiver texto e não estiver desabilitado
      if (e.key === '/' && isInInput && !message.trim() && !sending && isConnected) {
        e.preventDefault();
        // Abrir dropdown de respostas rápidas (via evento customizado)
        const event = new CustomEvent('openQuickReplies');
        document.dispatchEvent(event);
      }
    };
    
    document.addEventListener('keydown', handleSlashKey);
    return () => document.removeEventListener('keydown', handleSlashKey);
  }, [message, sending, isConnected]);

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
      const { data: confirmData } = await api.post('/chat/confirm-upload/', {
        conversation_id: activeConversation.id,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      });

      if (confirmData?.message) {
        const msg = { ...confirmData.message };
        if (!msg.conversation_id && activeConversation?.id) msg.conversation_id = activeConversation.id;
        addMessage(msg);
      }

      toast.success('Arquivo enviado!', { duration: 2000, position: 'bottom-right' });
      setSelectedFiles(prev => prev.filter(f => f !== file));
    } catch (error: any) {
      console.error('❌ [FILE] Erro ao enviar arquivo:', error);
      const errorMsg = error.response?.data?.error || error.message || 'Erro ao enviar arquivo';
      toast.error(errorMsg);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleBatchUpload = async (files: File[], contentText: string) => {
    if (!files.length || !activeConversation || uploadingFile) return;

    setUploadingFile(true);
    try {
      const presignedResponses = await Promise.all(
        files.map(f =>
          api.post('/chat/upload-presigned-url/', {
            conversation_id: activeConversation.id,
            filename: f.name,
            content_type: f.type,
            file_size: f.size,
          }).then(r => ({ file: f, data: r.data }))
        )
      );

      await Promise.all(
        presignedResponses.map(({ file, data }) =>
          new Promise<void>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.addEventListener('load', () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload ${xhr.status}`))));
            xhr.addEventListener('error', () => reject(new Error('Erro de rede')));
            xhr.open('PUT', data.upload_url);
            xhr.setRequestHeader('Content-Type', file.type);
            xhr.send(file);
          })
        )
      );

      const items = presignedResponses.map(({ file, data }) => ({
        attachment_id: data.attachment_id,
        s3_key: data.s3_key,
        filename: file.name,
        content_type: file.type,
        file_size: file.size,
      }));

      const { data: confirmData } = await api.post('/chat/confirm-upload-batch/', {
        conversation_id: activeConversation.id,
        items,
        content: contentText,
      });

      if (confirmData?.message) {
        const msg = { ...confirmData.message };
        if (!msg.conversation_id && activeConversation?.id) msg.conversation_id = activeConversation.id;
        addMessage(msg);
      }

      toast.success('Arquivos enviados!', { duration: 2000, position: 'bottom-right' });
    } catch (error: any) {
      console.error('❌ [BATCH] Erro:', error);
      const errMsg = error.response?.data?.error || error.message || 'Erro ao enviar arquivos';
      toast.error(errMsg);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  if (!activeConversation) {
    return null;
  }

  return (
    <>
    <div className="relative">
      {/* ✅ NOVO: Preview de mensagem respondida */}
      {replyToMessage && (
        <div className="px-4 pt-2 pb-1 bg-[#f0f2f5] dark:bg-gray-800 border-t border-gray-300 dark:border-gray-700">
          <div className="bg-white dark:bg-gray-700 rounded-lg border-l-4 border-l-blue-500 shadow-sm p-2.5 flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 mb-1">
                <Reply className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                <span className="text-xs font-semibold text-blue-600">
                  {replyToMessage.direction === 'incoming' 
                    ? (replyToMessage.sender_name || replyToMessage.sender_phone || 'Contato')
                    : 'Você'}
                </span>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-300 line-clamp-2 break-words">
                {replyToMessage.is_deleted
                  ? 'Mensagem apagada'
                  : (replyToMessage.content
                      ? (replyToMessage.content.length > 100
                          ? replyToMessage.content.substring(0, 100) + '...'
                          : replyToMessage.content)
                      : (replyToMessage.attachments && replyToMessage.attachments.length > 0
                          ? `📎 ${replyToMessage.attachments[0].original_filename || 'Anexo'}`
                          : 'Mensagem'))}
              </p>
            </div>
            <button
              onClick={clearReply}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-full transition-colors flex-shrink-0"
              title="Cancelar resposta"
            >
              <X className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>
      )}

      {/* Thumbnail preview acima do input */}
      {selectedFiles.length > 0 && (
        <div className="px-4 pt-2 pb-1 bg-[#f0f2f5] dark:bg-gray-800 border-t border-gray-300 dark:border-gray-700 flex flex-wrap gap-2">
          {selectedFiles.map((file, i) => (
            <AttachmentThumbnail
              key={`${file.name}-${file.size}-${i}`}
              file={file}
              onRemove={() => handleRemoveFile(i)}
              onUpload={handleFileUpload}
              isUploading={uploadingFile}
            />
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex items-end gap-2 px-4 py-3 bg-[#f0f2f5] dark:bg-gray-800 border-t border-gray-300 dark:border-gray-700 relative shadow-sm">
      {/* Toggle de Assinatura - ao lado esquerdo */}
      <button
        onClick={() => {
          if (!isGroupInputBlocked) {
            setIncludeSignature(!includeSignature);
          }
        }}
        className={`
          p-2 rounded-full transition-all duration-150 flex-shrink-0
          shadow-sm hover:shadow-md active:scale-95
          ${includeSignature 
            ? 'text-green-600 hover:bg-green-100 bg-green-50' 
            : 'text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
          }
        `}
        title={includeSignature ? 'Assinatura ativada - clique para desativar' : 'Assinatura desativada - clique para ativar'}
        disabled={isGroupInputBlocked}
      >
        <PenTool className="w-5 h-5" />
      </button>

      {/* Quick Replies button - ao lado da assinatura */}
      <QuickRepliesButton 
        onSelect={handleQuickReplySelect}
        disabled={sending || !isConnected || isGroupInputBlocked}
      />

      {/* Botão Template (Meta: fora da janela 24h) */}
      {activeConversation?.requires_template_to_message && sendMessageAsTemplate && (
        <button
          type="button"
          onClick={() => setShowTemplateModal(true)}
          className="p-2 rounded-full flex-shrink-0 text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 dark:text-indigo-400"
          title="Enviar por template (fora da janela 24h)"
        >
          <FileText className="w-5 h-5" />
        </button>
      )}

      {/* File Uploader */}
      <div className="relative">
        <FileUploader
          conversationId={activeConversation.id}
          selectedFiles={selectedFiles}
          onFileSelect={(files) => setSelectedFiles(prev => [...prev, ...files].slice(0, MAX_FILES))}
          onUpload={handleFileUpload}
          onUploadComplete={() => setSelectedFiles([])}
          disabled={sending || !isConnected || isGroupInputBlocked}
          isUploading={uploadingFile}
        />
      </div>

      {/* Emoji button */}
      <div className="relative" ref={emojiPickerRef}>
        <button
          onClick={() => {
            if (!isGroupInputBlocked) {
              setShowEmojiPicker(!showEmojiPicker);
            }
          }}
          className={`
            p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md
            ${showEmojiPicker ? 'bg-gray-200 shadow-md' : ''}
          `}
          title="Emoji"
          disabled={isGroupInputBlocked}
        >
          <Smile className="w-6 h-6 text-gray-600 dark:text-gray-400" />
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
      <div className="flex-1 bg-white dark:bg-gray-700 rounded-2xl shadow-md transition-all duration-200 hover:shadow-lg focus-within:shadow-lg focus-within:ring-2 focus-within:ring-[#00a884]/20">
        {conversationType === 'group' ? (
          <MentionInput
            value={message}
            onChange={handleMessageChange}
            onMentionsChange={setMentions}
            conversationId={conversationId}
            conversationType={conversationType as 'individual' | 'group' | 'broadcast'}
            placeholder={isGroupInputBlocked ? 'Instância removida do grupo' : 'Digite uma mensagem (use @ para mencionar)'}
            className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 placeholder-gray-500 transition-all duration-200"
            disabled={sending || isGroupInputBlocked}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
          />
        ) : (
          <textarea
            value={message}
            onChange={(e) => handleMessageChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={isGroupInputBlocked ? 'Instância removida do grupo' : 'Digite uma mensagem (Enter para enviar, Shift+Enter para nova linha)'}
            rows={1}
            className="w-full px-4 py-3 bg-transparent resize-none focus:outline-none text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 transition-all duration-200"
            style={{
              maxHeight: '120px',
              minHeight: '44px',
              transition: 'height 0.2s ease-out'
            }}
            disabled={sending || isGroupInputBlocked}
          />
        )}
      </div>

      {/* Voice Recorder button - ao lado do Send */}
      {!isGroupInputBlocked && (
        <VoiceRecorder
          conversationId={activeConversation.id}
          onRecordingComplete={() => {
            console.log('✅ Áudio enviado! WebSocket vai atualizar UI');
          }}
        />
      )}

      {/* Send button */}
      <button
        onClick={handleSend}
        disabled={isGroupInputBlocked || (!message.trim() && selectedFiles.length === 0) || sending || !isConnected || uploadingFile}
        className={`
          p-2 rounded-full transition-all duration-150 flex-shrink-0
          shadow-md hover:shadow-lg active:scale-95
          ${(message.trim() || selectedFiles.length > 0) && !sending && !uploadingFile && isConnected && !isGroupInputBlocked
            ? 'bg-[#00a884] hover:bg-[#008f6f]'
            : 'bg-gray-300 cursor-not-allowed opacity-50'
          }
        `}
        title={
          isGroupInputBlocked
            ? "Instância removida do grupo"
            : !isConnected
            ? "Conectando..."
            : uploadingFile
            ? "Enviando arquivo..."
            : (message.trim() || selectedFiles.length > 0)
            ? "Enviar"
            : "Digite uma mensagem ou selecione um arquivo"
        }
      >
        <Send className={`w-6 h-6 ${(message.trim() || selectedFiles.length > 0) && !sending && !uploadingFile && isConnected && !isGroupInputBlocked ? 'text-white' : 'text-gray-500 dark:text-gray-400'}`} />
      </button>
      </div>
    </div>

    {conversationId && (
      <TemplatePickerModal
        isOpen={showTemplateModal}
        onClose={() => setShowTemplateModal(false)}
        conversationId={conversationId}
        onSelectTemplate={(templateId, bodyParams) => {
          if (sendMessageAsTemplate) {
            sendMessageAsTemplate(conversationId, templateId, bodyParams);
            setShowTemplateModal(false);
          }
        }}
      />
    )}
    </>
  );
}
