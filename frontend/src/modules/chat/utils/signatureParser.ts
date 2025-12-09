/**
 * Utilitário para processar assinaturas em mensagens
 * Formato esperado: "Paulo Bernal disse:\n\n{mensagem}"
 */

export interface ParsedMessage {
  signature: string | null; // "Paulo Bernal disse:" ou null
  content: string; // Conteúdo da mensagem sem assinatura
}

/**
 * Extrai assinatura do conteúdo da mensagem
 * Formato: "Nome disse:\n\n{mensagem}"
 */
export function parseMessageSignature(content: string): ParsedMessage {
  if (!content) {
    return { signature: null, content: '' };
  }

  // Regex para detectar padrão "Nome disse:\n\n" no início
  // Aceita variações: "Nome disse:", "Nome disse:\n", "Nome disse:\n\n"
  const signatureRegex = /^([^:]+)\s+disse:\s*\n*\s*/;
  const match = content.match(signatureRegex);

  if (match) {
    const signature = match[1].trim() + ' disse:';
    const messageContent = content.substring(match[0].length).trim();
    return {
      signature,
      content: messageContent
    };
  }

  // Sem assinatura
  return {
    signature: null,
    content: content.trim()
  };
}

/**
 * Remove assinatura do conteúdo (útil para edição)
 */
export function removeSignature(content: string): string {
  const parsed = parseMessageSignature(content);
  return parsed.content;
}

