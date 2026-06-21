<template>
  <div class="dashboard">
    <!-- System Stats -->
    <section class="section">
      <h2 class="section-title">
        <Activity :size="18" />
        System Resources
      </h2>
      <SystemStats />
    </section>

    <!-- Quick Actions -->
    <section class="section">
      <h2 class="section-title">
        <Zap :size="18" />
        Quick Actions
      </h2>
      <div class="action-grid">
        <router-link to="/chat" class="action-card glass">
          <MessageSquare :size="24" />
          <span>New Chat</span>
        </router-link>
        <router-link to="/videos" class="action-card glass">
          <Video :size="24" />
          <span>Browse Videos</span>
        </router-link>
        <router-link to="/faces" class="action-card glass">
          <Users :size="24" />
          <span>Scan Faces</span>
        </router-link>
        <router-link to="/tasks" class="action-card glass">
          <ListTodo :size="24" />
          <span>View Tasks</span>
        </router-link>
      </div>
    </section>

    <!-- Health -->
    <section class="section">
      <h2 class="section-title">
        <Heart :size="18" />
        Service Health
      </h2>
      <div class="health-grid">
        <div class="health-card glass">
          <div class="health-label">Backend</div>
          <div class="health-status" :class="healthClass">
            <span class="status-dot" :class="healthClass" />
            {{ healthText }}
          </div>
        </div>
        <div class="health-card glass">
          <div class="health-label">LLM Providers</div>
          <div class="health-status online">
            <span class="status-dot online" />
            {{ providerCount }} configured
          </div>
        </div>
        <div class="health-card glass">
          <div class="health-label">Videos</div>
          <div class="health-status online">
            <span class="status-dot online" />
            Library ready
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import {
  Activity, Zap, MessageSquare, Video, Users, ListTodo, Heart,
} from 'lucide-vue-next'
import SystemStats from '../components/SystemStats.vue'
import { useSystemStore } from '../stores/system.js'
import { useChatStore } from '../stores/chat.js'

const systemStore = useSystemStore()
const chatStore = useChatStore()

const healthClass = computed(() => {
  const s = systemStore.health?.status
  return s === 'ok' ? 'online' : 'offline'
})
const healthText = computed(() => {
  const s = systemStore.health?.status
  return s === 'ok' ? 'Operational' : 'Unavailable'
})
const providerCount = computed(() => chatStore.providers.length)

onMounted(() => {
  chatStore.fetchProviders()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  max-width: 1200px;
  margin: 0 auto;
}

.section {
  animation: fadeIn 0.4s ease;
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-4);
}
.section-title svg { color: var(--accent); }

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all var(--ease-fast);
}
.action-card:hover {
  color: var(--accent);
  border-color: var(--accent-border);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
.action-card svg { opacity: 0.7; }
.action-card span {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.health-card {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.health-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-quaternary);
}
.health-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}
.health-status.online { color: var(--color-success); }
.health-status.offline { color: var(--color-error); }

@media (max-width: 768px) {
  .action-grid { grid-template-columns: repeat(2, 1fr); }
  .health-grid { grid-template-columns: 1fr; }
}
</style>
