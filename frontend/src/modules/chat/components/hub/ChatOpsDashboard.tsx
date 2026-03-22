import { ChatOpsMetricsRow } from './ChatOpsMetricsRow';
import { ChatOpsInsightsRow } from './ChatOpsInsightsRow';
import { useChatOpsMetrics } from './useChatOpsMetrics';

export function ChatOpsDashboard() {
  const { metrics, insights } = useChatOpsMetrics();
  return (
    <div
      className="flex-shrink-0 px-3 py-2 bg-chat-sidebar border-b border-gray-300 dark:border-gray-700 min-h-[3.25rem]"
      aria-label="Métricas da fila"
    >
      <ChatOpsMetricsRow metrics={metrics} />
      <ChatOpsInsightsRow insights={insights} />
    </div>
  );
}
