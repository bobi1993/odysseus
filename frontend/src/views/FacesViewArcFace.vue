<template>
  <div class="faces-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <Users :size="24" />
          Faces & Performers
          <span class="badge badge-accent">ArcFace</span>
        </h1>
        <span class="page-subtitle">
          {{ facesStore.performerCount }} performers · {{ facesStore.totalFaces }} faces
          <template v-if="serviceStatus !== 'healthy'">
            <span class="service-badge degraded" title="Face service unreachable">
              ⚠ {{ serviceStatus }}
            </span>
          </template>
        </span>
      </div>
      <div class="header-actions">
        <button class="btn btn-ghost btn-sm" @click="showFaceSearch = true">
          <Upload :size="14" />
          Face Search
        </button>
        <button class="btn btn-ghost btn-sm" @click="facesStore.fetchPerformers()" :disabled="facesStore.loading">
          <RefreshCw :size="14" :class="{ 'animate-spin': facesStore.loading }" />
        </button>
        <button class="btn btn-primary" @click="startScan" :disabled="facesStore.scanning">
          <ScanLine :size="16" :class="{ 'animate-pulse': facesStore.scanning }" />
          {{ facesStore.scanning ? `Scanning (${scanProgress}%)` : 'Scan Library' }}
        </button>
      </div>
    </div>

    <!-- Scan Progress -->
    <div v-if="facesStore.scanning" class="scan-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: scanProgress + '%' }" />
      </div>
      <span class="progress-text">{{ scanStage }} — {{ scanProgress }}%</span>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-bar">
        <Search :size="16" />
        <input v-model="searchQuery" type="text" placeholder="Search performers..." @input="onSearch" />
      </div>
      <div class="toolbar-filters">
        <button v-for="f in filters" :key="f.id"
          class="filter-btn" :class="{ active: activeFilter === f.id }"
          @click="activeFilter = f.id; onFilterChange()">{{ f.label }}</button>
      </div>
      <select v-model="sortBy" @change="onFilterChange" class="sort-select">
        <option value="video_count">Most Videos</option>
        <option value="quality">Highest Quality</option>
        <option value="name">Name A-Z</option>
        <option value="created_at">Recently Added</option>
      </select>
    </div>

    <!-- Loading skeletons -->
    <div v-if="facesStore.loading && !facesStore.performers.length" class="loading-grid">
      <div v-for="i in 8" :key="i" class="skeleton-card glass">
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
        v-for="p in facesStore.performers" :key="p.id"
        :performer="p" @click="viewPerformer(p)"
        @favorite="facesStore.toggleFavorite(p.id)"
      />
    </div>

    <!-- Empty -->
    <div v-else class="empty-state">
      <Users :size="48" />
      <h3>No performers yet</h3>
      <p>Click "Scan Library" to analyze videos and cluster by face similarity.</p>
      <p class="empty-hint">Or use "Face Search" to find a performer from a photo.</p>
    </div>

    <!-- Pagination -->
    <div v-if="facesStore.hasMore" class="pagination">
      <button class="btn btn-ghost btn-sm" @click="facesStore.loadMore()" :disabled="facesStore.loading">
        {{ facesStore.loading ? 'Loading...' : 'Load More' }}
      </button>
    </div>

    <!-- Performer Detail Modal -->
    <PerformerProfileView
      v-if="selectedPerformer"
      :performer="selectedPerformer"
      @close="selectedPerformer = null"
      @update="onPerformerUpdate"
    />

    <!-- Face Search Modal -->
    <div v-if="showFaceSearch" class="modal-backdrop" @click.self="showFaceSearch = false">
      <div class="modal glass-strong face-search-modal">
        <div class="modal-header">
          <h2><Camera :size="20" /> Face Search</h2>
          <button class="modal-close" @click="showFaceSearch = false">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-desc">Upload a photo to find matching videos and performers.</p>
          <div class="upload-zone" :class="{ dragging: isDragging }"
            @dragenter.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @dragover.prevent
            @drop.prevent="onFileDrop"
            @click="$refs.fileInput.click()">
            <input ref="fileInput" type="file" accept="image/*" hidden @change="onFileSelect" />
            <Upload v-if="!faceSearchPreview" :size="32" />
            <img v-else :src="faceSearchPreview" class="face-preview" />
            <span>{{ faceSearchPreview ? 'Click to change' : 'Drop image or click to upload' }}</span>
          </div>

          <div v-if="faceSearchResults.length" class="face-search-results">
            <h4>Matches</h4>
            <div class="results-list">
              <div v-for="r in faceSearchResults" :key="r.performerId"
                class="result-item" @click="viewPerformerById(r.performerId)">
                <div class="result-avatar">
                  <img v-if="r.thumbnail" :src="r.thumbnail" />
                  <User v-else :size="24" />
                </div>
                <div class="result-info">
                  <span class="result-name">{{ r.name }}</span>
                  <span class="result-meta">{{ r.videoCount }} videos · {{ Math.round(r.similarity * 100) }}% match</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="faceSearchError" class="face-search-error">{{ faceSearchError }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Users, Search, RefreshCw, Upload, ScanLine, Camera, User } from 'lucide-vue-next'
