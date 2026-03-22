import { useState } from 'react';
import { ChevronDown, ChevronUp, Lightbulb } from 'lucide-react';
import type { HubInsights } from './useChatOpsMetrics';

export function ChatOpsInsightsRow({ insights }: { insights: HubInsights }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 border-t border-gray-200/90 dark:border-gray-600/80 pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-medium text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white w-full text-left"
        aria-expanded={open}
      >
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        <Lightbulb className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" aria-hidden />
        Ver insights
      </button>
      {open && (
        <div className="mt-2 space-y-2 text-xs text-gray-600 dark:text-gray-400">
          <ul className="list-disc pl-4 space-y-1">
            {insights.alerts.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          {insights.suggestion && (
            <p className="text-amber-800 dark:text-amber-200/90 bg-amber-50/90 dark:bg-amber-900/20 rounded-md px-2 py-1.5 border border-amber-200/80 dark:border-amber-800/50">
              {insights.suggestion}
            </p>
          )}
          <p className="text-[10px] text-gray-500 dark:text-gray-500">{insights.trend}</p>
        </div>
      )}
    </div>
  );
}
