/**
 * Formata texto do WhatsApp com negrito, itálico, riscado e monoespaçado
 * Suporta os mesmos formatos do WhatsApp:
 * - *texto* ou _texto_ = negrito
 * - _texto_ = itálico
 * - ~texto~ = riscado
 * - `texto` = monoespaçado
 */

export function formatWhatsAppText(text: string): string {
  if (!text) return '';

  // Escapar HTML existente para segurança
  let formatted = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  // ✅ IMPORTANTE: Processar na ordem correta para evitar conflitos
  // 1. Primeiro monoespaçado (backtick) - tem prioridade
  // 2. Depois riscado (til)
  // 3. Depois negrito e itálico (asterisco e underscore)
  
  // Monoespaçado: `texto`
  formatted = formatted.replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded font-mono text-sm">$1</code>');

  // Riscado: ~texto~
  formatted = formatted.replace(/~([^~]+)~/g, '<span class="line-through">$1</span>');

  // Negrito: *texto* (um asterisco)
  // Mas precisa evitar conflito com itálico quando há _texto_
  // WhatsApp prioriza: se tem *texto* e _texto_, * é negrito e _ é itálico
  formatted = formatted.replace(/\*([^*]+)\*/g, '<strong class="font-semibold">$1</strong>');

  // Itálico: _texto_ (underscore)
  // Só aplicar se não for parte de um negrito já processado
  formatted = formatted.replace(/_([^_]+)_/g, '<em class="italic">$1</em>');

  return formatted;
}

/**
 * Versão que também processa URLs (combina formatação WhatsApp + links)
 */
export function formatWhatsAppTextWithLinks(text: string): string {
  if (!text) return '';

  // Primeiro formatar texto do WhatsApp
  let formatted = formatWhatsAppText(text);

  // Depois processar URLs
  const urlRegex = /(https?:\/\/[^\s<>"{}|\\^`[\]]+|www\.[^\s<>"{}|\\^`[\]]+|[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}[^\s<>"{}|\\^`[\]]*)/gi;

  // Converter URLs em links (mas não dentro de tags HTML já criadas)
  formatted = formatted.replace(urlRegex, (url, offset, string) => {
    // Verificar se a URL não está dentro de uma tag HTML
    const beforeUrl = string.substring(0, offset);
    const openTags = (beforeUrl.match(/<[^>]*>/g) || []).length;
    const closeTags = (beforeUrl.match(/<\/[^>]*>/g) || []).length;
    
    // Se está dentro de uma tag HTML, não converter
    if (openTags > closeTags) {
      return url;
    }

    // Adicionar https:// se não tiver protocolo
    let href = url;
    if (!url.match(/^https?:\/\//i)) {
      href = url.startsWith('www.') ? `https://${url}` : `https://${url}`;
    }

    // Validar URL antes de criar link
    try {
      new URL(href);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline break-all">${url}</a>`;
    } catch {
      return url;
    }
  });

  return formatted;
}

