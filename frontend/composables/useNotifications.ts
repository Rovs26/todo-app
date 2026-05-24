import { ref, computed } from 'vue'
import type { Notification } from '~/types'
import { notificationsApi } from '~/utils/api'

const notifications = ref<Notification[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const desktopPermission = ref<'default' | 'granted' | 'denied' | 'unsupported'>(
  typeof window === 'undefined' || typeof Notification === 'undefined'
    ? 'unsupported'
    : (Notification.permission as any),
)

export function useNotifications() {
  const unreadCount = computed(
    () => notifications.value.filter((n) => !n.read).length,
  )

  async function requestDesktopPermission(): Promise<void> {
    if (
      typeof window === 'undefined' ||
      typeof Notification === 'undefined' ||
      desktopPermission.value === 'granted' ||
      desktopPermission.value === 'denied'
    ) {
      return
    }
    try {
      const result = await Notification.requestPermission()
      desktopPermission.value = result as any
    } catch {
      desktopPermission.value = 'denied'
    }
  }

  function fireDesktop(items: Notification[]) {
    if (
      typeof window === 'undefined' ||
      typeof Notification === 'undefined' ||
      desktopPermission.value !== 'granted'
    ) {
      return
    }
    for (const n of items) {
      const title =
        n.notification_type === 'reminder_due'
          ? `Reminder: ${n.todo_title}`
          : n.notification_type === 'overdue'
          ? `Overdue: ${n.todo_title}`
          : n.notification_type === 'ai_coach'
          ? 'AI nudge'
          : 'Notification'
      try {
        new Notification(title, {
          body:
            n.notification_type === 'ai_coach'
              ? n.todo_title
              : 'Open the dashboard for details.',
          tag: n.id,
        })
      } catch {
        /* swallow — some browsers throw outside HTTPS */
      }
    }
  }

  async function fetch(unreadOnly = false): Promise<void> {
    loading.value = true
    error.value = null
    try {
      notifications.value = await notificationsApi.list(unreadOnly)
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to load notifications'
    } finally {
      loading.value = false
    }
  }

  async function check(): Promise<Notification[]> {
    try {
      const fresh = await notificationsApi.check()
      if (fresh.length) {
        const existing = new Set(notifications.value.map((n) => n.id))
        const additions = fresh.filter((n) => !existing.has(n.id))
        if (additions.length) {
          notifications.value = [...additions, ...notifications.value]
          fireDesktop(additions)
        }
      }
      return fresh
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to check notifications'
      return []
    }
  }

  async function markRead(id: string): Promise<void> {
    const target = notifications.value.find((n) => n.id === id)
    if (!target || target.read) return
    target.read = true
    try {
      await notificationsApi.markRead(id)
    } catch (err: any) {
      target.read = false
      error.value = err?.message ?? 'Failed to mark as read'
    }
  }

  async function markAllRead(): Promise<void> {
    const snapshot = notifications.value.map((n) => ({ id: n.id, read: n.read }))
    notifications.value.forEach((n) => {
      n.read = true
    })
    try {
      await notificationsApi.markAllRead()
    } catch (err: any) {
      snapshot.forEach((s) => {
        const n = notifications.value.find((x) => x.id === s.id)
        if (n) n.read = s.read
      })
      error.value = err?.message ?? 'Failed to mark all as read'
    }
  }

  async function clearAll(): Promise<void> {
    const previous = [...notifications.value]
    notifications.value = []
    try {
      await notificationsApi.clearAll()
    } catch (err: any) {
      notifications.value = previous
      error.value = err?.message ?? 'Failed to clear notifications'
    }
  }

  return {
    notifications,
    unreadCount,
    loading,
    error,
    desktopPermission,
    fetch,
    check,
    markRead,
    markAllRead,
    clearAll,
    requestDesktopPermission,
  }
}
