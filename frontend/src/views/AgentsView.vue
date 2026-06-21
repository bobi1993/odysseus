<template>
  <div class="agents-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <Bot :size="24" />
          Agents
        </h1>
        <span class="page-subtitle">AI agent registry and status</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-grid">
      <div v-for="i in 4" :key="i" class="skeleton-card glass">
        <div class="skeleton-line w-40" />
        <div class="skeleton-line w-60" />
        <div class="skeleton-line w-30" />
      </div>
    </div>

    <!-- Agent Grid -->
    <div v-else-if="agents.length" class="agents-grid">
      <div v-for="agent in agents" :key="agent.id" class="agent-card glass">
        <div class="agent-header">
          <div class="agent-icon">
            <Bot :size="20" />
          </div>
          <div class="agent-info">
            <h3 class="agent-name">{{ agent.name }}</h3>
            <span class="agent-type">{{ agent.type || 'worker' }}</span>
          </div>
          <span class="agent-status" :class="agent.status || 'idle'">
            {{ agent.status || 'idle' }}
          </span>
        </div>
        <p v-if="agent.description" class="agent-desc">{{ agent.description }}</p>
        <div class="agent-footer">
          <span v-if="agent.last_seen" class="agent-time">
            Last seen: {{ formatTime(agent.last_seen) }}
          </span>
          <span v-if="agent.task_count" class="agent-tasks">
            {{ agent.task_count }} tasks
          </span>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="empty-state">
      <Bot :size="48" />
      <h3>No agents registered</h3>
      <p>Agents will appear here when they connect to the platform.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Bot } from 'lucide-vue-next'
import api from '../api/client.js'

const agents = ref([])
const loading = ref(false)

function formatTime(ts) {
  if (!ts) return 'Never'
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return d.toLocaleDateString()
}

async function fetchAgents() {
  loading.value = true
  try {
    const { data } = await api.get('/agents/')
    agents.value = data
  } catch (err) {
    console.error('Failed to fetch agents:', err)
  } finally {
    loading.value = false
  }
}

onMounted(fetchAgents)
</script>

<style scoped>
.agents-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

.agent-card {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: all var(--ease-fast);
}
.agent-card:hover {
  border-color: var(--accent-border);
  transform: translateY(-2px);
}

.agent-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.agent-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.agent-info { flex: 1; min-width: 0; }
.agent-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent-type {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
  text-transform: capitalize;
}

.agent-status {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.agent-status.idle { background: rgba(255, 255, 255, 0.06); color: var(--text-quaternary); }
.agent-status.running { background: rgba(59, 130, 246, 0.15); color: var(--color-info); }
.agent-status.busy { background: rgba(245, 158, 11, 0.15); color: var(--color-warning); }
.agent-status.offline { background: rgba(239, 68, 68, 0.15); color: var(--color-error); }

.agent-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  line-height: 1.5;
}

.agent-footer {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-quaternary);
}

.loading-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}
.skeleton-card {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.skeleton-line {
  height: 14px;
  border-radius: 7px;
  background: linear-gradient(90deg, var(--bg-tertiary) 25%, rgba(255,255,255,0.04) 50%, var(--bg-tertiary) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-40 { width: 40%; }
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-30 { width: 30%; }
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
</style>
