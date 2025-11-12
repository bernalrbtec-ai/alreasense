/**
 * Utilitários para manipulação de mensagens
 * Centraliza lógica reutilizável para evitar duplicação
 */

import type { Message, MessageAttachment } from '../types';

/**
 * Ordena mensagens por timestamp (mais recente primeiro - feed moderno)
 * ✅ MELHORIA UX: Mensagens mais recentes aparecem no topo
 */
export function sortMessagesByTimestamp(messages: Message[]): Message[] {
  return [...messages].sort((a, b) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    return timeB - timeA; // ✅ Invertido: mais recente primeiro (timeB - timeA)
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
  const isAllowed = allowedTypes.some(type => {
    if (type.endsWith('/*')) {
      const baseType = type.slice(0, -2);
      return file.type.startsWith(baseType);
    }
    return file.type === type;
  });
  
  if (!isAllowed) {
    return {
      valid: false,
      error: 'Tipo de arquivo não permitido'
    };
  }
  
  return { valid: true };
}

