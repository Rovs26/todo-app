import { ref } from 'vue'
import type { Folder, FolderCreate, FolderStats, FolderUpdate } from '~/types'
import { foldersApi } from '~/utils/api'

const folders = ref<Folder[]>([])
const stats = ref<FolderStats[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

export function useFolders() {
  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const [list, statsList] = await Promise.all([
        foldersApi.list(),
        foldersApi.stats(),
      ])
      folders.value = list
      stats.value = statsList
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to load folders'
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      stats.value = await foldersApi.stats()
    } catch (err: any) {
      error.value = err?.message ?? 'Failed to refresh folder stats'
    }
  }

  async function create(data: FolderCreate): Promise<Folder | null> {
    try {
      const created = await foldersApi.create(data)
      folders.value = [...folders.value, created].sort((a, b) =>
        a.name.localeCompare(b.name),
      )
      await fetchStats()
      return created
    } catch (err: any) {
      error.value = extractError(err)
      return null
    }
  }

  async function update(id: string, data: FolderUpdate): Promise<Folder | null> {
    try {
      const updated = await foldersApi.update(id, data)
      folders.value = folders.value
        .map((f) => (f.id === id ? updated : f))
        .sort((a, b) => a.name.localeCompare(b.name))
      await fetchStats()
      return updated
    } catch (err: any) {
      error.value = extractError(err)
      return null
    }
  }

  async function remove(id: string): Promise<boolean> {
    try {
      await foldersApi.delete(id)
      folders.value = folders.value.filter((f) => f.id !== id)
      await fetchStats()
      return true
    } catch (err: any) {
      error.value = extractError(err)
      return false
    }
  }

  return {
    folders,
    stats,
    loading,
    error,
    fetchAll,
    fetchStats,
    create,
    update,
    remove,
  }
}

function extractError(err: any): string {
  const status = err?.response?.status || err?.statusCode || err?.status
  const data = err?.response?._data || err?.data
  if (status === 409) return data?.detail || 'Folder name already exists'
  if (status === 422) {
    if (Array.isArray(data?.detail)) {
      return data.detail.map((e: any) => e.message || e.msg).join('. ')
    }
    return data?.detail || 'Invalid folder'
  }
  if (err?.message) return err.message
  return 'Something went wrong with folders'
}
