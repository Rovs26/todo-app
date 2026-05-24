<template>
  <div class="bg-white dark:bg-secondary-800 rounded-lg border border-secondary-200 dark:border-secondary-700 p-4">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <button
        type="button"
        class="p-1.5 rounded-md text-secondary-500 hover:bg-secondary-100 dark:hover:bg-secondary-700 transition-colors"
        aria-label="Previous month"
        @click="shiftMonth(-1)"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" /></svg>
      </button>
      <div class="flex items-center gap-2">
        <h3 class="text-base font-semibold text-secondary-900 dark:text-white">{{ monthLabel }}</h3>
        <button
          v-if="!isCurrentMonth"
          type="button"
          class="text-xs text-primary-600 dark:text-primary-400 hover:underline"
          @click="goToToday"
        >
          Today
        </button>
      </div>
      <button
        type="button"
        class="p-1.5 rounded-md text-secondary-500 hover:bg-secondary-100 dark:hover:bg-secondary-700 transition-colors"
        aria-label="Next month"
        @click="shiftMonth(1)"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
      </button>
    </div>

    <!-- Day-of-week header -->
    <div class="grid grid-cols-7 gap-px text-[11px] font-medium uppercase tracking-wide text-secondary-500 dark:text-secondary-400 mb-1">
      <div v-for="d in dayLabels" :key="d" class="text-center py-1">{{ d }}</div>
    </div>

    <!-- Grid -->
    <div class="grid grid-cols-7 gap-1">
      <div
        v-for="(cell, idx) in cells"
        :key="idx"
        class="min-h-[5rem] rounded-md border p-1 text-xs flex flex-col"
        :class="cellClasses(cell)"
      >
        <div class="flex items-center justify-between">
          <span
            class="font-medium"
            :class="cell.isToday ? 'text-primary-600 dark:text-primary-400' : 'text-secondary-700 dark:text-secondary-300'"
          >
            {{ cell.dayNumber }}
          </span>
          <span v-if="cell.todos.length > 1" class="text-[10px] text-secondary-400">
            {{ cell.todos.length }}
          </span>
        </div>

        <ul class="mt-1 space-y-0.5 overflow-hidden">
          <li
            v-for="t in cell.todos.slice(0, 3)"
            :key="t.id"
            class="truncate px-1 py-0.5 rounded text-[11px] cursor-pointer transition-colors"
            :class="todoClasses(t)"
            :title="t.title"
            @click="$emit('select', t)"
          >
            {{ t.title }}
          </li>
          <li v-if="cell.todos.length > 3" class="text-[10px] text-secondary-400 px-1">
            +{{ cell.todos.length - 3 }} more
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Todo } from '~/types'

const props = defineProps<{ todos: Todo[] }>()
defineEmits<{ select: [todo: Todo] }>()

const today = new Date()
today.setHours(0, 0, 0, 0)

// Anchor date is always the first day of the displayed month
const cursor = ref(new Date(today.getFullYear(), today.getMonth(), 1))

const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const monthLabel = computed(() =>
  cursor.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
)

const isCurrentMonth = computed(() =>
  cursor.value.getMonth() === today.getMonth() && cursor.value.getFullYear() === today.getFullYear(),
)

interface Cell {
  date: Date
  dayNumber: number
  inMonth: boolean
  isToday: boolean
  isoDate: string
  todos: Todo[]
}

const cells = computed<Cell[]>(() => {
  const first = new Date(cursor.value.getFullYear(), cursor.value.getMonth(), 1)
  const start = new Date(first)
  start.setDate(1 - first.getDay()) // back up to the previous Sunday

  // Group todos by due_date
  const byDate = new Map<string, Todo[]>()
  for (const t of props.todos) {
    if (!t.due_date) continue
    const list = byDate.get(t.due_date) ?? []
    list.push(t)
    byDate.set(t.due_date, list)
  }

  const out: Cell[] = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    out.push({
      date: d,
      dayNumber: d.getDate(),
      inMonth: d.getMonth() === cursor.value.getMonth(),
      isToday: d.getTime() === today.getTime(),
      isoDate: iso,
      todos: byDate.get(iso) ?? [],
    })
  }
  return out
})

function shiftMonth(delta: number) {
  cursor.value = new Date(
    cursor.value.getFullYear(),
    cursor.value.getMonth() + delta,
    1,
  )
}

function goToToday() {
  cursor.value = new Date(today.getFullYear(), today.getMonth(), 1)
}

function cellClasses(cell: Cell): string {
  const base = 'border-secondary-100 dark:border-secondary-700'
  if (!cell.inMonth) return `bg-secondary-50/40 dark:bg-secondary-900/40 text-secondary-300 ${base}`
  if (cell.isToday) return `bg-primary-50/40 dark:bg-primary-900/10 border-primary-300 dark:border-primary-700`
  return `bg-white dark:bg-secondary-800 ${base}`
}

function todoClasses(t: Todo): string {
  if (t.status === 'done') {
    return 'bg-green-100/60 text-green-800 line-through dark:bg-green-900/20 dark:text-green-400'
  }
  if (t.priority === 'high') {
    return 'bg-red-100 text-red-800 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400'
  }
  if (t.priority === 'medium') {
    return 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400'
  }
  return 'bg-primary-100 text-primary-800 hover:bg-primary-200 dark:bg-primary-900/30 dark:text-primary-400'
}
</script>
