/**
 * stores/facesArcFace.js
 * ────────────────────
 * Extended Pinia store for ArcFace face recognition.
 * Adds new methods alongside the original faces.js store.
 * Import this in ArcFace-enabled components.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useFacesArcFaceStore = defineStore('faces-arcface', () => {
  const performers = ref([])
  const selectedPerformer = ref(null)
  const loading = ref(false)
  const scanning = ref(false)
  const error = ref(null)
  const searchQuery = ref('')
  const serviceStatus = ref('unknown')
  const totalFaces = ref(0)
  const hasMore = ref(false)
  const currentPage = ref(0)
  const pageSize = 50

  const performerCount = computed(() => performers.value.length)

  async function checkServiceHealth() {
    try {
      const { data } = await api.get('/faces/health')
      serviceStatus.value = data.model_loaded ? 'healthy' : 'degraded'
      return data
    } catch {
      serviceStatus.value = 'unreachable'
      return null
    }
  }

  async function fetchPerformers(opts = {}) {
    loading.value = true
    error.value = null
    try {
      const params = {
        limit: opts.limit || pageSize,
        offset: opts.offset || 0,
        order_by: opts.orderBy || 'video_count',
        search: opts.search || searchQuery.value || undefined,
        favorite_only: opts.favoriteOnly || undefined,
      }
      const { data } = await api.get('/faces/performers', { params })
      if (opts.append) {
        performers.value = [...performers.value, ...(data.performers || [])]
      } else {
        performers.value = data.performers || []
      }
      totalFaces.value = data.total_faces || 0
      hasMore.value = (data.performers?.length || 0) >= pageSize
      currentPage.value = opts.offset ? Math.floor(opts.offset / pageSize) + 1 : 1
    } catch (err) {
      error.value = err.normalizedMessage || err.message
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    await fetchPerformers({ offset: currentPage.value * pageSize, append: true })
  }

  async function fetchPerformer(id) {
    loading.value = true
    try {
      const { data } = await api.get(`/faces/performers/${id}`)
      selectedPerformer.value = data
      return data
    } catch (err) {
      error.value = err.normalizedMessage || err.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function updatePerformer(id, data) {
    try {
      const { data: updated } = await api.patch(`/faces/performers/${id}`, data)
      const idx = performers.value.findIndex(p => p.id === id)
      if (idx >= 0) performers.value[idx] = { ...performers.value[idx], ...updated }
      if (selectedPerformer.value?.id === id) {
        selectedPerformer.value = { ...selectedPerformer.value, ...updated }
      }
      return updated
    } catch (err) {
      error.value = err.normalizedMessage || err.message
    }
  }

  async function toggleFavorite(id) {
    const p = performers.value.find(p => p.id === id)
    if (p) await updatePerformer(id, { favorite: !p.favorite })
  }

  async function searchFaces(query) {
    searchQuery.value = query
    if (!query.trim()) return fetchPerformers()
    loading.value = true
    try {
      const { data } = await api.get('/faces/performers', { params: { search: query, limit: 50 } })
      performers.value = data.performers || []
      hasMore.value = false
    } catch (err) {
      error.value = err.normalizedMessage || err.message
    } finally {
      loading.value = false
    }
  }

  async function setFilter(filterId, sortBy) {
    const opts = { offset: 0 }
    if (filterId === 'favorite') opts.favoriteOnly = true
    if (filterId === 'high_quality') opts.orderBy = 'quality'
    else opts.orderBy = sortBy || 'video_count'
    await fetchPerformers(opts)
  }

  async function triggerScan(onProgress) {
    scanning.value = true
    error.value = null
    try {
      const { data } = await api.post('/faces/scan', {}, { timeout: 120000 })
      const sessionId = data.session_id

      const pollInterval = setInterval(async () => {
        try {
          const { data: status } = await api.get(`/faces/scan/${sessionId}`)
          onProgress?.(status.stage, status.progress)
          if (status.status === 'completed' || status.status === 'error') {
            clearInterval(pollInterval)
            scanning.value = false
            if (status.status === 'error') {
              error.value = status.error_message || 'Scan failed'
            } else {
              await fetchPerformers()
            }
          }
        } catch { /* ignore poll errors */ }
      }, 2000)

      setTimeout(() => {
        clearInterval(pollInterval)
        if (scanning.value) { scanning.value = false; error.value = 'Scan timed out' }
      }, 1_800_000)
    } catch (err) {
      scanning.value = false
      error.value = err.normalizedMessage || err.message || 'Failed to start scan'
    }
  }

  async function searchByFace(file) {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/faces/match', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
    return data.matches || []
  }

  async function trainPerformer(performerId, faceDetectionId, isPositive = true) {
    await api.post(`/faces/performers/${performerId}/train`, {
      face_detection_id: faceDetectionId,
      is_positive: isPositive,
    })
  }

  async function mergePerformers(targetId, sourceId) {
    await api.post(`/faces/performers/${targetId}/merge`, { source_id: sourceId })
    await fetchPerformers()
  }

  async function deletePerformer(id) {
    await api.delete(`/faces/performers/${id}`)
    performers.value = performers.value.filter(p => p.id !== id)
    if (selectedPerformer.value?.id === id) selectedPerformer.value = null
  }

  return {
    performers, selectedPerformer, loading, scanning, error,
    searchQuery, serviceStatus, totalFaces, hasMore, currentPage,
    performerCount, checkServiceHealth, fetchPerformers, fetchPerformer,
    updatePerformer, toggleFavorite, searchFaces, setFilter,
    triggerScan, searchByFace, trainPerformer, mergePerformers,
    deletePerformer, loadMore,
  }
})
