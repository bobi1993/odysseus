import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/client.js'

export const useFacesStore = defineStore('faces', () => {
  const performers = ref([])
  const selectedPerformer = ref(null)
  const loading = ref(false)
  const scanning = ref(false)
  const error = ref(null)
  const searchQuery = ref('')

  async function fetchFaces() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/faces/')
      performers.value = data
    } catch (err) {
      error.value = err.normalizedMessage
    } finally {
      loading.value = false
    }
  }

  async function fetchPerformer(id) {
    loading.value = true
    try {
      const { data } = await api.get(`/faces/${id}`)
      selectedPerformer.value = data
      return data
    } catch (err) {
      error.value = err.normalizedMessage
      return null
    } finally {
      loading.value = false
    }
  }

  async function triggerScan() {
    scanning.value = true
    try {
      await api.post('/faces/scan')
      // Reload faces after scan
      await fetchFaces()
    } catch (err) {
      error.value = err.normalizedMessage
    } finally {
      scanning.value = false
    }
  }

  async function searchFaces(query) {
    searchQuery.value = query
    if (!query.trim()) return fetchFaces()
    loading.value = true
    try {
      const { data } = await api.get('/faces/', { params: { q: query } })
      performers.value = data
    } catch (err) {
      error.value = err.normalizedMessage
    } finally {
      loading.value = false
    }
  }

  return {
    performers, selectedPerformer, loading, scanning, error,
    searchQuery,
    fetchFaces, fetchPerformer, triggerScan, searchFaces,
  }
})
