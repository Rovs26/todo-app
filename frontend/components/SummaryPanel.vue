<template>
  <div class="bg-gradient-to-br from-primary-50 to-white dark:from-primary-900/20 dark:to-secondary-800 rounded-lg border border-primary-100 dark:border-primary-900/40 p-4">
    <div class="flex items-center gap-2 mb-2">
      <svg class="w-4 h-4 text-primary-600 dark:text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      <h3 class="text-sm font-semibold text-secondary-900 dark:text-white">Smart summary</h3>
      <button
        type="button"
        class="ml-auto text-xs text-primary-600 dark:text-primary-400 hover:underline"
        :disabled="loading"
        @click="refresh"
      >
        {{ loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <p
      v-if="data?.summary"
      class="text-sm leading-relaxed text-secondary-700 dark:text-secondary-300"
    >
      {{ data.summary }}
    </p>
    <p v-else-if="loading" class="text-sm text-secondary-500 dark:text-secondary-400">
      Generating summary...
    </p>
    <p v-else-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    <p v-else class="text-sm text-secondary-500 dark:text-secondary-400">
      Click refresh to generate a summary of your todos.
    </p>

    <div v-if="data?.top_tags?.length" class="mt-3 flex flex-wrap gap-1.5">
      <span
        v-for="t in data.top_tags"
        :key="t.name"
        class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-white/60 dark:bg-secondary-700/60 text-secondary-700 dark:text-secondary-300"
      >
        #{{ t.name }} <span class="text-secondary-400">{{ t.count }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import type { SummaryResponse } from '~/types'
import { todosApi } from '~/utils/api'

const props = defineProps<{ refreshKey?: number }>()

const data = ref<SummaryResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function refresh() {
  loading.value = true
  error.value = null
  try {
    data.value = await todosApi.summary()
  } catch (err: any) {
    error.value = err?.message ?? 'Could not generate summary'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
watch(() => props.refreshKey, refresh)

defineExpose({ refresh })
</script>
