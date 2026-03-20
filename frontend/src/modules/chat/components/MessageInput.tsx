/**
 * Campo de input de mensagens - Estilo WhatsApp Web
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Send, Smile, PenTool, Reply, X, FileText, LayoutList, ListOrdered, UserPlus } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useAuthStore } from '@/stores/authStore';
import { toast } from 'sonner';
import { VoiceRecorder } from './VoiceRecorder';
import { EmojiPicker } from './EmojiPicker';
import { FileUploader } from './FileUploader';
import { AttachmentThumbnail } from './AttachmentThumbnail';
import { MentionInput } from './MentionInput';
import { QuickRepliesButton } from './QuickRepliesButton';
import { TemplatePickerModal } from './TemplatePickerModal';
import { api } from '@/lib/api';
import { getMessagePreviewText, resolveFileMimeType } from '../utils/messageUtils';

export interface InteractiveButton {
  id: string;
  title: string;
}

interface MessageInputProps {
  sendMessage: (content: string, includeSignature?: boolean, isInternal?: boolean, replyToMessageId?: string, mentions?: string[], mentionEveryone?: boolean) => boolean;
  sendMessageAsTemplate?: (conversationId: string, waTemplateId: string, bodyParameters: string[]) => boolean;
  sendMessageWithButtons?: (conversationId: string, bodyText: string, buttons: InteractiveButton[]) => boolean;
  sendMessageWithList?: (
    conversationId: string,
    bodyText: string,
    buttonText: string,
    sections: Array<{ title?: string; rows: Array<{ id: string; title: string; description?: string }> }>,
    headerText?: string,
    footerText?: string,
    replyTo?: string,
  ) => boolean;
  sendMessageWithContacts?: (conversationId: string, contacts: Array<{ display_name: string; phone: string }>, replyTo?: string) => boolean;
  sendTyping: (isTyping: boolean) => void;
  isConnected: boolean;
  conversationId?: string;
  conversationType?: 'individual' | 'group' | 'broadcast';
}

export function MessageInput({ sendMessage, sendMessageAsTemplate, sendMessageWithButtons, sendMessageWithList, sendMessageWithContacts, sendTyping, isConnected, conversationId: propConversationId, conversationType: propConversationType }: MessageInputProps) {
  const { activeConversation, replyToMessage, clearReply, addMessage, difyActiveConversations } = useChatStore();
  const { user } = useAuthStore();
  const allowMetaInteractiveButtons = user?.allow_meta_interactive_buttons !== false;
  // ✅ CORREÇÃO CRÍTICA: Usar props se disponíveis, senão usar do store com validação
  const conversationId = propConversationId || activeConversation?.id;
  const conversationType = propConversationType || activeConversation?.conversation_type || 'individual';
  const isGroupInputBlocked = conversationType === 'group' && !!activeConversation?.group_metadata?.instance_removed;
  const [message, setMessage] = useState('');
  const [mentions, setMentions] = useState<string[]>([]); // ✅ NOVO: Lista de números mencionados
  const [sending, setSending] = useState(false);
  const [showAutomationStopConfirm, setShowAutomationStopConfirm] = useState(false);
  const [pendingSendPayload, setPendingSendPayload] = useState<{
    content: string;
    includeSignature: boolean;
    isInternal: boolean;
    replyToMessageId?: string;
    mentions?: string[];
    mentionEveryone?: boolean;
  } | null>(null);
  const pendingAutomationActionRef = useRef<null | (() => Promise<void>)>(null);
  const [includeSignature, setIncludeSignature] = useState(true); // ✅ Assinatura habilitada por padrão
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [showButtonsModal, setShowButtonsModal] = useState(false);
  const [buttonsBodyText, setButtonsBodyText] = useState('');
  const [buttonsList, setButtonsList] = useState<InteractiveButton[]>([{ id: 'btn1', title: '' }]);
  const [showListModal, setShowListModal] = useState(false);
  const [listBodyText, setListBodyText] = useState('');
  const [listButtonText, setListButtonText] = useState('');
  const [listHeaderText, setListHeaderText] = useState('');
  const [listFooterText, setListFooterText] = useState('');
  const [showContactModal, setShowContactModal] = useState(false);
  const [contactModalTab, setContactModalTab] = useState<'agenda' | 'manual'>('agenda');
  const [contactAgendaSearch, setContactAgendaSearch] = useState('');
  const [contactAgendaList, setContactAgendaList] = useState<Array<{ id: string; name: string; phone: string }>>([]);
  const [contactAgendaLoading, setContactAgendaLoading] = useState(false);
  const [contactSelected, setContactSelected] = useState<{ display_name: string; phone: string } | null>(null);
  const [contactManualName, setContactManualName] = useState('');
  const [contactManualPhone, setContactManualPhone] = useState('');
  const [contactSending, setContactSending] = useState(false);
  const [listSections, setListSections] = useState<Array<{ title: string; rows: Array<{ id: string; title: string; description: string }> }>>([
    { title: 'Opções', rows: [{ id: 'opt1', title: '', description: '' }] },
  ]);
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

  // Fechar modal de contato ao trocar de conversa
  const prevConversationIdRef = useRef<string | undefined>(conversationId);
  useEffect(() => {
    if (prevConversationIdRef.current !== conversationId) {
      prevConversationIdRef.current = conversationId;
      setShowContactModal(false);
    }
  }, [conversationId]);

  // Buscar contatos da agenda quando modal está aberto na aba agenda
  useEffect(() => {
    if (!showContactModal || contactModalTab !== 'agenda') return;
    setContactAgendaLoading(true);
    const search = contactAgendaSearch.trim();
    const params = search ? { search } : {};
    api.get('/contacts/contacts/', { params })
      .then(res => {
        const results = res.data?.results ?? res.data ?? [];
        setContactAgendaList(
          (Array.isArray(results) ? results : []).map((c: { id: string; name?: string; phone?: string }) => ({
            id: String(c.id),
            name: (c.name || '').trim() || 'Sem nome',
            phone: (c.phone || '').trim(),
          }))
        );
      })
      .catch(() => setContactAgendaList([]))
      .finally(() => setContactAgendaLoading(false));
  }, [showContactModal, contactModalTab, contactAgendaSearch]);

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

      // Limpar modo botões ao trocar de conversa
      setShowButtonsModal(false);
      setButtonsBodyText('');
      setButtonsList([{ id: 'btn1', title: '' }]);
      
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

  const activeDifyName = conversationId ? difyActiveConversations?.[String(conversationId)] : undefined;

  const stopDifyIfActive = useCallback(async () => {
    if (!conversationId) return;
    if (!activeDifyName) return;
    try {
      await api.post(`/chat/conversations/${conversationId}/stop-dify-agent/`);
    } catch {
      // best-effort: backend também para no outgoing, aqui é UX
    }
  }, [conversationId, activeDifyName]);

  const requestActionWithAutomationGuard = useCallback((action: () => Promise<void>) => {
    if (activeDifyName) {
      pendingAutomationActionRef.current = action;
      setPendingSendPayload(null);
      setShowAutomationStopConfirm(true);
      return;
    }
    void action();
  }, [activeDifyName]);

  const requestSendWithAutomationGuard = useCallback((payload: {
    content: string;
    includeSignature: boolean;
    isInternal: boolean;
    replyToMessageId?: string;
    mentions?: string[];
    mentionEveryone?: boolean;
  }) => {
    if (activeDifyName) {
      setPendingSendPayload(payload);
      pendingAutomationActionRef.current = null;
      setShowAutomationStopConfirm(true);
      return false;
    }
    return sendMessage(
      payload.content,
      payload.includeSignature,
      payload.isInternal,
      payload.replyToMessageId,
      payload.mentions,
      payload.mentionEveryone,
    );
  }, [activeDifyName, sendMessage]);

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
        if (activeDifyName) {
          const caption = hasText ? message.trim() : '';
          const files = [...selectedFiles];
          requestActionWithAutomationGuard(async () => {
            await stopDifyIfActive();
            if (files.length === 1) {
              await handleFileUpload(files[0], caption);
            } else {
              await handleBatchUpload(files, caption);
            }
            setSelectedFiles([]);
            if (replyToMessage) clearReply();
            if (caption) {
              setMessage('');
              setMentions([]);
              if (conversationId) messageByConversationRef.current.delete(conversationId);
            }
          });
          return;
        }
        if (selectedFiles.length === 1) {
          await handleFileUpload(selectedFiles[0], hasText ? message.trim() : '');
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
        const success = requestSendWithAutomationGuard({
          content: messageText,
          includeSignature,
          isInternal: false,
          replyToMessageId: replyToId,
          mentions: mentionsToSend,
          mentionEveryone,
        });
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

  const confirmStopAutomationAndSend = async () => {
    const pendingAction = pendingAutomationActionRef.current;
    if (pendingAction) {
      setShowAutomationStopConfirm(false);
      pendingAutomationActionRef.current = null;
      setPendingSendPayload(null);
      try {
        setSending(true);
        await pendingAction();
      } finally {
        setSending(false);
      }
      return;
    }
    const payload = pendingSendPayload;
    setShowAutomationStopConfirm(false);
    setPendingSendPayload(null);
    if (!payload) return;
    try {
      setSending(true);
      await stopDifyIfActive();
      const ok = sendMessage(
        payload.content,
        payload.includeSignature,
        payload.isInternal,
        payload.replyToMessageId,
        payload.mentions,
        payload.mentionEveryone,
      );
      if (ok) {
        setMessage('');
        setMentions([]);
        if (conversationId) messageByConversationRef.current.delete(conversationId);
        if (replyToMessage) clearReply();
      } else {
        toast.error('Erro ao enviar mensagem. WebSocket desconectado.', { duration: 4000, position: 'bottom-right' });
      }
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

  const handleFileUpload = async (file: File, captionText?: string) => {
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
      const contentType = resolveFileMimeType(file);
      const { data: presignedData } = await api.post('/chat/upload-presigned-url/', {
        conversation_id: activeConversation.id,
        filename: file.name,
        content_type: contentType,
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
        xhr.setRequestHeader('Content-Type', contentType);
        xhr.send(file);
      });

      console.log('✅ [FILE] Upload S3 completo');

      // 3️⃣ Confirmar backend
      const { data: confirmData } = await api.post('/chat/confirm-upload/', {
        conversation_id: activeConversation.id,
        attachment_id: presignedData.attachment_id,
        s3_key: presignedData.s3_key,
        filename: file.name,
        content_type: contentType,
        file_size: file.size,
        content: captionText || '',
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
          {
            const contentType = resolveFileMimeType(f);
            return api.post('/chat/upload-presigned-url/', {
              conversation_id: activeConversation.id,
              filename: f.name,
              content_type: contentType,
              file_size: f.size,
            }).then(r => ({ file: f, contentType, data: r.data }));
          }
        )
      );

      await Promise.all(
        presignedResponses.map(({ file, contentType, data }) =>
          new Promise<void>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.addEventListener('load', () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload ${xhr.status}`))));
            xhr.addEventListener('error', () => reject(new Error('Erro de rede')));
            xhr.open('PUT', data.upload_url);
            xhr.setRequestHeader('Content-Type', contentType);
            xhr.send(file);
          })
        )
      );

      const items = presignedResponses.map(({ file, contentType, data }) => ({
        attachment_id: data.attachment_id,
        s3_key: data.s3_key,
        filename: file.name,
        content_type: contentType,
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
    {showAutomationStopConfirm && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        onClick={() => { setShowAutomationStopConfirm(false); setPendingSendPayload(null); }}
      >
        <div
          className="w-full max-w-md rounded-2xl border border-gray-200 dark:border-gray-700 shadow-2xl overflow-hidden bg-white dark:bg-gray-800"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                <PenTool className="w-5 h-5 text-amber-700 dark:text-amber-300" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">Você vai assumir a conversa</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">O assistente será desativado</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => { setShowAutomationStopConfirm(false); setPendingSendPayload(null); }}
              className="p-2 rounded-xl text-gray-500 hover:text-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              aria-label="Fechar"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="px-5 py-4 space-y-3">
            <p className="text-sm text-gray-700 dark:text-gray-200">
              Existe um agente ativo nesta conversa (<strong>{activeDifyName}</strong>). Se você enviar a mensagem, o agente/fluxo será desativado por segurança.
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => { setShowAutomationStopConfirm(false); setPendingSendPayload(null); }}
                className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={sending}
                onClick={() => { void confirmStopAutomationAndSend(); }}
                className="px-4 py-2 text-sm bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                {sending ? 'Enviando…' : 'Sim, enviar e desativar'}
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
    <div className="relative">
      {/* ✅ NOVO: Preview de mensagem respondida */}
      {replyToMessage && (
        <div className="px-4 pt-2 pb-1 bg-chat-sidebar border-t border-gray-300 dark:border-gray-700">
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
                  : (() => {
                      const raw = replyToMessage.content != null ? String(replyToMessage.content) : '';
                      const normalized = getMessagePreviewText(raw, replyToMessage.metadata as Record<string, unknown> | undefined) || raw;
                      if (normalized) {
                        return normalized.length > 100 ? normalized.substring(0, 100) + '...' : normalized;
                      }
                      return replyToMessage.attachments && replyToMessage.attachments.length > 0
                        ? `📎 ${replyToMessage.attachments[0].original_filename || 'Anexo'}`
                        : 'Mensagem';
                    })()}
              </p>
            </div>
            <button
              onClick={clearReply}
              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-full transition-colors flex-shrink-0"
              title="Cancelar resposta"
            >
              <X className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            </button>
          </div>
        </div>
      )}

      {/* Thumbnail preview acima do input */}
      {selectedFiles.length > 0 && (
        <div className="px-4 pt-2 pb-1 bg-chat-sidebar border-t border-gray-300 dark:border-gray-700 flex flex-wrap gap-2">
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
      <div className="flex items-end gap-2 px-4 py-3 bg-chat-sidebar border-t border-gray-300 dark:border-gray-700 relative shadow-sm">
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

      {/* Botão Template: apenas instâncias Meta (envio fora da 24h) */}
      {conversationType === 'individual' && activeConversation?.integration_type === 'meta_cloud' && sendMessageAsTemplate && (
        <button
          type="button"
          onClick={() => setShowTemplateModal(true)}
          className="p-2 rounded-full flex-shrink-0 text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 dark:text-indigo-400"
          title={activeConversation?.requires_template_to_message ? 'Enviar por template (fora da janela 24h)' : 'Enviar por template (ex.: mensagem com botões)'}
        >
          <FileText className="w-5 h-5" />
        </button>
      )}

      {/* Botão Reply Buttons: apenas instâncias Meta + individual + feature flag (dentro da 24h) */}
      {conversationType === 'individual' && activeConversation?.integration_type === 'meta_cloud' && allowMetaInteractiveButtons && sendMessageWithButtons && (
        <button
          type="button"
          onClick={() => setShowButtonsModal(true)}
          className="p-2 rounded-full flex-shrink-0 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/30 dark:text-emerald-400"
          title="Adicionar botões (até 3, dentro da janela 24h)"
        >
          <LayoutList className="w-5 h-5" />
        </button>
      )}
      {/* Botão Lista interativa: apenas Meta + individual + feature flag (dentro da 24h) */}
      {conversationType === 'individual' && activeConversation?.integration_type === 'meta_cloud' && allowMetaInteractiveButtons && sendMessageWithList && (
        <button
          type="button"
          onClick={() => setShowListModal(true)}
          className="p-2 rounded-full flex-shrink-0 text-violet-600 hover:bg-violet-50 dark:hover:bg-violet-900/30 dark:text-violet-400"
          title="Enviar lista (até 10 opções, dentro da janela 24h)"
        >
          <ListOrdered className="w-5 h-5" />
        </button>
      )}

      {/* Botão Compartilhar contato (individual e grupo) */}
      {sendMessageWithContacts && (
        <button
          type="button"
          onClick={() => {
            setShowContactModal(true);
            setContactModalTab('agenda');
            setContactSelected(null);
            setContactManualName('');
            setContactManualPhone('');
            setContactAgendaSearch('');
          }}
          className="p-2 rounded-full flex-shrink-0 text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 dark:text-amber-400"
          title="Compartilhar contato"
          disabled={sending || !isConnected || isGroupInputBlocked}
        >
          <UserPlus className="w-5 h-5" />
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
            ? 'bg-chat-ring hover:bg-[#008f6f]'
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
            requestActionWithAutomationGuard(async () => {
              await stopDifyIfActive();
              sendMessageAsTemplate(conversationId, templateId, bodyParams);
              setShowTemplateModal(false);
            });
          }
        }}
      />
    )}

    {/* Modal Mensagem com botões (só Meta, dentro da 24h) */}
    {showButtonsModal && conversationId && sendMessageWithButtons && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowButtonsModal(false)}>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Mensagem com botões</h3>
            <button type="button" onClick={() => setShowButtonsModal(false)} className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Até 3 botões. Disponível apenas dentro da janela de 24h (Meta).</p>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Texto da mensagem</label>
          <textarea
            value={buttonsBodyText}
            onChange={e => setButtonsBodyText(e.target.value.slice(0, 1024))}
            placeholder="Digite o texto que aparece acima dos botões"
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-3"
          />
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Botões (título até 20 caracteres)</label>
          {buttonsList.map((btn, idx) => (
            <div key={idx} className="flex gap-2 mb-2">
              <input
                type="text"
                value={btn.id}
                onChange={e => {
                  const v = e.target.value.replace(/[^a-zA-Z0-9_-]/g, '');
                  setButtonsList(prev => prev.map((b, i) => i === idx ? { ...b, id: v } : b));
                }}
                placeholder="id"
                className="w-24 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              />
              <input
                type="text"
                value={btn.title}
                onChange={e => setButtonsList(prev => prev.map((b, i) => i === idx ? { ...b, title: e.target.value.slice(0, 20) } : b))}
                placeholder="Título"
                className="flex-1 px-2 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
              />
              {buttonsList.length > 1 && (
                <button type="button" onClick={() => setButtonsList(prev => prev.filter((_, i) => i !== idx))} className="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
          {buttonsList.length < 3 && (
            <button
              type="button"
              onClick={() => {
                const existingIds = new Set(buttonsList.map(b => b.id));
                let id = `btn_${Date.now().toString(36)}`;
                while (existingIds.has(id)) {
                  id = `btn_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
                }
                setButtonsList(prev => [...prev, { id, title: '' }]);
              }}
              className="text-sm text-emerald-600 dark:text-emerald-400 hover:underline mb-3"
            >
              + Adicionar botão
            </button>
          )}
          <div className="flex justify-end gap-2 mt-3">
            <button type="button" onClick={() => setShowButtonsModal(false)} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600">
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => {
                const body = buttonsBodyText.trim();
                const list = buttonsList.filter(b => b.id.trim() && b.title.trim());
                const ids = new Set(list.map(b => b.id));
                if (!body || list.length === 0 || ids.size !== list.length) {
                  toast.error('Preencha o texto e pelo menos 1 botão com id e título únicos.');
                  return;
                }
                requestActionWithAutomationGuard(async () => {
                  await stopDifyIfActive();
                  sendMessageWithButtons(conversationId, body, list);
                  setShowButtonsModal(false);
                  setButtonsBodyText('');
                  setButtonsList([{ id: 'btn1', title: '' }]);
                  toast.success('Mensagem com botões enviada.');
                });
              }}
              disabled={!isConnected || !buttonsBodyText.trim() || buttonsList.every(b => !b.title.trim())}
              className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white disabled:opacity-50"
            >
              Enviar
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Modal Lista interativa (só Meta, dentro da 24h) */}
    {showListModal && conversationId && sendMessageWithList && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowListModal(false)}>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Mensagem com lista</h3>
            <button type="button" onClick={() => setShowListModal(false)} className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">Até 10 opções. Apenas instâncias Meta, dentro da janela de 24h.</p>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Texto da mensagem (obrigatório)</label>
          <textarea
            value={listBodyText}
            onChange={e => setListBodyText(e.target.value.slice(0, 1024))}
            placeholder="Corpo da mensagem"
            rows={2}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-2"
          />
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Texto do botão (até 20 caracteres)</label>
          <input
            type="text"
            value={listButtonText}
            onChange={e => setListButtonText(e.target.value.slice(0, 20))}
            placeholder="Ex: Ver opções"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-2"
          />
          <label className="block text-sm text-gray-500 dark:text-gray-400 mb-1">Cabeçalho (opcional, até 60)</label>
          <input
            type="text"
            value={listHeaderText}
            onChange={e => setListHeaderText(e.target.value.slice(0, 60))}
            placeholder="Opcional"
            className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-2 text-sm"
          />
          <label className="block text-sm text-gray-500 dark:text-gray-400 mb-1">Rodapé (opcional, até 60)</label>
          <input
            type="text"
            value={listFooterText}
            onChange={e => setListFooterText(e.target.value.slice(0, 60))}
            placeholder="Opcional"
            className="w-full px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-3 text-sm"
          />
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Opções (id único, título até 24, descrição até 72; máx. 10)</label>
          {listSections.map((sec, si) => (
            <div key={si} className="mb-3">
              <input
                type="text"
                value={sec.title}
                onChange={e => setListSections(prev => prev.map((s, i) => i === si ? { ...s, title: e.target.value.slice(0, 24) } : s))}
                placeholder="Título da seção"
                className="w-full px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm mb-1"
              />
              {sec.rows.map((row, ri) => (
                <div key={ri} className="flex gap-2 mb-1 flex-wrap">
                  <input
                    type="text"
                    value={row.id}
                    onChange={e => setListSections(prev => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, id: e.target.value.replace(/[^a-zA-Z0-9_-]/g, '') } : r) } : s))}
                    placeholder="id"
                    className="w-20 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  />
                  <input
                    type="text"
                    value={row.title}
                    onChange={e => setListSections(prev => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, title: e.target.value.slice(0, 24) } : r) } : s))}
                    placeholder="Título"
                    className="flex-1 min-w-[80px] px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  />
                  <input
                    type="text"
                    value={row.description}
                    onChange={e => setListSections(prev => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, description: e.target.value.slice(0, 72) } : r) } : s))}
                    placeholder="Desc (opc)"
                    className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  />
                  {listSections.reduce((acc, s) => acc + s.rows.length, 0) > 1 && (
                    <button type="button" onClick={() => setListSections(prev => prev.map((s, i) => i === si ? { ...s, rows: s.rows.filter((_, j) => j !== ri) } : s).filter(s => s.rows.length > 0 || prev.length === 1))} className="p-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              {listSections.reduce((acc, s) => acc + s.rows.length, 0) < 10 && (
                <button
                  type="button"
                  onClick={() => {
                    const total = listSections.reduce((acc, s) => acc + s.rows.length, 0);
                    if (total >= 10) return;
                    const newId = `opt_${Date.now().toString(36)}`;
                    setListSections(prev => prev.map((s, i) => i === si ? { ...s, rows: [...s.rows, { id: newId, title: '', description: '' }] } : s));
                  }}
                  className="text-sm text-violet-600 dark:text-violet-400 hover:underline mb-1"
                >
                  + Adicionar opção
                </button>
              )}
            </div>
          ))}
          <div className="flex justify-end gap-2 mt-3">
            <button type="button" onClick={() => setShowListModal(false)} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600">
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => {
                const body = listBodyText.trim();
                const btn = listButtonText.trim();
                const allRows = listSections.flatMap(s => s.rows).filter(r => r.id.trim() && r.title.trim());
                const ids = new Set(allRows.map(r => r.id));
                if (!body || !btn || allRows.length === 0 || ids.size !== allRows.length) {
                  toast.error('Preencha o texto, o botão e pelo menos 1 opção com id e título únicos.');
                  return;
                }
                const sections = listSections.map(sec => ({
                  title: sec.title.slice(0, 24),
                  rows: sec.rows.filter(r => r.id.trim() && r.title.trim()).map(r => ({
                    id: r.id.trim(),
                    title: r.title.slice(0, 24),
                    description: r.description?.trim().slice(0, 72) || undefined,
                  })),
                })).filter(sec => sec.rows.length > 0);
                if (sections.length === 0) {
                  toast.error('Adicione pelo menos uma opção.');
                  return;
                }
                const replyToId = replyToMessage?.id ? String(replyToMessage.id) : undefined;
                requestActionWithAutomationGuard(async () => {
                  await stopDifyIfActive();
                  sendMessageWithList(conversationId, body, btn, sections, listHeaderText.trim() || undefined, listFooterText.trim() || undefined, replyToId);
                  setShowListModal(false);
                  setListBodyText('');
                  setListButtonText('');
                  setListHeaderText('');
                  setListFooterText('');
                  setListSections([{ title: 'Opções', rows: [{ id: 'opt1', title: '', description: '' }] }]);
                  clearReply();
                  toast.success('Mensagem com lista enviada.');
                });
              }}
              disabled={!isConnected || !listBodyText.trim() || !listButtonText.trim() || listSections.every(s => s.rows.every(r => !r.title.trim()))}
              className="px-3 py-1.5 rounded-lg bg-violet-600 text-white disabled:opacity-50"
            >
              Enviar
            </button>
          </div>
        </div>
      </div>
    )}

    {/* Modal Compartilhar contato */}
    {showContactModal && conversationId && sendMessageWithContacts && (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => !contactSending && setShowContactModal(false)}>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">Compartilhar contato</h3>
            <button type="button" onClick={() => !contactSending && setShowContactModal(false)} className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" disabled={contactSending}>
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex gap-2 mb-3 border-b border-gray-200 dark:border-gray-600">
            <button
              type="button"
              onClick={() => setContactModalTab('agenda')}
              className={`px-3 py-1.5 text-sm rounded-t ${contactModalTab === 'agenda' ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 font-medium' : 'text-gray-600 dark:text-gray-400'}`}
            >
              Contatos da agenda
            </button>
            <button
              type="button"
              onClick={() => setContactModalTab('manual')}
              className={`px-3 py-1.5 text-sm rounded-t ${contactModalTab === 'manual' ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 font-medium' : 'text-gray-600 dark:text-gray-400'}`}
            >
              Digitar manualmente
            </button>
          </div>
          {contactModalTab === 'agenda' && (
            <>
              <input
                type="text"
                value={contactAgendaSearch}
                onChange={e => setContactAgendaSearch(e.target.value)}
                placeholder="Buscar contato..."
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 mb-2 text-sm"
              />
              <div className="max-h-48 overflow-y-auto border border-gray-200 dark:border-gray-600 rounded-lg mb-3">
                {contactAgendaLoading && <p className="p-2 text-sm text-gray-500">Carregando...</p>}
                {!contactAgendaLoading && contactAgendaList.length === 0 && <p className="p-2 text-sm text-gray-500">Nenhum contato encontrado.</p>}
                {!contactAgendaLoading && contactAgendaList.map(c => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setContactSelected({ display_name: c.name, phone: c.phone || '' })}
                    className={`w-full text-left px-3 py-2 text-sm border-b border-gray-100 dark:border-gray-700 last:border-0 ${contactSelected?.phone === c.phone ? 'bg-amber-50 dark:bg-amber-900/30' : 'hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                  >
                    <span className="font-medium text-gray-900 dark:text-gray-100">{c.name}</span>
                    {c.phone && <span className="block text-xs text-gray-500">{c.phone}</span>}
                  </button>
                ))}
              </div>
            </>
          )}
          {contactModalTab === 'manual' && (
            <div className="space-y-2 mb-3">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Nome (máx. 255)</label>
              <input
                type="text"
                value={contactManualName}
                onChange={e => setContactManualName(e.target.value.slice(0, 255))}
                placeholder="Nome do contato"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Telefone (mín. 10 dígitos)</label>
              <input
                type="tel"
                value={contactManualPhone}
                onChange={e => setContactManualPhone(e.target.value)}
                placeholder="Ex: 11999999999"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => !contactSending && setShowContactModal(false)} className="px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600" disabled={contactSending}>
              Cancelar
            </button>
            <button
              type="button"
              disabled={contactSending || (contactModalTab === 'agenda' ? !contactSelected : contactManualPhone.replace(/\D/g, '').length < 10)}
              className="px-3 py-1.5 rounded-lg bg-amber-600 text-white disabled:opacity-50"
              aria-busy={contactSending}
              onClick={async () => {
                const replyToId = replyToMessage?.id ? String(replyToMessage.id) : undefined;
                let toSend: { display_name: string; phone: string } | null = null;
                if (contactModalTab === 'agenda' && contactSelected) {
                  toSend = contactSelected;
                } else if (contactModalTab === 'manual') {
                  const digits = contactManualPhone.replace(/\D/g, '');
                  if (digits.length < 10) {
                    toast.error('Telefone deve ter pelo menos 10 dígitos.');
                    return;
                  }
                  toSend = { display_name: contactManualName.trim() || 'Contato', phone: digits };
                }
                if (!toSend || !conversationId) return;
                setContactSending(true);
                try {
                  requestActionWithAutomationGuard(async () => {
                    await stopDifyIfActive();
                    const ok = sendMessageWithContacts(conversationId, [toSend!], replyToId);
                    if (ok) {
                      setShowContactModal(false);
                      setContactSelected(null);
                      setContactManualName('');
                      setContactManualPhone('');
                      clearReply();
                      toast.success('Contato enviado.');
                    } else {
                      toast.error('Não foi possível enviar. Verifique a conexão.');
                    }
                  });
                } finally {
                  setContactSending(false);
                }
              }}
            >
              {contactSending ? 'Enviando...' : 'Enviar'}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
