import { ref, computed } from 'vue'
import type { Notification } from '~/types'
import { notificationsApi } from '~/utils/api'

const notifications = ref<Notification[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

export function useNotifications() {
  const unreadCount = computed(
    () => notifications.value.filter((n) => !n.read).length,
  )

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
        notifications.value = [...additions, ...notifications.value]
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
    fetch,
    check,
    markRead,
    markAllRead,
    clearAll,
  }
}
