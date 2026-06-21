<template>
  <div class="performer-card glass" @click="$emit('click', performer)" role="button" tabindex="0">
    <div class="card-media">
      <img
        v-if="performer.thumbnail || performer.face_thumbnail"
        :src="performer.thumbnail || performer.face_thumbnail"
        :alt="performer.name"
        @error="onImageError"
        loading="lazy"
      />
      <div v-else class="no-thumb">
        <User :size="32" />
      </div>
      <div class="card-overlay" />
      <div class="card-badges">
        <span v-if="performer.quality" class="quality-badge" :class="qualityClass">
          {{ qualityLabel }}
        </span>
        <span v-if="performer.video_count" class="count-badge">
          {{ performer.video_count }}
        </span>
      </div>
    </div>
    <div class="card-body">
      <h3 class="card-name">{{ performer.name || 'Unnamed Cluster' }}</h3>
      <div class="card-meta">
        <span v-if="performer.video_count" class="meta-item">
          <Film :size="12" />
          {{ performer.video_count }} videos
        </span>
        <span v-if="performer.detection_count" class="meta-item">
          <Eye :size="12" />
          {{ performer.detection_count }} faces
        </span>
      </div>
      <div v-if="performer.tags?.length" class="card-tags">
        <span v-for="tag in performer.tags.slice(0, 3)" :key="tag" class="card-tag">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { User, Film, Eye } from 'lucide-vue-next'

const props = defineProps({ performer: { type: Object, required: true } })
defineEmits(['click'])

function onImageError(e) {
  e.target.style.display = 'none'
}

const qualityClass = computed(() => {
  const q = props.performer.quality || 0
  if (q >= 0.7) return 'high'
  if (q >= 0.4) return 'medium'
  return 'low'
})

const qualityLabel = computed(() => {
  const q = props.performer.quality || 0
  if (q >= 0.7) return 'High'
  if (q >= 0.4) return 'Medium'
  return 'Low'
})
</script>

<style scoped>
.performer-card {
  overflow: hidden;
  cursor: pointer;
  transition: all var(--ease-normal);
}
.performer-card:hover {
  transform: translateY(-4px);
  border-color: var(--accent-border);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.card-media {
  position: relative;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  background: var(--bg-tertiary);
}
.card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--ease-slow);
}
.performer-card:hover .card-media img { transform: scale(1.05); }

.card-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 40%, rgba(0, 0, 0, 0.7) 100%);
}

.card-badges {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.quality-badge {
  padding: 3px 8px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  backdrop-filter: blur(4px);
}
.quality-badge.high { background: rgba(34, 197, 94, 0.9); color: #fff; }
.quality-badge.medium { background: rgba(245, 158, 11, 0.9); color: #fff; }
.quality-badge.low { background: rgba(239, 68, 68, 0.9); color: #fff; }

.count-badge {
  padding: 3px 10px;
  background: var(--accent);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-bold);
  color: #fff;
  text-align: center;
}

.no-thumb {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-quaternary);
}

.card-body {
  padding: var(--space-4);
}

.card-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.card-tags {
  display: flex;
  gap: var(--space-1-5);
  flex-wrap: wrap;
}
.card-tag {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
}
</style>
