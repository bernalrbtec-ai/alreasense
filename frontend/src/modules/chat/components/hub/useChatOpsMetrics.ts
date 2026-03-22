import { useMemo } from 'react';
import { shallow } from 'zustand/shallow';
import { useChatStore } from '../../store/chatStore';
import { filterConversationsForActiveView } from '../../utils/filterConversationsForActiveView';
import { isConversationUrgent, URGENT_AFTER_MIN } from '../../utils/conversationStatusPresentation';
import type { StatusChipVariant } from '../../utils/conversationStatusPresentation';

export interface HubMetricCard {
  id: string;
  label: string;
  value: string | number;
  /** Ícone lucide name opcional — renderizado no row */
  icon: 'inbox' | 'users' | 'clock' | 'alert';
  tone: StatusChipVariant;
}

export interface HubInsights {
  alerts: string[];
  suggestion: string | null;
  trend: string;
}

export function useChatOpsMetrics() {
  const { conversations, activeDepartment, waitingForResponseMode, activeConversation } = useChatStore(
    (s) => ({
      conversations: s.conversations,
      activeDepartment: s.activeDepartment,
      waitingForResponseMode: s.waitingForResponseMode,
      activeConversation: s.activeConversation,
    }),
    shallow
  );

  return useMemo(() => {
    const queue = filterConversationsForActiveView(
      conversations,
      activeDepartment,
      waitingForResponseMode,
      { activeConversation }
    );

    const nonClosed = queue.filter((c) => (c.status ?? 'open') !== 'closed');
    const unreadTotal = nonClosed.reduce((s, c) => s + (c.unread_count ?? 0), 0);
    const pendingTriagem = nonClosed.filter((c) => (c.status ?? 'pending') === 'pending').length;
    const emAtendimento = nonClosed.filter((c) => {
      const st = c.status ?? 'pending';
      return st === 'open' && !!c.assigned_to;
    }).length;
    const urgentes = nonClosed.filter((c) => isConversationUrgent(c)).length;

    const metrics: HubMetricCard[] = [
      {
        id: 'queue',
        label: 'Na fila (aba atual)',
        value: queue.length,
        icon: 'inbox',
        tone: 'neutral',
      },
      {
        id: 'unread',
        label: 'Não lidos',
        value: unreadTotal,
        icon: 'users',
        tone: unreadTotal > 0 ? 'warning' : 'success',
      },
      {
        id: 'pending',
        label: 'Triagem',
        value: pendingTriagem,
        icon: 'clock',
        tone: pendingTriagem > 0 ? 'warning' : 'neutral',
      },
      {
        id: 'urgent',
        label: `Urgentes (>${URGENT_AFTER_MIN}m)`,
        value: urgentes,
        icon: 'alert',
        tone: urgentes > 0 ? 'danger' : 'success',
      },
    ];

    const insights: HubInsights = {
      alerts: [
        urgentes > 0
          ? `${urgentes} conversa(s) com não lidos há mais de ${URGENT_AFTER_MIN} min na vista atual.`
          : 'Nenhuma conversa urgente na vista atual.',
        emAtendimento > 0
          ? `${emAtendimento} em atendimento ou abertas nesta vista.`
          : 'Sem conversas abertas nesta vista.',
      ],
      suggestion:
        pendingTriagem > 5
          ? 'Considere priorizar a triagem — várias conversas aguardam departamento.'
          : null,
      trend: 'Estimativa com base na lista visível (mesmos filtros que a sidebar).',
    };

    return { metrics, insights, queueEstimate: queue.length };
  }, [conversations, activeDepartment, waitingForResponseMode, activeConversation]);
}
