<template>
  <div class="relative">
    <button
      ref="buttonRef"
      type="button"
      class="relative p-2 rounded-md text-secondary-500 dark:text-secondary-400 hover:text-secondary-900 dark:hover:text-white hover:bg-secondary-100 dark:hover:bg-secondary-700 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary-500"
      :aria-label="`Notifications (${unreadCount} unread)`"
      :aria-expanded="open"
      aria-haspopup="true"
      @click="toggle"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
      <span
        v-if="unreadCount > 0"
        class="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full"
        aria-hidden="true"
      >
        {{ unreadCount > 9 ? '9+' : unreadCount }}
      </span>
    </button>

    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      leave-active-class="transition-all duration-100 ease-in"
      enter-from-class="opacity-0 -translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-96 max-w-[calc(100vw-1rem)] bg-white dark:bg-secondary-800 rounded-lg shadow-xl border border-secondary-200 dark:border-secondary-700 overflow-hidden z-30"
        role="menu"
      >
        <div class="flex items-center justify-between px-4 py-3 border-b border-secondary-200 dark:border-secondary-700">
          <h3 class="text-sm font-semibold text-secondary-900 dark:text-white">Notifications</h3>
          <div v-if="notifications.length" class="flex items-center gap-3 text-xs">
            <button
              v-if="unreadCount > 0"
              type="button"
              class="text-primary-600 dark:text-primary-400 hover:underline focus:outline-none"
              @click="onMarkAllRead"
            >
              Mark all read
            </button>
            <button
              type="button"
              class="text-red-600 dark:text-red-400 hover:underline focus:outline-none"
              @click="onClearAll"
            >
              Clear all
            </button>
          </div>
        </div>

        <div class="max-h-96 overflow-y-auto">
          <div
            v-if="!loading && notifications.length === 0"
            class="flex flex-col items-center justify-center py-10 px-4"
          >
            <svg class="w-10 h-10 text-secondary-300 dark:text-secondary-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <p class="text-sm text-secondary-500 dark:text-secondary-400">No notifications</p>
          </div>

          <p
            v-else-if="loading && notifications.length === 0"
            class="px-4 py-6 text-center text-sm text-secondary-500 dark:text-secondary-400"
          >
            Loading...
          </p>

          <ul v-else class="divide-y divide-secondary-200 dark:divide-secondary-700">
            <li
              v-for="n in notifications"
              :key="n.id"
              class="px-4 py-3 flex items-start gap-3 transition-colors duration-150 hover:bg-secondary-50 dark:hover:bg-secondary-700/50 cursor-pointer"
              :class="{ 'bg-primary-50/40 dark:bg-primary-900/10': !n.read }"
              @click="onItemClick(n)"
            >
              <span
                class="mt-1.5 inline-block flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
                :class="iconWrapperClasses(n.notification_type)"
                aria-hidden="true"
              >
                <svg v-if="n.notification_type === 'reminder_due'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <svg v-else-if="n.notification_type === 'ai_coach'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M5 19h14a2 2 0 001.732-3L13.732 4a2 2 0 00-3.464 0L3.268 16A2 2 0 005 19z" />
                </svg>
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-secondary-900 dark:text-white truncate">
                  {{ titleFor(n) }}
                </p>
                <p class="text-xs text-secondary-500 dark:text-secondary-400 mt-0.5">
                  <span v-if="n.notification_type === 'ai_coach'">AI nudge</span>
                  <span v-else-if="n.notification_type === 'reminder_due'">Reminder</span>
                  <span v-else-if="n.notification_type === 'overdue'">Overdue</span>
                  · {{ formatRelative(n.delivered_at) }}
                </p>
              </div>
              <span
                v-if="!n.read"
                class="mt-1.5 inline-block w-2 h-2 rounded-full bg-primary-500 flex-shrink-0"
                aria-hidden="true"
              ></span>
            </li>
          </ul>
        </div>
      </div>
    </Transition>

    <!-- Click-away backdrop -->
    <div
      v-if="open"
      class="fixed inset-0 z-20"
      aria-hidden="true"
      @click="open = false"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useNotifications } from '~/composables/useNotifications'
import type { Notification } from '~/types'

const {
  notifications,
  unreadCount,
  loading,
  fetch,
  check,
  markRead,
  markAllRead,
  clearAll,
} = useNotifications()

const open = ref(false)
const buttonRef = ref<HTMLButtonElement | null>(null)

let pollHandle: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  await fetch()
  // Poll every 60s for fresh notifications.
  pollHandle = setInterval(() => {
    void check()
  }, 60_000)
})

onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle)
})

async function toggle() {
  open.value = !open.value
  if (open.value) {
    // Refresh on open so the panel reflects the latest state.
    await check()
  }
}

async function onMarkAllRead() {
  await markAllRead()
}

async function onClearAll() {
  await clearAll()
}

async function onItemClick(n: Notification) {
  if (!n.read) await markRead(n.id)
}

function titleFor(n: Notification): string {
  if (n.notification_type === 'reminder_due') {
    return `Reminder: ${n.todo_title}`
  }
  if (n.notification_type === 'overdue') {
    return `Overdue: ${n.todo_title}`
  }
  if (n.notification_type === 'ai_coach') {
    return n.todo_title
  }
  return n.todo_title
}

function iconWrapperClasses(kind: Notification['notification_type']): string {
  if (kind === 'overdue') {
    return 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400'
  }
  if (kind === 'ai_coach') {
    return 'bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400'
  }
  return 'bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400'
}

function formatRelative(iso: string): string {
  const date = new Date(iso)
  if (isNaN(date.getTime())) return ''
  const diffMs = Date.now() - date.getTime()
  const diffMin = Math.round(diffMs / 60_000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>
