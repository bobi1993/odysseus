<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-header">
      <router-link class="logo" to="/">
        <div class="logo-mark">
          <Zap :size="18" />
        </div>
        <span class="logo-text">Odysseus</span>
      </router-link>
      <button class="toggle-btn" @click="$emit('toggle')" title="Toggle sidebar">
        <PanelLeft :size="16" />
      </button>
    </div>

    <nav class="sidebar-nav">
      <div v-for="group in navGroups" :key="group.title" class="nav-section">
        <div class="nav-section-title">{{ group.title }}</div>
        <router-link
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to }"
        >
          <component :is="item.icon" class="nav-icon" :size="18" :stroke-width="2" />
          <span class="nav-label">{{ item.label }}</span>
          <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
        </router-link>
      </div>
    </nav>

    <div class="sidebar-footer">
      <span class="version-pill">v1.0</span>
    </div>
  </aside>
</template>

<script setup>
import { computed, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import {
  LayoutDashboard, MessageSquare, Video, Users, ListTodo,
  Bot, Settings, Zap, PanelLeft,
} from 'lucide-vue-next'

defineProps({ collapsed: Boolean })
defineEmits(['toggle'])
const route = useRoute()

const navGroups = [
  {
    title: 'Main',
    items: [
      { label: 'Dashboard', to: '/', icon: markRaw(LayoutDashboard) },
      { label: 'Chat', to: '/chat', icon: markRaw(MessageSquare) },
    ],
  },
  {
    title: 'Library',
    items: [
      { label: 'Videos', to: '/videos', icon: markRaw(Video) },
      { label: 'Faces', to: '/faces', icon: markRaw(Users) },
    ],
  },
  {
    title: 'System',
    items: [
      { label: 'Tasks', to: '/tasks', icon: markRaw(ListTodo) },
      { label: 'Agents', to: '/agents', icon: markRaw(Bot) },
      { label: 'Settings', to: '/settings', icon: markRaw(Settings) },
    ],
  },
]
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-glass);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-right: 1px solid var(--border-subtle);
  transition: width var(--ease-slow);
  z-index: var(--z-sidebar);
}
.sidebar.collapsed { width: var(--sidebar-collapsed-w); }

.sidebar-header {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  flex-shrink: 0;
}
.logo-mark {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  border-radius: var(--radius-md);
  color: var(--accent);
  flex-shrink: 0;
}
.logo-text {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  white-space: nowrap;
  letter-spacing: -0.02em;
}
.sidebar.collapsed .logo-text { display: none; }

.toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: all var(--ease-fast);
  margin-left: auto;
  flex-shrink: 0;
}
.toggle-btn:hover { background: var(--bg-tertiary); color: var(--text-secondary); }
.sidebar.collapsed .toggle-btn { margin: 0 auto; }

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-4) var(--space-2);
  scrollbar-width: none;
}
.sidebar-nav::-webkit-scrollbar { display: none; }

.nav-section { margin-bottom: var(--space-6); }
.nav-section-title {
  font-size: 10px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-quaternary);
  padding: 0 var(--space-3);
  margin-bottom: var(--space-2);
}
.sidebar.collapsed .nav-section-title { display: none; }

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  transition: all var(--ease-fast);
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  text-decoration: none;
}
.nav-link:hover { background: var(--bg-tertiary); color: var(--text-primary); }
.nav-link.active { background: var(--accent-soft); color: var(--accent); }
.nav-link.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
}
.nav-icon { flex-shrink: 0; opacity: 0.6; }
.nav-link.active .nav-icon { opacity: 1; }
.sidebar.collapsed .nav-label { display: none; }
.sidebar.collapsed .nav-link { justify-content: center; padding: var(--space-2); }

.nav-badge {
  margin-left: auto;
  padding: 1px 6px;
  background: var(--accent);
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  color: #fff;
}

.sidebar-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.version-pill {
  font-size: 10px;
  font-weight: var(--font-medium);
  color: var(--text-quaternary);
  padding: var(--space-1) var(--space-2);
}
.sidebar.collapsed .version-pill { display: none; }
</style>
