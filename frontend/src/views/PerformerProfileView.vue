<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal glass-strong performer-profile">
      <!-- Header -->
      <div class="modal-header">
        <h2>{{ performer.name }}</h2>
        <div class="header-actions">
          <button class="icon-btn" @click="toggleFavorite" :title="performer.favorite ? 'Remove from favorites' : 'Add to favorites'">
            <Heart :size="18" :fill="performer.favorite ? 'var(--red)' : 'none'" :color="performer.favorite ? 'var(--red)' : 'var(--text-tertiary)'" />
          </button>
          <button class="icon-btn" @click="$emit('close')">
            <X :size="18" />
          </button>
        </div>
      </div>

      <div class="modal-body">
        <!-- Hero section -->
        <div class="performer-hero">
          <div class="hero-avatar">
            <img v-if="performer.thumbnail" :src="performer.thumbnail" @error="onImageError" />
            <div v-else class="avatar-placeholder">
              <User :size="48" />
            </div>
          </div>
          <div class="hero-info">
            <h3>{{ performer.name }}</h3>
            <div class="hero-stats">
              <span class="stat"><strong>{{ performer.videoCount }}</strong> videos</span>
              <span class="stat"><strong>{{ performer.detectionCount }}</strong> faces</span>
              <span v-if="performer.quality" class="stat">
                <strong>{{ Math.round(performer.quality * 100) }}%</strong> quality
              </span>
              <span v-if="performer.gender" class="stat">{{ performer.gender }}</span>
            </div>
            <div v-if="performer.categories.length" class="hero-tags">
              <span v-for="cat in performer.categories" :key="cat" class="tag">{{ cat }}</span>
            </div>
            <div class="hero-actions">
              <button class="btn btn-primary btn-sm" @click="playAll">
                <Play :size="14" fill="currentColor" />
                Play All
              </button>
              <button class="btn btn-ghost btn-sm" @click="showEdit = !showEdit">
                <Pencil :size="14" />
                Edit
              </button>
            </div>
          </div>
        </div>

        <!-- Edit form -->
        <div v-if="showEdit" class="edit-section">
          <div class="form-group">
            <label>Name</label>
            <input v-model="editName" type="text" />
          </div>
          <div class="form-group">
            <label>Gender</label>
            <select v-model="editGender">
              <option value="">Unknown</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="non-binary">Non-binary</option>
            </select>
          </div>
          <div class="form-group">
            <label>Aliases (comma-separated)</label>
            <input v-model="editAliases" type="text" />
          </div>
          <div class="form-group">
            <label>Notes</label>
            <textarea v-model="editNotes" rows="3" />
          </div>
          <div class="form-actions">
            <button class="btn btn-primary btn-sm" @click="saveEdit">Save</button>
            <button class="btn btn-ghost btn-sm" @click="showEdit = false">Cancel</button>
          </div>
        </div>

        <!-- Stats overview -->
        <div class="stats-grid">
          <div class="stat-card">
            <Film :size="16" />
            <span class="stat-value">{{ performer.videoCount }}</span>
            <span class="stat-label">Videos</span>
          </div>
          <div class="stat-card">
            <Eye :size="16" />
            <span class="stat-value">{{ performer.detectionCount }}</span>
            <span class="stat-label">Face Detections</span>
          </div>
          <div class="stat-card">
            <Star :size="16" />
            <span class="stat-value">{{ performer.quality ? Math.round(performer.quality * 100) : — }}</span>
            <span class="stat-label">Avg Quality</span>
          </div>
          <div class="stat-card">
            <Clock :size="16" />
            <span class="stat-value">{{ firstSeenText }}</span>
            <span class="stat-label">First Seen</span>
          </div>
        </div>

        <!-- Projection types -->
        <div v-if="projectionTypes.length" class="subsection">
          <h4>Projection Types</h4>
          <div class="projection-badges">
            <span v-for="proj in projectionTypes" :key="proj" class="projection-badge">
              {{ formatProjection(proj) }}
            </span>
          </div>
        </div>

        <!-- Videos list -->
        <div class="subsection">
          <h4>Videos ({{ videos.length }})</h4>
          <div class="video-list">
            <div
              v-for="v in videos"
              :key="v.id"
              class="video-list-item"
              @click="playVideo(v)"
            >
              <div class="vli-thumb">
                <img v-if="v.thumbnail" :src="v.thumbnail" @error="onImageError" />
                <div v-else class="vli-placeholder"><Film :size="16" /></div>
              </div>
              <div class="vli-info">
                <span class="vli-title">{{ v.title || 'Untitled' }}</span>
                <span class="vli-meta">
                  {{ v.source || '' }} · {{ v.duration || '' }}
                  <template v-if="v.confidence">
                    · {{ Math.round(v.confidence * 100) }}% match
                  </template>
                </span>
              </div>
              <div class="vli-actions">
                <button class="icon-btn-sm" @click.stop="playVideo(v)">
                  <Play :size="14" />
                </button>
              </div>
            </div>
            <div v-if="!videos.length" class="no-videos">
              No videos associated with this performer.
            </div>
          </div>
        </div>

        <!-- Face gallery -->
        <div v-if="faceGallery.length" class="subsection">
          <h4>Face Gallery</h4>
          <div class="face-gallery">
            <div
              v-for="(face, i) in faceGallery"
              :key="i"
              class="face-thumb"
              :style="{ backgroundImage: `url(${face.thumbnail})` }"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  User, Play, Heart, X, Pencil, Film, Eye, Star, Clock,
} from 'lucide-vue-next'

