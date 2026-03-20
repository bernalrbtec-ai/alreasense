/**
 * Utilitários para manipulação de mensagens
 * Centraliza lógica reutilizável para evitar duplicação
 */

import type { Message, MessageAttachment } from '../types';

const EXTENSION_MIME_MAP: Record<string, string> = {
  txt: 'text/plain',
  pdf: 'application/pdf',
  doc: 'application/msword',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  xls: 'application/vnd.ms-excel',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  aac: 'audio/aac',
  amr: 'audio/amr',
  mp3: 'audio/mpeg',
  m4a: 'audio/mp4',
  ogg: 'audio/ogg',
  '3gp': 'video/3gpp',
  mp4: 'video/mp4',
  xml: 'application/xml',
  json: 'application/json',
  zip: 'application/zip',
  rar: 'application/vnd.rar',
  '7z': 'application/x-7z-compressed',
};

/**
 * Ordena mensagens por timestamp (mais antiga primeiro - estilo WhatsApp)
 */
export function sortMessagesByTimestamp(messages: Message[]): Message[] {
  return [...messages].sort((messageA, messageB) => {
    const timeA = new Date(messageA.created_at).getTime();
    const timeB = new Date(messageB.created_at).getTime();
    return timeA - timeB; // Mais antiga primeiro (timeA - timeB)
  });
}

/**
 * Faz merge de attachments baseado em timestamp e estado de processamento
 * Prioriza attachments com file_url válido e mais recentes
 */
export function mergeAttachments(
  existing: MessageAttachment[],
  incoming: MessageAttachment[]
): MessageAttachment[] {
  if (!existing || existing.length === 0) {
    return incoming || [];
  }
  
  if (!incoming || incoming.length === 0) {
    return existing;
  }
  
  // Mapear attachments existentes por ID
  const existingMap = new Map<string, MessageAttachment>();
  existing.forEach(att => {
    existingMap.set(att.id, att);
  });
  
  // Fazer merge inteligente
  const merged: MessageAttachment[] = [];
  const processedIds = new Set<string>();
  
  // Processar attachments novos (priorizar)
  incoming.forEach(newAtt => {
    const existingAtt = existingMap.get(newAtt.id);
    
    if (existingAtt) {
      // ✅ Merge baseado em timestamp e estado
      const existingHasUrl = isValidFileUrl(existingAtt.file_url);
      const newHasUrl = isValidFileUrl(newAtt.file_url);
      
      // Priorizar attachment com URL válida
      if (existingHasUrl && !newHasUrl) {
        merged.push(existingAtt);
      } else if (newHasUrl && !existingHasUrl) {
        merged.push(newAtt);
      } else {
        // Ambos têm ou não têm URL - usar o mais recente (comparar created_at se disponível)
        const existingTime = existingAtt.created_at ? new Date(existingAtt.created_at).getTime() : 0;
        const newTime = newAtt.created_at ? new Date(newAtt.created_at).getTime() : 0;
        merged.push(newTime > existingTime ? newAtt : existingAtt);
      }
    } else {
      // Novo attachment
      merged.push(newAtt);
    }
    
    processedIds.add(newAtt.id);
  });
  
  // Adicionar attachments existentes que não foram atualizados
  existing.forEach(existingAtt => {
    if (!processedIds.has(existingAtt.id)) {
      merged.push(existingAtt);
    }
  });
  
  return merged;
}

/**
 * Verifica se uma URL de arquivo é válida (não é placeholder)
 */
function isValidFileUrl(url: string | undefined | null): boolean {
  if (!url || !url.trim()) {
    return false;
  }
  
  // URLs do WhatsApp ou Evolution API são temporárias/placeholders
  if (url.includes('whatsapp.net') || url.includes('evo.')) {
    return false;
  }
  
  return true;
}

/**
 * Sanitiza conteúdo HTML para prevenir XSS
 * Por enquanto, apenas remove tags HTML (não usamos DOMPurify ainda)
 */
export function sanitizeContent(content: string): string {
  if (!content) {
    return '';
  }
  
  // ✅ Por enquanto, apenas escapar caracteres HTML básicos
  // TODO: Implementar DOMPurify se necessário para permitir HTML formatado
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Valida tamanho de arquivo
 */
export function validateFileSize(file: File, maxSizeMB: number = 50): { valid: boolean; error?: string } {
  const maxSizeBytes = maxSizeMB * 1024 * 1024;
  
  if (file.size > maxSizeBytes) {
    return {
      valid: false,
      error: `Arquivo muito grande. Máximo: ${maxSizeMB}MB`
    };
  }
  
  return { valid: true };
}

/**
 * Valida tipo de arquivo
 */
export function validateFileType(file: File, allowedTypes: string[]): { valid: boolean; error?: string } {
  const resolvedMime = resolveFileMimeType(file);
  const isAllowed = allowedTypes.some(type => {
    if (type.endsWith('/*')) {
      const baseType = type.slice(0, -2);
      return resolvedMime.startsWith(baseType);
    }
    // Aceita tipo exato ou com parâmetros (ex: "text/xml; charset=utf-8")
    return resolvedMime === type || resolvedMime.startsWith(type + ';');
  });
  
  if (!isAllowed) {
    return {
      valid: false,
      error: 'Tipo de arquivo não permitido'
    };
  }
  
  return { valid: true };
}

/**
 * Resolve MIME type com fallback por extensão quando file.type vem vazio.
 */
export function resolveFileMimeType(file: File): string {
  const raw = (file.type || '').trim().toLowerCase();
  if (raw) return raw;
  const filename = (file.name || '').toLowerCase();
  const ext = filename.includes('.') ? filename.split('.').pop() || '' : '';
  return EXTENSION_MIME_MAP[ext] || 'application/octet-stream';
}

/** Metadata shape for placeholder detection */
type MessageMetadataForPreview = {
  interactive_list?: unknown;
  template_message?: unknown;
  interactive_reply_buttons?: unknown;
} | null | undefined;

/**
 * Texto de preview/placeholder para mensagens especiais (template, botões, lista, etc.).
 * Centraliza labels em um único lugar para MessageList, ConversationList, modais e input.
 */
export function getMessagePreviewText(
  content: string | undefined | null,
  metadata?: MessageMetadataForPreview
): string {
  const raw = (content ?? '').trim();
  if (raw === '[button]' || raw === '[interactive]') return 'Resposta de botão';
  if (raw === '[templateMessage]') return 'Mensagem de template';
  if (raw === '[buttonsMessage]') return 'Mensagem com botões';
  if (raw === '[listMessage]') return '';
  if (metadata?.interactive_list != null && typeof metadata.interactive_list === 'object') {
    const il = metadata.interactive_list as { body_text?: string };
    return (il?.body_text && String(il.body_text).trim()) ? String(il.body_text).trim() : '';
  }
  return raw || '';
}

