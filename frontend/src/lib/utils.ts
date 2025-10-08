import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number, currency: string = 'BRL'): string {
  if (currency === 'BRL') {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(amount)
  }
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount)
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('pt-BR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date))
}

export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const targetDate = new Date(date)
  const diffInSeconds = Math.floor((now.getTime() - targetDate.getTime()) / 1000)

  if (diffInSeconds < 60) {
    return 'agora'
  } else if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60)
    return `${minutes}m atrás`
  } else if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600)
    return `${hours}h atrás`
  } else {
    const days = Math.floor(diffInSeconds / 86400)
    return `${days}d atrás`
  }
}

export function getSentimentColor(sentiment: number): string {
  if (sentiment >= 0.3) return 'text-green-600'
  if (sentiment <= -0.3) return 'text-red-600'
  return 'text-yellow-600'
}

export function getSentimentEmoji(sentiment: number): string {
  if (sentiment >= 0.3) return '😊'
  if (sentiment <= -0.3) return '😞'
  return '😐'
}

export function getSatisfactionColor(satisfaction: number): string {
  if (satisfaction >= 80) return 'text-green-600'
  if (satisfaction >= 60) return 'text-blue-600'
  if (satisfaction >= 40) return 'text-yellow-600'
  if (satisfaction >= 20) return 'text-orange-600'
  return 'text-red-600'
}

export function getEmotionEmoji(emotion: string): string {
  const emotionEmojis: Record<string, string> = {
    'positivo': '😊',
    'negativo': '😞',
    'neutro': '😐',
    'feliz': '😄',
    'triste': '😢',
    'irritado': '😠',
    'ansioso': '😰',
    'calmo': '😌',
    'confuso': '😕',
    'surpreso': '😲',
  }
  
  return emotionEmojis[emotion?.toLowerCase()] || '😐'
}
