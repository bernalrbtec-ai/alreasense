/**
 * Formatação de tempo relativo para chat (sidebar e mensagens).
 */

import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

/**
 * Retorna tempo relativo em português (ex.: "há 5 min", "há 2 horas").
 */
export function formatTimeAgo(dateString: string | undefined): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return '';
    return formatDistanceToNow(date, { addSuffix: true, locale: ptBR });
  } catch {
    return '';
  }
}

/**
 * Retorna tempo relativo sem sufixo (ex.: "5 minutos", "2 horas").
 */
export function formatTimeRelative(dateString: string | undefined): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return '';
    return formatDistanceToNow(date, { addSuffix: false, locale: ptBR });
  } catch {
    return '';
  }
}
