/**
 * Separador de data entre grupos de mensagens (ex.: "Hoje", "Ontem", "12 de março").
 */

import React from 'react';

interface DateSeparatorProps {
  label: string;
}

export function DateSeparator({ label }: DateSeparatorProps) {
  return (
    <div className="flex items-center justify-center py-3 px-2">
      <span className="text-[11px] font-medium tracking-wide text-zinc-500 dark:text-zinc-400 bg-zinc-100/90 dark:bg-zinc-800/80 px-3.5 py-1.5 rounded-full shadow-sm border border-zinc-200/60 dark:border-zinc-600/50">
        {label}
      </span>
    </div>
  );
}
