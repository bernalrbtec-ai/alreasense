import React from 'react';
import { Inbox, Users, Clock, AlertTriangle } from 'lucide-react';
import { STATUS_CHIP_VARIANT_CLASSES } from '../../utils/conversationStatusPresentation';
import type { HubMetricCard } from './useChatOpsMetrics';

const ICONS = {
  inbox: Inbox,
  users: Users,
  clock: Clock,
  alert: AlertTriangle,
} as const;

export const ChatOpsMetricCard = React.memo(function ChatOpsMetricCard({ card }: { card: HubMetricCard }) {
  const Icon = ICONS[card.icon];
  const toneClass = STATUS_CHIP_VARIANT_CLASSES[card.tone];
  return (
    <div
      className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 min-w-0 flex-1 sm:flex-none sm:min-w-[7.5rem] border border-gray-200/80 dark:border-gray-600/80 ${toneClass}`}
      title={card.label}
    >
      <Icon className="w-3.5 h-3.5 flex-shrink-0 opacity-80" aria-hidden />
      <div className="min-w-0 text-left">
        <p className="text-[10px] font-medium leading-tight opacity-90 truncate">{card.label}</p>
        <p className="text-sm font-semibold tabular-nums">{card.value}</p>
      </div>
    </div>
  );
});

export function ChatOpsMetricsRow({ metrics }: { metrics: HubMetricCard[] }) {
  return (
    <div className="flex flex-wrap gap-2 items-stretch justify-start sm:justify-between">
      {metrics.map((m) => (
        <ChatOpsMetricCard key={m.id} card={m} />
      ))}
    </div>
  );
}
