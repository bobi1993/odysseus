<template>
  <div class="video-card glass" @click="$emit('click', video)">
    <div class="thumb-wrap">
      <img
        v-if="video.thumbnail_url"
        :src="video.thumbnail_url"
        :alt="video.title"
        loading="lazy"
        class="thumb-img"
      />
      <div v-else class="thumb-placeholder">
        <Film :size="32" />
      </div>

      <div class="thumb-overlay">
        <span class="play-icon">
          <Play :size="20" fill="currentColor" />
        </span>
      </div>

      <div v-if="video.duration" class="duration-badge">{{ formattedDuration }}</div>

      <button
        class="fav-btn"
        :class="{ active: isFavorite }"
        @click.stop="toggleFavorite"
        :aria-label="isFavorite ? 'Remove favorite' : 'Add favorite'"
      >
        <Heart :size="14" :fill="isFavorite ? 'currentColor' : 'none'" />
      </button>

      <div v-if="video.progress" class="progress-bar">
        <div class="progress-fill" :style="{ width: video.progress + '%' }" />
      </div>
    </div>

    <div class="card-meta">
      <h4 class="card-title">{{ video.title }}</h4>
      <div class="card-sub">
        <span v-if="video.source_type" class="source">{{ video.source_type }}</span>
        <span v-if="video.views" class="dot">·</span>
        <span v-if="video.views" class="views">{{ formatViews(video.views) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Play, Heart, Film } from 'lucide-vue-next'
import { useVideoStore } from '../stores/videos.js'

const props = defineProps({ video: { type: Object, required: true } })
defineEmits(['click'])

const videoStore = useVideoStore()
const isFavorite = computed(() => videoStore.favoriteIds.has(props.video.id))

function toggleFavorite() {
  videoStore.toggleFavorite(props.video.id)
}

const formattedDuration = computed(() => {
  const s = Number(props.video.duration)
  if (!s || isNaN(s)) return ''
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.round(s % 60)
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
})

function formatViews(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}
</script>

<style scoped>
.video-card {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: transform var(--ease-normal), box-shadow var(--ease-normal);
  overflow: hidden;
}
.video-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
}

.thumb-wrap {
  position: relative;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  background: var(--bg-tertiary);
}
.thumb-wrap::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04),
              inset 0 -40px 60px -30px rgba(0, 0, 0, 0.5);
  z-index: 1;
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform var(--ease-slow);
}
.video-card:hover .thumb-img { transform: scale(1.05); }

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-quaternary);
}

.thumb-overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, transparent 40%, rgba(0, 0, 0, 0.5) 100%);
  opacity: 0;
  transition: opacity var(--ease-normal);
  z-index: 2;
}
.video-card:hover .thumb-overlay { opacity: 1; }

.play-icon {
  width: 3rem;
  height: 3rem;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: #fff;
  display: grid;
  place-items: center;
  padding-left: 2px;
  transform: scale(0.8);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  transition: transform var(--ease-normal);
}
.video-card:hover .play-icon { transform: scale(1); }

.duration-badge {
  position: absolute;
  bottom: var(--space-2);
  right: var(--space-2);
  z-index: 2;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: #fff;
  background: rgba(0, 0, 0, 0.72);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.fav-btn {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-full);
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  display: grid;
  place-items: center;
  z-index: 3;
  opacity: 0;
  transition: opacity var(--ease-fast);
}
.video-card:hover .fav-btn { opacity: 1; }
.fav-btn:hover { background: rgba(0, 0, 0, 0.8); }
.fav-btn.active { opacity: 1; color: var(--color-error); }

.progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(255, 255, 255, 0.2);
  z-index: 2;
}
.progress-fill {
  height: 100%;
  background: var(--accent);
}

.card-meta {
  padding: var(--space-3) var(--space-2) 0;
}
.card-title {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  line-height: 1.4;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--ease-fast);
}
.video-card:hover .card-title { color: var(--accent); }

.card-sub {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1-5);
  font-size: var(--text-xs);
  color: var(--text-quaternary);
}
.source { text-transform: capitalize; }
.dot { color: var(--text-quaternary); }

@media (max-width: 640px) {
  .fav-btn { opacity: 1; }
  .thumb-overlay { display: none; }
}
</style>
