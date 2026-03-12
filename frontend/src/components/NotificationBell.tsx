/**
 * Sino de notificações: transferências, tarefas, agenda.
 * Badge com contador; dropdown com lista e ações (abrir conversa / agenda).
 */
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { Button } from './ui/Button'
import { useNotificationStore, type UserNotification } from '@/stores/notificationStore'
import { useChatStore } from '@/modules/chat/store/chatStore'
import { cn } from '@/lib/utils'

const MAX_LIST_HEIGHT = 320

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Agora'
    if (diffMins < 60) return `${diffMins} min`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h`
    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d`
    return d.toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })
  } catch {
    return ''
  }
}

function truncate(str: string, max: number): string {
  if (!str) return ''
  return str.length <= max ? str : str.slice(0, max) + '…'
}

export function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const { notifications, markAsRead, markAllAsRead } = useNotificationStore()

  const unreadCount = notifications.filter((n) => !n.read).length
  const sorted = [...notifications].sort((a, b) => {
    if (a.read !== b.read) return a.read ? 1 : -1
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })

  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  }, [])

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [open])

  const handleItemClick = (n: UserNotification) => {
    markAsRead(n.id)
    setOpen(false)
    if (n.type === 'conversation_transferred' && (n.conversation_id || n.conversation)) {
      const { conversations, setActiveConversation, addConversation } = useChatStore.getState()
      const existing = conversations.find((c) => String(c.id) === String(n.conversation_id))
      const conv = existing ?? (n.conversation as Record<string, unknown>)
      if (conv) {
        if (!existing && n.conversation) addConversation(n.conversation as never)
        setActiveConversation(conv as never)
      }
      navigate('/chat')
    } else if (n.type === 'task_reminder' || n.type === 'agenda_reminder') {
      navigate('/agenda')
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(!open)}
        className="relative"
        aria-label={
          unreadCount > 0
            ? `${unreadCount} notificação${unreadCount !== 1 ? 'ões' : ''} não lida${unreadCount !== 1 ? 's' : ''}`
            : 'Notificações'
        }
        title={unreadCount > 0 ? `${unreadCount} pendência(s)` : 'Notificações'}
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span
            className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[10px] font-medium text-white dark:bg-brand-500"
            aria-hidden
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div
          className="absolute bottom-full right-0 z-50 mb-2 w-80 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
          role="dialog"
          aria-label="Lista de notificações"
        >
          <div className="border-b border-gray-100 px-3 py-2 dark:border-gray-700">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
              Notificações
            </span>
          </div>
          <div
            className="overflow-y-auto py-1"
            style={{ maxHeight: MAX_LIST_HEIGHT }}
          >
            {sorted.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                Nenhuma pendência
              </p>
            ) : (
              sorted.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleItemClick(n)}
                  className={cn(
                    'flex w-full flex-col gap-0.5 px-4 py-2.5 text-left text-sm transition-colors',
                    n.read
                      ? 'text-gray-600 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-700/50'
                      : 'bg-brand-50/50 font-medium text-gray-800 hover:bg-brand-50 dark:bg-brand-900/20 dark:text-gray-200 dark:hover:bg-brand-900/30'
                  )}
                >
                  <span className="font-medium">{n.title}</span>
                  <span className="line-clamp-2 text-xs text-gray-500 dark:text-gray-400">
                    {truncate(n.message, 120)}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">
                    {formatTime(n.created_at)}
                  </span>
                </button>
              ))
            )}
          </div>
          {notifications.some((n) => !n.read) && (
            <div className="border-t border-gray-100 px-2 py-1.5 dark:border-gray-700">
              <button
                type="button"
                onClick={() => {
                  markAllAsRead()
                  setOpen(false)
                }}
                className="w-full rounded px-2 py-1.5 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-900/30"
              >
                Marcar todas como lidas
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
