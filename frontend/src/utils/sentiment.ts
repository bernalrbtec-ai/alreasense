/**
 * Configuração de sentimento para UI (sidebar e indicadores).
 */

export type SentimentScore = 'positive' | 'negative' | 'neutral';

export const sentimentConfig: Record<
  SentimentScore,
  { dot: string; label: string; text: string }
> = {
  positive: {
    dot: 'bg-emerald-500',
    label: 'Positivo',
    text: 'text-emerald-600 dark:text-emerald-400',
  },
  negative: {
    dot: 'bg-red-500',
    label: 'Negativo',
    text: 'text-red-600 dark:text-red-400',
  },
  neutral: {
    dot: 'bg-amber-400',
    label: 'Neutro',
    text: 'text-amber-600 dark:text-amber-400',
  },
};
