import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useVideoStore = defineStore('videos', () => {
  const videos = ref([])
  const currentVideo = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const searchQuery = ref('')
  const favorites = ref(new Set())

  const favoriteIds = computed(() => favorites.value)

  async function fetchVideos(params = {}) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/videos/', { params })
      videos.value = data.videos || data
    } catch (err) {
      error.value = err.normalizedMessage
    } finally {
      loading.value = false
    }
  }

  async function fetchVideo(id) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get(`/videos/${id}`)
      currentVideo.value = data
      return data
    } catch (err) {
      error.value = err.normalizedMessage
      return null
    } finally {
      loading.value = false
    }
  }

  async function toggleFavorite(id) {
    const wasFav = favorites.value.has(id)
    if (wasFav) {
      favorites.value.delete(id)
    } else {
      favorites.value.add(id)
    }
    try {
      await api.post(`/videos/${id}/favorite`)
    } catch (err) {
      // Rollback
      if (wasFav) favorites.value.add(id)
      else favorites.value.delete(id)
    }
  }

  async function searchVideos(query) {
    searchQuery.value = query
    if (!query.trim()) return fetchVideos()
    return fetchVideos({ search: query })
  }

  return {
    videos, currentVideo, loading, error,
    searchQuery, favorites, favoriteIds,
    fetchVideos, fetchVideo, toggleFavorite, searchVideos,
  }
})
