/**
 * Store de notificações do usuário (sino): transferências, tarefas, agenda.
 * Alimentado pelo WebSocket (user_notification); limpo no logout.
 */
import { create } from 'zustand'

const MAX_NOTIFICATIONS = 50

export type UserNotificationType = 'conversation_transferred' | 'task_reminder' | 'agenda_reminder'

export interface UserNotification {
  id: string
  type: UserNotificationType
  title: string
  message: string
  read: boolean
  created_at: string
  conversation_id?: string
  task_id?: string
  due_date?: string
  date?: string
  conversation?: Record<string, unknown>
}

interface NotificationState {
  notifications: UserNotification[]
  addNotification: (notification: Omit<UserNotification, 'read' | 'created_at'>) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  clear: () => void
}

function pruneToLimit(notifications: UserNotification[], max: number): UserNotification[] {
  if (notifications.length <= max) return notifications
  const sorted = [...notifications].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
  return sorted.slice(0, max)
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],

  addNotification: (notification) => {
    const now = new Date().toISOString()
    const item: UserNotification = {
      ...notification,
      read: false,
      created_at: now,
    }
    set((state) => {
      const existingIndex = state.notifications.findIndex((n) => n.id === item.id)
      let next: UserNotification[]
      if (existingIndex >= 0) {
        const existing = state.notifications[existingIndex]
        next = state.notifications.map((n, i) =>
          i === existingIndex
            ? { ...n, ...item, read: existing.read, created_at: n.created_at }
            : n
        )
      } else {
        next = [item, ...state.notifications]
      }
      return { notifications: pruneToLimit(next, MAX_NOTIFICATIONS) }
    })
  },

  markAsRead: (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    }))
  },

  markAllAsRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
    }))
  },

  clear: () => set({ notifications: [] }),
}))

/** Para ser chamado no logout (closeGlobalTenantSocket). */
export function clearUserNotifications(): void {
  useNotificationStore.getState().clear()
}
