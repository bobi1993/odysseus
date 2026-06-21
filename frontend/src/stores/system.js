import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useSystemStore = defineStore('system', () => {
  const health = ref(null)
  const resources = ref(null)
  const loading = ref(false)

  async function fetchHealth() {
    try {
      const { data } = await api.get('/health/')
      health.value = data
    } catch (err) {
      health.value = { status: 'error', error: err.normalizedMessage }
    }
  }

  async function fetchResources() {
    loading.value = true
    try {
      const { data } = await api.get('/system/resources/')
      resources.value = data
    } catch (err) {
      resources.value = null
    } finally {
      loading.value = false
    }
  }

  const cpuPercent = computed(() => resources.value?.cpu_percent ?? 0)
  const ramPercent = computed(() => resources.value?.ram_percent ?? 0)
  const diskPercent = computed(() => resources.value?.disk_percent ?? 0)
  const ramUsed = computed(() => resources.value?.ram_used_gb ?? 0)
  const ramTotal = computed(() => resources.value?.ram_total_gb ?? 0)
  const diskUsed = computed(() => resources.value?.disk_used_gb ?? 0)
  const diskTotal = computed(() => resources.value?.disk_total_gb ?? 0)

  return {
    health, resources, loading,
    cpuPercent, ramPercent, diskPercent,
    ramUsed, ramTotal, diskUsed, diskTotal,
    fetchHealth, fetchResources,
  }
})