const props = defineProps({
  performer: { type: Object, required: true },
})

const emit = defineEmits(['close', 'update'])

const showEdit = ref(false)
const editName = ref(props.performer.name)
const editGender = ref(props.performer.gender || '')
const editAliases = ref((props.performer.aliases || []).join(', '))
const editNotes = ref(props.performer.notes || '')

const videos = ref([])
const faceGallery = ref([])
const projectionTypes = ref([])

const firstSeenText = computed(() => {
  if (!props.performer.lastSeenAt) return '—'
  const d = new Date(props.performer.lastSeenAt)
  return d.toLocaleDateString()
})

function onImageError(e) {
  e.target.style.display = 'none'
}

function toggleFavorite() {
  emit('update', { id: props.performer.id, favorite: !props.performer.favorite })
}

function saveEdit() {
  emit('update', {
    id: props.performer.id,
    name: editName.value,
    gender: editGender.value || null,
    aliases: editAliases.value.split(',').map(s => s.trim()).filter(Boolean),
    notes: editNotes.value,
  })
  showEdit.value = false
}

function playAll() {
  if (videos.value.length) {
    playVideo(videos.value[0])
  }
}

function playVideo(video) {
  // Navigate to video detail — integrate with existing router
  window.dispatchEvent(new CustomEvent('play-video', { detail: video }))
}

function formatProjection(proj) {
  const labels = {
    '180_sbs': '180° SBS',
    '180_tb': '180° TB',
    '360_mono': '360° Mono',
    '360_sbs': '360° SBS',
    '360_tb': '360° TB',
    'flat': 'Flat',
    'fisheye': 'Fisheye',
  }
  return labels[proj] || proj
}

onMounted(async () => {
  // Load performer videos and face gallery
  // These would come from the API in production
  videos.value = props.performer.videos || []
  faceGallery.value = (props.performer.faceGallery || []).map(f => ({
    thumbnail: f,
  }))

  // Compute projection types from videos
  const projs = new Set()
  for (const v of videos.value) {
    if (v.projections) v.projections.forEach(p => projs.add(p))
  }
  projectionTypes.value = [...projs]
})
</script>

<style scoped>
.performer-profile {
  max-width: 720px;
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

.header-actions {
  display: flex;
  gap: var(--space-1);
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--ease-fast);
}
.icon-btn:hover { background: var(--bg-glass-hover); color: var(--text-primary); }

.icon-btn-sm {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-quaternary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--ease-fast);
}
.icon-btn-sm:hover { background: var(--bg-tertiary); color: var(--text-primary); }

.modal-body {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* Hero */
.performer-hero {
  display: flex;
  gap: var(--space-5);
}

.hero-avatar {
  width: 120px;
  height: 120px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-tertiary);
}
.hero-avatar img { width: 100%; height: 100%; object-fit: cover; }

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
.hero-stats strong { color: var(--text-primary); }

.hero-tags {
  display: flex;
  gap: var(--space-1-5);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.tag {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
}

.hero-actions { display: flex; gap: var(--space-2); }

/* Edit form */
.edit-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.form-group label {
  font-size: 11px;
  font-weight: var(--font-semibold);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.form-group input,
.form-group select,
.form-group textarea {
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-primary);
  outline: none;
}
.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  border-color: var(--accent);
}

.form-actions {
  display: flex;
  gap: var(--space-2);
}

/* Stats grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-4);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  color: var(--text-quaternary);
}
.stat-value {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}
.stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Subsections */
.subsection h4 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--space-3);
}

.projection-badges {
  display: flex;
  gap: var(--space-1-5);
  flex-wrap: wrap;
}
.projection-badge {
  padding: 3px 10px;
  background: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.2);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-medium);
  color: var(--accent);
}

/* Video list */
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
  cursor: pointer;
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
.vli-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-quaternary);
}

.vli-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.vli-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vli-meta { font-size: var(--text-xs); color: var(--text-quaternary); }

.no-videos {
  font-size: var(--text-sm);
  color: var(--text-quaternary);
  padding: var(--space-4);
  text-align: center;
}

/* Face gallery */
.face-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
  gap: var(--space-2);
}
.face-thumb {
  aspect-ratio: 1;
  border-radius: var(--radius-sm);
  background-size: cover;
  background-position: center;
  background-color: var(--bg-tertiary);
}

/* Buttons */
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
  .performer-hero { flex-direction: column; align-items: center; text-align: center; }
  .hero-stats { justify-content: center; }
  .hero-actions { justify-content: center; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
