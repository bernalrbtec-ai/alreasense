/**
 * Utilitário para formatação de telefone (como WhatsApp faz)
 * 
 * Exibe número formatado quando não há nome disponível
 */

/**
 * Formata telefone para exibição (como WhatsApp faz).
 * 
 * Exemplos:
 * - +5511999999999 → (11) 99999-9999
 * - 5511999999999 → (11) 99999-9999
 * - 11999999999 → (11) 99999-9999
 * 
 * @param phone Telefone em qualquer formato
 * @returns Telefone formatado para exibição
 */
export function formatPhoneForDisplay(phone: string): string {
  if (!phone) return '';
  
  // Remover caracteres não numéricos
  const clean = phone.replace(/\D/g, '');
  
  // Se começar com 55 (código do Brasil), remover
  let digits = clean;
  if (digits.startsWith('55') && digits.length >= 12) {
    digits = digits.substring(2);
  }
  
  // Formatar: (XX) XXXXX-XXXX para celular ou (XX) XXXX-XXXX para fixo
  if (digits.length === 11) {
    // Celular com DDD: (11) 99999-9999
    return `(${digits.substring(0, 2)}) ${digits.substring(2, 7)}-${digits.substring(7, 11)}`;
  } else if (digits.length === 10) {
    // Fixo com DDD: (11) 9999-9999
    return `(${digits.substring(0, 2)}) ${digits.substring(2, 6)}-${digits.substring(6, 10)}`;
  } else if (digits.length === 9) {
    // Celular sem DDD: 99999-9999
    return `${digits.substring(0, 5)}-${digits.substring(5, 9)}`;
  } else if (digits.length === 8) {
    // Fixo sem DDD: 9999-9999
    return `${digits.substring(0, 4)}-${digits.substring(4, 8)}`;
  } else {
    // Se não conseguir formatar, retornar como está (limitado a 15 chars)
    return digits.substring(0, 15) || phone;
  }
}

/**
 * Obtém nome de exibição da conversa (nome ou telefone formatado).
 * 
 * Se não tiver nome válido, retorna telefone formatado (como WhatsApp faz).
 * 
 * @param conversation Conversa com contact_name e contact_phone
 * @returns Nome para exibição
 */
export function getDisplayName(conversation: {
  contact_name?: string | null;
  contact_phone?: string;
  conversation_type?: 'individual' | 'group' | 'broadcast';
  group_metadata?: {
    group_name?: string;
  };
}): string {
  // Grupos: usar nome do grupo ou metadata
  if (conversation.conversation_type === 'group') {
    return (
      conversation.group_metadata?.group_name ||
      conversation.contact_name ||
      'Grupo WhatsApp'
    );
  }
  
  // Individuais: usar nome ou telefone formatado
  const name = conversation.contact_name?.trim();
  
  // Se tem nome válido (não é só número, não é placeholder)
  if (name && 
      name !== 'Grupo WhatsApp' && 
      !/^[\d\s\-\(\)]+$/.test(name) && // Não é só números/formatos de telefone
      name.length > 0) {
    return name;
  }
  
  // Fallback: usar telefone formatado
  if (conversation.contact_phone) {
    return formatPhoneForDisplay(conversation.contact_phone);
  }
  
  return 'Contato';
}