import PerformerCard from '../components/PerformerCard.vue'
import PerformerProfileView from '../views/PerformerProfileView.vue'
import { useFacesStore } from '../stores/faces.js'

const facesStore = useFacesStore()
const searchQuery = ref('')
const activeFilter = ref('all')
const sortBy = ref('video_count')
const selectedPerformer = ref(null)
const showFaceSearch = ref(false)
const isDragging = ref(false)
const faceSearchPreview = ref('')
const faceSearchResults = ref([])
const faceSearchError = ref('')
const fileInput = ref(null)
const serviceStatus = ref('unknown')
const scanProgress = ref(0)
const scanStage = ref('')

const filters = [
  { id: 'all', label: 'All' },
  { id: 'favorite', label: '★ Favorites' },
  { id: 'high_quality', label: 'High Quality' },
]

let searchTimer = null

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => facesStore.searchFaces(searchQuery.value), 300)
}

function onFilterChange() {
  facesStore.setFilter(activeFilter.value, sortBy.value)
}

async function startScan() {
  scanProgress.value = 0
  scanStage.value = 'Starting...'
  await facesStore.triggerScan((stage, progress) => {
    scanStage.value = stage
    scanProgress.value = progress
  })
}

function viewPerformer(performer) { selectedPerformer.value = performer }
function viewPerformerById(id) {
  const p = facesStore.performers.find(p => p.id === id)
  if (p) { selectedPerformer.value = p; showFaceSearch.value = false }
}
function onPerformerUpdate(data) { facesStore.updatePerformer(data.id, data) }

async function onFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) await processFaceSearch(file)
}

async function onFileDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) await processFaceSearch(file)
}

async function processFaceSearch(file) {
  faceSearchError.value = ''
  faceSearchResults.value = []
  faceSearchPreview.value = URL.createObjectURL(file)
  try {
    faceSearchResults.value = await facesStore.searchByFace(file)
  } catch (err) {
    faceSearchError.value = err.message || 'Face search failed'
  }
}

onMounted(async () => {
  facesStore.fetchPerformers()
  try {
    const h = await facesStore.checkServiceHealth()
    serviceStatus.value = h?.modelLoaded ? 'healthy' : 'degraded'
  } catch { serviceStatus.value = 'unreachable' }
})
</script>

