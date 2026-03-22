/**
 * Rótulo e variante visual únicos para estado da conversa (sidebar + header).
 */
import type { Conversation } from '../types';

export type StatusChipVariant = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'muted';

export interface ConversationStatusPresentation {
  label: string;
  variant: StatusChipVariant;
  /** Lista: conversa pendente com não lidos há mais de 30 minutos */
  showUrgentIndicator: boolean;
}

const URGENT_AFTER_MIN = 30;

function isConversationUrgent(conv: Conversation): boolean {
  const status = conv.status ?? 'pending';
  const lastAt = conv.last_message_at;
  const ageMs = lastAt ? Date.now() - new Date(lastAt).getTime() : NaN;
  return (
    status === 'pending' &&
    (conv.unread_count ?? 0) > 0 &&
    lastAt != null &&
    lastAt !== '' &&
    !Number.isNaN(ageMs) &&
    ageMs > URGENT_AFTER_MIN * 60 * 1000
  );
}

function parseAssignedToId(conv: Conversation): string | number | null {
  const a = conv.assigned_to;
  if (a == null || a === '') return null;
  if (typeof a === 'number') return a;
  if (typeof a === 'string' && a.trim() !== '') return a;
  return null;
}

export function getConversationStatusPresentation(
  conv: Conversation,
  opts: { activeAgentName?: string | null }
): ConversationStatusPresentation {
  const status = conv.status ?? 'pending';
  const agentName = opts.activeAgentName?.trim() || null;

  const urgent = isConversationUrgent(conv);

  if (status === 'closed') {
    return { label: 'Encerrada', variant: 'muted', showUrgentIndicator: false };
  }

  if (agentName) {
    return {
      label: `IA ativa · ${agentName}`,
      variant: 'success',
      showUrgentIndicator: urgent,
    };
  }

  if (status === 'pending') {
    return {
      label: 'Aguardando triagem',
      variant: 'warning',
      showUrgentIndicator: urgent,
    };
  }

  const assigned = parseAssignedToId(conv);
  if (assigned) {
    const human = conv.assigned_to_data;
    const short =
      [human?.first_name, human?.last_name].filter(Boolean).join(' ').trim() ||
      human?.email ||
      'Atendente';
    return {
      label: `Em atendimento · ${short}`,
      variant: 'info',
      showUrgentIndicator: false,
    };
  }

  return {
    label: 'Atendimento ativo',
    variant: 'info',
    showUrgentIndicator: false,
  };
}

/** Classes Tailwind para o chip (dark mode incluído). */
export const STATUS_CHIP_VARIANT_CLASSES: Record<StatusChipVariant, string> = {
  neutral: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100',
  success: 'bg-green-100 text-green-900 dark:bg-green-900/40 dark:text-green-100',
  warning: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100',
  danger: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-100',
  info: 'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-100',
  muted: 'bg-gray-200/90 text-gray-600 dark:bg-gray-600 dark:text-gray-200',
};
