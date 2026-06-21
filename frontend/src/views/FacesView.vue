<template>
  <div class="faces-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <Users :size="24" />
          Faces & Performers
        </h1>
        <span class="page-subtitle">Face-clustered performers from your video library</span>
      </div>
      <button class="btn btn-primary" @click="scan" :disabled="facesStore.scanning">
        <RotateCw :size="16" :class="{ 'animate-spin': facesStore.scanning }" />
        {{ facesStore.scanning ? 'Scanning...' : 'Scan Library' }}
      </button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-bar">
        <Search :size="16" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search performers..."
          @input="onSearch"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="facesStore.loading" class="loading-grid">
      <div v-for="i in 6" :key="i" class="skeleton-card glass">
        <div class="skeleton-thumb" />
        <div class="skeleton-meta">
          <div class="skeleton-line w-60" />
          <div class="skeleton-line w-40" />
        </div>
      </div>
    </div>

    <!-- Performers Grid -->
    <div v-else-if="facesStore.performers.length" class="performers-grid">
      <PerformerCard
        v-for="p in facesStore.performers"
        :key="p.id"
        :performer="p"
        @click="viewPerformer(p)"
      />
    </div>

    <!-- Empty -->
    <div v-else class="empty-state">
      <Users :size="48" />
      <h3>No performers yet</h3>
      <p>Click "Scan Library" to analyze video thumbnails and cluster by face similarity.</p>
    </div>

    <!-- Performer Detail Modal -->
    <div v-if="selectedPerformer" class="modal-backdrop" @click.self="selectedPerformer = null">
      <div class="modal glass-strong">
        <div class="modal-header">
          <h2>{{ selectedPerformer.name }}</h2>
          <button class="modal-close" @click="selectedPerformer = null">×</button>
        </div>
        <div class="modal-body">
          <div class="performer-hero">
            <div class="hero-avatar">
              <img
                v-if="selectedPerformer.thumbnail || selectedPerformer.face_thumbnail"
                :src="selectedPerformer.thumbnail || selectedPerformer.face_thumbnail"
                @error="onImageError"
              />
              <div v-else class="avatar-placeholder">
                <User :size="48" />
              </div>
            </div>
            <div class="hero-info">
              <h3>{{ selectedPerformer.name }}</h3>
              <div class="hero-stats">
                <span><strong>{{ selectedPerformer.video_count || 0 }}</strong> videos</span>
                <span v-if="selectedPerformer.detection_count"><strong>{{ selectedPerformer.detection_count }}</strong> faces</span>
                <span v-if="selectedPerformer.quality"><strong>{{ Math.round(selectedPerformer.quality * 100) }}%</strong> quality</span>
              </div>
              <div class="hero-actions">
                <button class="btn btn-primary btn-sm">
                  <Play :size="14" fill="currentColor" />
                  Play All
                </button>
                <button class="btn btn-ghost btn-sm">
                  <Heart :size="14" />
                  Favorite
                </button>
              </div>
            </div>
          </div>

          <h4 class="subsection-title">Videos</h4>
          <div class="video-list">
            <div
              v-for="(v, i) in (selectedPerformer.videos || [])"
              :key="i"
              class="video-list-item"
            >
              <div class="vli-thumb">
                <img v-if="v.thumbnail_url || v.thumbnail" :src="v.thumbnail_url || v.thumbnail" @error="onImageError" />
                <div v-else class="vli-placeholder"><Film :size="16" /></div>
              </div>
              <div class="vli-info">
                <span class="vli-title">{{ v.title || 'Untitled' }}</span>
                <span class="vli-meta">{{ v.source_type || '' }} · {{ v.duration || '' }}</span>
              </div>
            </div>
            <div v-if="!selectedPerformer.videos?.length" class="no-videos">
              No videos associated with this performer.
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  Users, Search, RotateCw, User, Play, Heart, Film,
} from 'lucide-vue-next'
import PerformerCard from '../components/PerformerCard.vue'
import { useFacesStore } from '../stores/faces.js'

const facesStore = useFacesStore()
const searchQuery = ref('')
const selectedPerformer = ref(null)

let searchTimer = null

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    facesStore.searchFaces(searchQuery.value)
  }, 300)
}

async function scan() {
  await facesStore.triggerScan()
}

async function viewPerformer(performer) {
  await facesStore.fetchPerformer(performer.id)
  selectedPerformer.value = facesStore.selectedPerformer
}

function onImageError(e) {
  e.target.style.display = 'none'
}

onMounted(() => {
  facesStore.fetchFaces()
})
</script>

<style scoped>
.faces-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.page-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}
.page-title svg { color: var(--accent); }
.page-subtitle {
  display: block;
  font-size: var(--text-sm);
  color: var(--text-quaternary);
  margin-top: var(--space-1);
}

.toolbar {
  display: flex;
  gap: var(--space-3);
}

.search-bar {
  flex: 1;
  max-width: 400px;
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

.performers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-5);
}

.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-5);
}
.skeleton-card { overflow: hidden; }
.skeleton-thumb {
  aspect-ratio: 16 / 10;
  background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-meta {
  padding: var(--space-4);
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
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-40 { width: 40%; }
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
.empty-state h3 { font-size: var(--text-xl); color: var(--text-tertiary); }

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  padding: var(--space-6);
}
.modal {
  width: 100%;
  max-width: 640px;
  max-height: 80vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.modal-header h2 {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}
.modal-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--ease-fast);
}
.modal-close:hover { background: var(--bg-glass-hover); color: var(--text-primary); }

.modal-body {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.performer-hero {
  display: flex;
  gap: var(--space-5);
}
.hero-avatar {
  width: 100px;
  height: 100px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-tertiary);
}
.hero-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-quaternary);
}
.hero-info { flex: 1; }
.hero-info h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.hero-stats {
  display: flex;
  gap: var(--space-4);
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}
.hero-actions { display: flex; gap: var(--space-2); }

.subsection-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.video-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.video-list-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  transition: background var(--ease-fast);
}
.video-list-item:hover { background: var(--bg-tertiary); }
.vli-thumb {
  width: 80px;
  height: 45px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-tertiary);
}
.vli-thumb img { width: 100%; height: 100%; object-fit: cover; }
.vli-placeholder { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: var(--text-quaternary); }
.vli-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.vli-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vli-meta { font-size: var(--text-xs); color: var(--text-quaternary); }
.no-videos { font-size: var(--text-sm); color: var(--text-quaternary); padding: var(--space-4); text-align: center; }

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
.btn-sm { padding: var(--space-1-5) var(--space-3); font-size: var(--text-xs); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { opacity: 0.85; }
.btn-ghost { background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-subtle); }
.btn-ghost:hover { border-color: var(--border-strong); }

@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .performer-hero { flex-direction: column; align-items: center; text-align: center; }
  .hero-stats { justify-content: center; }
  .hero-actions { justify-content: center; }
}
</style>
