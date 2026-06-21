import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)

  const pendingTasks = computed(() => tasks.value.filter(t => t.status === 'pending'))
  const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'))
  const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))
  const failedTasks = computed(() => tasks.value.filter(t => t.status === 'failed'))

  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/tasks/')
      tasks.value = data
    } catch (err) {
      error.value = err.normalizedMessage
    } finally {
      loading.value = false
    }
  }

  async function createTask(taskData) {
    try {
      const { data } = await api.post('/tasks/', taskData)
      tasks.value.unshift(data)
      return data
    } catch (err) {
      error.value = err.normalizedMessage
      return null
    }
  }

  async function dispatchTask(id) {
    try {
      const { data } = await api.post(`/tasks/${id}/dispatch`)
      const idx = tasks.value.findIndex(t => t.id === id)
      if (idx !== -1) tasks.value[idx] = data
      return data
    } catch (err) {
      error.value = err.normalizedMessage
      return null
    }
  }

  async function completeTask(id, result = null) {
    try {
      const { data } = await api.post(`/tasks/${id}/complete`, { result })
      const idx = tasks.value.findIndex(t => t.id === id)
      if (idx !== -1) tasks.value[idx] = data
      return data
    } catch (err) {
      error.value = err.normalizedMessage
      return null
    }
  }

  return {
    tasks, loading, error,
    pendingTasks, runningTasks, completedTasks, failedTasks,
    fetchTasks, createTask, dispatchTask, completeTask,
  }
})
