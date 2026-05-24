import { defineStore } from 'pinia'
import type { Todo, TodoStats, TodoCreate, TodoUpdate } from '~/types'
import { todosApi } from '~/utils/api'

interface TodosState {
  todos: Todo[]
  stats: TodoStats | null
  loading: boolean
  error: string | null
  filters: {
    status: string | undefined
    priority: string | undefined
    tag: string | undefined
    search: string | undefined
    folder_id: string | undefined
  }
  sort_by: string | undefined
}

export const useTodosStore = defineStore('todos', {
  state: (): TodosState => ({
    todos: [],
    stats: null,
    loading: false,
    error: null,
    filters: {
      status: undefined,
      priority: undefined,
      tag: undefined,
      search: undefined,
      folder_id: undefined,
    },
    sort_by: undefined,
  }),

  getters: {
    filteredTodos(state): Todo[] {
      return state.todos
    },

    todoStats(state): TodoStats | null {
      return state.stats
    },
  },

  actions: {
    async fetchTodos() {
      this.loading = true
      this.error = null

      try {
        const params: Record<string, string | undefined> = {
          status: this.filters.status,
          priority: this.filters.priority,
          tag: this.filters.tag,
          search: this.filters.search,
          folder_id: this.filters.folder_id,
          sort_by: this.sort_by,
        }
        this.todos = await todosApi.list(params)
      } catch (err: any) {
        this.error = extractErrorMessage(err)
        throw err
      } finally {
        this.loading = false
      }
    },

    async createTodo(data: TodoCreate): Promise<Todo> {
      this.error = null

      try {
        const todo = await todosApi.create(data)
        this.todos.unshift(todo)
        return todo
      } catch (err: any) {
        this.error = extractErrorMessage(err)
        throw err
      }
    },

    async updateTodo(id: string, data: TodoUpdate): Promise<Todo> {
      this.error = null

      try {
        const updated = await todosApi.update(id, data)
        const index = this.todos.findIndex((t) => t.id === id)
        if (index !== -1) {
          this.todos[index] = updated
        }
        return updated
      } catch (err: any) {
        this.error = extractErrorMessage(err)
        throw err
      }
    },

    async deleteTodo(id: string): Promise<void> {
      this.error = null

      try {
        await todosApi.delete(id)
        this.todos = this.todos.filter((t) => t.id !== id)
      } catch (err: any) {
        this.error = extractErrorMessage(err)
        throw err
      }
    },

    async fetchStats(): Promise<void> {
      try {
        this.stats = await todosApi.stats()
      } catch (err: any) {
        this.error = extractErrorMessage(err)
        throw err
      }
    },

    setFilter(key: 'status' | 'priority' | 'tag' | 'search' | 'folder_id', value: string | undefined) {
      this.filters[key] = value
    },

    setSortBy(value: string | undefined) {
      this.sort_by = value
    },
  },
})

function extractErrorMessage(err: any): string {
  const statusCode = err?.response?.status || err?.statusCode || err?.status
  const data = err?.response?._data || err?.data

  if (statusCode === 422) {
    if (data?.detail && Array.isArray(data.detail)) {
      return data.detail.map((e: any) => e.message || e.msg).join('. ')
    }
    return data?.detail || 'Validation error'
  }

  if (statusCode === 404) {
    return data?.detail || 'Todo not found'
  }

  if (err?.message === 'Request timed out. Please try again.') {
    return err.message
  }

  return 'Something went wrong. Please try again.'
}
