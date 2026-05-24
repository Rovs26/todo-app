<template>
  <div class="bg-white dark:bg-secondary-800 rounded-lg border border-secondary-200 dark:border-secondary-700 p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold text-secondary-900 dark:text-white">Focus timer</h3>
      <span
        class="text-[11px] uppercase tracking-wide font-medium px-2 py-0.5 rounded-full"
        :class="phaseChipClasses"
      >
        {{ phaseLabel }}
      </span>
    </div>

    <select
      v-model="selectedTodoId"
      class="input-field text-sm mb-3"
      :disabled="running"
      aria-label="Pomodoro target todo"
    >
      <option value="">No todo (just focus)</option>
      <option v-for="t in activeTodos" :key="t.id" :value="t.id">
        {{ t.title }}
      </option>
    </select>

    <div class="flex items-center justify-center my-2">
      <div class="text-4xl font-mono font-bold tabular-nums text-secondary-900 dark:text-white">
        {{ formatted }}
      </div>
    </div>

    <div class="flex items-center justify-between gap-2 mt-3">
      <button
        v-if="!running"
        type="button"
        class="btn-primary text-sm flex-1"
        @click="start"
      >
        Start
      </button>
      <button
        v-else
        type="button"
        class="btn-secondary text-sm flex-1"
        @click="pause"
      >
        Pause
      </button>
      <button
        type="button"
        class="btn-secondary text-sm"
        :disabled="running && elapsed === 0"
        @click="reset"
      >
        Reset
      </button>
      <button
        type="button"
        class="btn-secondary text-sm"
        @click="togglePhase"
      >
        {{ phase === 'focus' ? 'Break' : 'Focus' }}
      </button>
    </div>

    <p v-if="phase === 'focus' && selectedTodo" class="mt-3 text-xs text-secondary-500 dark:text-secondary-400 truncate">
      Tracking time on: <span class="font-medium text-secondary-700 dark:text-secondary-300">{{ selectedTodo.title }}</span>
      <span v-if="selectedTodo.time_spent_seconds"> · total {{ humanTotal(selectedTodo.time_spent_seconds) }}</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { Todo } from '~/types'
import { todosApi } from '~/utils/api'

const props = defineProps<{ todos: Todo[] }>()
const emit = defineEmits<{ logged: [todoId: string, seconds: number] }>()

const FOCUS_SECONDS = 25 * 60
const BREAK_SECONDS = 5 * 60

type Phase = 'focus' | 'break'
const phase = ref<Phase>('focus')
const elapsed = ref(0) // seconds elapsed in the current phase
const running = ref(false)
const selectedTodoId = ref<string>('')

let intervalHandle: ReturnType<typeof setInterval> | null = null

const total = computed(() => (phase.value === 'focus' ? FOCUS_SECONDS : BREAK_SECONDS))
const remaining = computed(() => Math.max(0, total.value - elapsed.value))

const formatted = computed(() => {
  const r = remaining.value
  const m = Math.floor(r / 60)
  const s = r % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

const phaseLabel = computed(() => (phase.value === 'focus' ? 'Focus' : 'Break'))
const phaseChipClasses = computed(() =>
  phase.value === 'focus'
    ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400'
    : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
)

const activeTodos = computed(() =>
  props.todos.filter((t) => t.status !== 'done').slice(0, 50),
)

const selectedTodo = computed(() =>
  props.todos.find((t) => t.id === selectedTodoId.value) ?? null,
)

function start() {
  if (running.value) return
  running.value = true
  intervalHandle = setInterval(() => {
    elapsed.value += 1
    if (remaining.value <= 0) {
      onPhaseComplete()
    }
  }, 1000)
}

function pause() {
  running.value = false
  if (intervalHandle) {
    clearInterval(intervalHandle)
    intervalHandle = null
  }
}

function reset() {
  pause()
  elapsed.value = 0
}

function togglePhase() {
  pause()
  phase.value = phase.value === 'focus' ? 'break' : 'focus'
  elapsed.value = 0
}

async function onPhaseComplete() {
  const completedSeconds = total.value
  const targetTodoId = selectedTodoId.value
  pause()
  elapsed.value = total.value

  if (phase.value === 'focus' && targetTodoId) {
    try {
      await todosApi.addTime(targetTodoId, completedSeconds)
      emit('logged', targetTodoId, completedSeconds)
    } catch {
      // swallow — UI still rolled forward
    }
  }

  // Auto-rotate to the other phase, ready to start
  phase.value = phase.value === 'focus' ? 'break' : 'focus'
  elapsed.value = 0
}

watch(running, (val) => {
  if (!val && intervalHandle) {
    clearInterval(intervalHandle)
    intervalHandle = null
  }
})

onUnmounted(() => {
  if (intervalHandle) clearInterval(intervalHandle)
})

function humanTotal(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return remM ? `${h}h ${remM}m` : `${h}h`
}
</script>
