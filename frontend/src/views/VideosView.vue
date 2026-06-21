<template>
  <div class="videos-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-bar">
        <Search :size="16" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search videos..."
          @input="onSearch"
        />
      </div>
      <div class="toolbar-actions">
        <select v-model="sortBy" class="glass-select">
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="views">Most Views</option>
          <option value="title">Title A-Z</option>
        </select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="videoStore.loading" class="loading-grid">
      <div v-for="i in 8" :key="i" class="skeleton-card glass">
        <div class="skeleton-thumb" />
        <div class="skeleton-meta">
          <div class="skeleton-line w-75" />
          <div class="skeleton-line w-50" />
        </div>
      </div>
    </div>

    <!-- Grid -->
    <div v-else-if="filteredVideos.length" class="video-grid">
      <VideoCard
        v-for="video in filteredVideos"
        :key="video.id"
        :video="video"
        @click="goToVideo(video.id)"
      />
    </div>

    <!-- Empty -->
    <div v-else class="empty-state">
      <Video :size="48" />
      <h3>No videos found</h3>
      <p>Try adjusting your search or filters.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, Video } from 'lucide-vue-next'
import VideoCard from '../components/VideoCard.vue'
import { useVideoStore } from '../stores/videos.js'

const router = useRouter()
const videoStore = useVideoStore()
const searchQuery = ref('')
const sortBy = ref('newest')
let searchTimer = null

const filteredVideos = computed(() => {
  let vids = [...videoStore.videos]
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    vids = vids.filter(v => (v.title || '').toLowerCase().includes(q))
  }
  switch (sortBy.value) {
    case 'oldest': vids.sort((a, b) => new Date(a.created_at) - new Date(b.created_at)); break
    case 'views': vids.sort((a, b) => (b.views || 0) - (a.views || 0)); break
    case 'title': vids.sort((a, b) => (a.title || '').localeCompare(b.title || '')); break
    default: vids.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  }
  return vids
})

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    if (searchQuery.value.trim()) {
      videoStore.searchVideos(searchQuery.value)
    } else {
      videoStore.fetchVideos()
    }
  }, 300)
}

function goToVideo(id) {
  router.push(`/videos/${id}`)
}

onMounted(() => {
  videoStore.fetchVideos()
})
</script>

<style scoped>
.videos-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1400px;
  margin: 0 auto;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-shrink: 0;
}

.search-bar {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  color: var(--text-quaternary);
  transition: border-color var(--ease-fast);
}
.search-bar:focus-within { border-color: var(--accent); }
.search-bar input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: var(--text-sm);
  color: var(--text-primary);
}
.search-bar input::placeholder { color: var(--text-quaternary); }

.glass-select {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-5);
}

.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-5);
}

.skeleton-card {
  overflow: hidden;
}
.skeleton-thumb {
  aspect-ratio: 16 / 9;
  background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-meta {
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-75 { width: 75%; }
.skeleton-line.w-50 { width: 50%; }
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-12) 0;
  color: var(--text-quaternary);
}
.empty-state h3 {
  font-size: var(--text-xl);
  color: var(--text-tertiary);
}

@media (max-width: 640px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .video-grid { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
}
</style>
