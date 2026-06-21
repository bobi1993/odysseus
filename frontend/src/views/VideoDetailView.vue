<template>
  <div class="video-detail">
    <div v-if="videoStore.loading" class="loading">
      <div class="skeleton-player" />
    </div>

    <div v-else-if="videoStore.currentVideo" class="content">
      <!-- Player area -->
      <div class="player-area glass">
        <div class="player-placeholder">
          <Play :size="48" />
          <span>Video Player</span>
          <small>{{ videoStore.currentVideo.title }}</small>
        </div>
      </div>

      <!-- Info -->
      <div class="video-info">
        <h1 class="video-title">{{ videoStore.currentVideo.title }}</h1>
        <div class="video-meta">
          <span v-if="videoStore.currentVideo.source_type" class="meta-chip">
            {{ videoStore.currentVideo.source_type }}
          </span>
          <span v-if="videoStore.currentVideo.duration" class="meta-chip">
            {{ formatDuration(videoStore.currentVideo.duration) }}
          </span>
          <span v-if="videoStore.currentVideo.views" class="meta-chip">
            {{ videoStore.currentVideo.views }} views
          </span>
        </div>
        <p v-if="videoStore.currentVideo.description" class="video-desc">
          {{ videoStore.currentVideo.description }}
        </p>

        <div class="video-actions">
          <button
            class="btn"
            :class="isFavorite ? 'btn-danger' : 'btn-ghost'"
            @click="toggleFav"
          >
            <Heart :size="16" :fill="isFavorite ? 'currentColor' : 'none'" />
            {{ isFavorite ? 'Favorited' : 'Favorite' }}
          </button>
          <button class="btn btn-ghost" @click="$router.back()">
            <ArrowLeft :size="16" />
            Back
          </button>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <Video :size="48" />
      <h3>Video not found</h3>
      <router-link to="/videos" class="btn btn-primary">Browse Videos</router-link>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Play, Heart, ArrowLeft, Video } from 'lucide-vue-next'
import { useVideoStore } from '../stores/videos.js'

const route = useRoute()
const videoStore = useVideoStore()

const isFavorite = computed(() => {
  if (!videoStore.currentVideo) return false
  return videoStore.favoriteIds.has(videoStore.currentVideo.id)
})

function toggleFav() {
  if (videoStore.currentVideo) {
    videoStore.toggleFavorite(videoStore.currentVideo.id)
  }
}

function formatDuration(s) {
  const sec = Number(s)
  if (!sec || isNaN(sec)) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const r = Math.round(sec % 60)
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
  return `${m}:${String(r).padStart(2, '0')}`
}

function loadVideo() {
  const id = route.params.id
  if (id) videoStore.fetchVideo(id)
}

onMounted(loadVideo)
watch(() => route.params.id, loadVideo)
</script>

<style scoped>
.video-detail {
  max-width: 1000px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.player-area {
  aspect-ratio: 16 / 9;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.player-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-quaternary);
}
.player-placeholder span {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-tertiary);
}
.player-placeholder small {
  font-size: var(--text-sm);
  max-width: 400px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.video-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.video-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.3;
}

.video-meta {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.meta-chip {
  padding: var(--space-1) var(--space-3);
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
}

.video-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.video-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.btn {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  transition: all var(--ease-fast);
}
.btn-ghost {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}
.btn-ghost:hover { border-color: var(--border-strong); color: var(--text-primary); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-danger { background: rgba(239, 68, 68, 0.15); color: var(--color-error); border: 1px solid rgba(239, 68, 68, 0.2); }

.loading { display: flex; }
.skeleton-player {
  aspect-ratio: 16 / 9;
  width: 100%;
  border-radius: var(--radius-lg);
  background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12) 0;
  color: var(--text-quaternary);
}
.empty-state h3 { font-size: var(--text-xl); color: var(--text-tertiary); }
</style>