<style scoped>
.faces-view { display: flex; flex-direction: column; gap: var(--space-5); max-width: 1400px; margin: 0 auto; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); flex-wrap: wrap; }
.header-left { flex: 1; min-width: 200px; }
.header-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.page-title { display: flex; align-items: center; gap: var(--space-3); font-size: var(--text-2xl); font-weight: var(--font-bold); color: var(--text-primary); }
.page-title svg { color: var(--accent); }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.badge-accent { background: rgba(88,166,255,0.15); color: var(--accent); border: 1px solid rgba(88,166,255,0.3); }
.page-subtitle { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); color: var(--text-quaternary); margin-top: var(--space-1); }
.service-badge { padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
.service-badge.degraded { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid rgba(245,158,11,0.3); }
.scan-progress { display: flex; align-items: center; gap: var(--space-3); }
.progress-bar { flex: 1; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.3s ease; }
.progress-text { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; min-width: 120px; }
.toolbar { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; }
.search-bar { flex: 1; min-width: 200px; max-width: 400px; display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-4); background: var(--bg-tertiary); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); color: var(--text-quaternary); transition: border-color var(--ease-fast); }
.search-bar:focus-within { border-color: var(--accent); }
.search-bar input { flex: 1; background: transparent; border: none; outline: none; font-size: var(--text-sm); color: var(--text-primary); }
.search-bar input::placeholder { color: var(--text-quaternary); }
.toolbar-filters { display: flex; gap: var(--space-1); }
.filter-btn { padding: var(--space-1-5) var(--space-3); background: var(--bg-tertiary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); font-size: var(--text-xs); color: var(--text-tertiary); cursor: pointer; transition: all var(--ease-fast); }
.filter-btn:hover { border-color: var(--border-strong); }
.filter-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.sort-select { padding: var(--space-1-5) var(--space-3); background: var(--bg-tertiary); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); font-size: var(--text-xs); color: var(--text-secondary); outline: none; }
.performers-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--space-5); }
.loading-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: var(--space-5); }
.skeleton-card { overflow: hidden; }
.skeleton-thumb { aspect-ratio: 16/10; background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; }
.skeleton-meta { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.skeleton-line { height: 12px; border-radius: 6px; background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; }
.skeleton-line.w-60 { width: 60%; } .skeleton-line.w-40 { width: 40%; }
@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-3); padding: var(--space-12) 0; color: var(--text-quaternary); }
.empty-state h3 { font-size: var(--text-xl); color: var(--text-tertiary); }
.empty-hint { font-size: var(--text-xs); opacity: 0.7; }
.pagination { display: flex; justify-content: center; padding: var(--space-4) 0; }
.face-search-modal { max-width: 480px; }
.upload-zone { display: flex; flex-direction: column; align-items: center; gap: var(--space-3); padding: var(--space-8); border: 2px dashed var(--border-subtle); border-radius: var(--radius-lg); cursor: pointer; transition: all var(--ease-fast); color: var(--text-quaternary); }
.upload-zone:hover, .upload-zone.dragging { border-color: var(--accent); background: rgba(88,166,255,0.04); }
.upload-zone span { font-size: var(--text-sm); }
.face-preview { max-width: 200px; max-height: 200px; border-radius: var(--radius-md); object-fit: cover; }
.face-search-results { margin-top: var(--space-5); }
.face-search-results h4 { font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--text-secondary); margin-bottom: var(--space-3); }
.results-list { display: flex; flex-direction: column; gap: var(--space-2); }
.result-item { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-md); cursor: pointer; transition: background var(--ease-fast); }
.result-item:hover { background: var(--bg-tertiary); }
.result-avatar { width: 40px; height: 40px; border-radius: var(--radius-md); overflow: hidden; flex-shrink: 0; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center; color: var(--text-quaternary); }
.result-avatar img { width: 100%; height: 100%; object-fit: cover; }
.result-info { display: flex; flex-direction: column; gap: 2px; }
.result-name { font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--text-primary); }
.result-meta { font-size: 11px; color: var(--text-quaternary); }
.face-search-error { margin-top: var(--space-4); padding: var(--space-3); background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); border-radius: var(--radius-md); font-size: var(--text-sm); color: #ef4444; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal); padding: var(--space-6); }
.modal { width: 100%; max-width: 640px; max-height: 80vh; overflow-y: auto; display: flex; flex-direction: column; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: var(--space-5); border-bottom: 1px solid var(--border-subtle); }
.modal-header h2 { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--text-primary); }
.modal-close { width: 32px; height: 32px; border-radius: var(--radius-full); background: var(--bg-tertiary); color: var(--text-tertiary); font-size: 20px; display: flex; align-items: center; justify-content: center; transition: all var(--ease-fast); }
.modal-close:hover { background: var(--bg-glass-hover); color: var(--text-primary); }
.modal-body { padding: var(--space-5); display: flex; flex-direction: column; gap: var(--space-4); }
.modal-desc { font-size: var(--text-sm); color: var(--text-tertiary); }
.btn { padding: var(--space-2) var(--space-4); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: var(--font-medium); display: flex; align-items: center; gap: var(--space-2); transition: all var(--ease-fast); }
.btn-sm { padding: var(--space-1-5) var(--space-3); font-size: var(--text-xs); }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { opacity: 0.85; }
.btn-ghost { background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-subtle); }
.btn-ghost:hover { border-color: var(--border-strong); }
@media (max-width: 640px) { .page-header { flex-direction: column; } .toolbar { flex-direction: column; } .search-bar { max-width: 100%; } }
</style>
