<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <NavBar :collapsed="collapsed" @toggle="collapsed = !collapsed" />

    <!-- Main content -->
    <div class="main-content">
      <header class="topbar">
        <button class="mobile-toggle" @click="collapsed = !collapsed">
          <Menu :size="20" />
        </button>
        <div class="topbar-title">
          <h2>{{ route.name }}</h2>
        </div>
        <div class="topbar-actions">
          <div class="conn-badge" :class="connClass">
            <span class="conn-dot" />
            <span class="conn-text">{{ connText }}</span>
          </div>
        </div>
      </header>

      <main class="page-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Menu } from 'lucide-vue-next'
import NavBar from './components/NavBar.vue'
import { useSystemStore } from './stores/system.js'

const route = useRoute()
const collapsed = ref(false)
const systemStore = useSystemStore()

const connClass = computed(() => {
  const s = systemStore.health?.status
  return s === 'ok' ? 'online' : s === 'error' ? 'offline' : 'warning'
})
const connText = computed(() => {
  const s = systemStore.health?.status
  return s === 'ok' ? 'Connected' : s === 'error' ? 'Offline' : 'Checking...'
})

function handleResize() {
  if (window.innerWidth < 1024) collapsed.value = true
}

onMounted(() => {
  systemStore.fetchHealth()
  systemStore.fetchResources()
  handleResize()
  window.addEventListener('resize', handleResize)
  const timer = setInterval(() => {
    systemStore.fetchHealth()
    systemStore.fetchResources()
  }, 30000)
  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    clearInterval(timer)
  })
})
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.topbar {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-6);
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
  z-index: var(--z-topbar);
}

.mobile-toggle {
  display: none;
  color: var(--text-secondary);
  padding: var(--space-2);
  border-radius: var(--radius-md);
}
.mobile-toggle:hover {
  background: var(--bg-tertiary);
}

.topbar-title h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.topbar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.conn-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1-5) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}
.conn-badge.online { background: rgba(34, 197, 94, 0.1); color: var(--color-success); }
.conn-badge.offline { background: rgba(239, 68, 68, 0.1); color: var(--color-error); }
.conn-badge.warning { background: rgba(245, 158, 11, 0.1); color: var(--color-warning); }
.conn-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.conn-badge.online .conn-dot { background: var(--color-success); box-shadow: 0 0 6px var(--color-success); }
.conn-badge.offline .conn-dot { background: var(--color-error); }
.conn-badge.warning .conn-dot { background: var(--color-warning); animation: pulse 1.5s infinite; }

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}

/* Page transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 1024px) {
  .mobile-toggle { display: flex; }
}
</style>
