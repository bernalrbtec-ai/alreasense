/**
 * Separador de data entre grupos de mensagens (ex.: "Hoje", "Ontem", "12 de março").
 */

import React from 'react';

interface DateSeparatorProps {
  label: string;
}

export function DateSeparator({ label }: DateSeparatorProps) {
  return (
    <div className="flex items-center justify-center py-2">
      <span className="text-xs text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-full">
        {label}
      </span>
    </div>
  );
}
