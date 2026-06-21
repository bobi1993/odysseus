<template>
  <div class="settings-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <Settings :size="24" />
          Settings
        </h1>
        <span class="page-subtitle">Configure providers, models, and system preferences</span>
      </div>
    </div>

    <!-- LLM Providers Section -->
    <section class="settings-section glass">
      <h2 class="section-title">
        <Cpu :size="18" />
        LLM Providers
      </h2>

      <div v-if="chatStore.providers.length" class="provider-list">
        <div v-for="p in chatStore.providers" :key="p.id || p.name" class="provider-item">
          <div class="provider-info">
            <span class="provider-name">{{ p.name || p.id }}</span>
            <span class="provider-base">{{ p.base_url || p.url }}</span>
          </div>
          <div class="provider-actions">
            <span class="status-badge online">Active</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-hint">
        No providers configured. Add one below.
      </div>

      <!-- Add Provider Form -->
      <div class="add-form">
        <h3>Add Provider</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Name</label>
            <input v-model="newProvider.name" type="text" placeholder="e.g. OpenAI" />
          </div>
          <div class="form-group">
            <label>Base URL</label>
            <input v-model="newProvider.base_url" type="text" placeholder="https://api.openai.com/v1" />
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input v-model="newProvider.api_key" type="password" placeholder="sk-..." />
          </div>
          <div class="form-group">
            <label>Default Model</label>
            <input v-model="newProvider.model" type="text" placeholder="gpt-4o" />
          </div>
        </div>
        <button class="btn btn-primary btn-sm" @click="addProvider" :disabled="!newProvider.name || !newProvider.base_url">
          <Plus :size="14" />
          Add Provider
        </button>
      </div>
    </section>

    <!-- Models Section -->
    <section class="settings-section glass">
      <h2 class="section-title">
        <Braces :size="18" />
        Available Models
      </h2>

      <div v-if="chatStore.models.length" class="model-list">
        <div v-for="m in chatStore.models" :key="m.id || m.name" class="model-item">
          <div class="model-info">
            <span class="model-name">{{ m.name || m.id }}</span>
            <span class="model-provider">{{ m.provider || 'default' }}</span>
          </div>
          <span class="model-context" v-if="m.context_length">
            {{ formatContext(m.context_length) }} ctx
          </span>
        </div>
      </div>
      <div v-else class="empty-hint">
        No models loaded. Configure a provider first.
      </div>
    </section>

    <!-- Free Models Browser Section -->
    <section class="settings-section glass">
      <h2 class="section-title">
        <Braces :size="18" />
        Free Models Browser
      </h2>
      <FreeModelsBrowser />
    </section>

    <!-- System Info -->
    <section class="settings-section glass">
      <h2 class="section-title">
        <Info :size="18" />
        System Information
      </h2>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Backend Status</span>
          <span class="info-value" :class="systemStore.health?.status === 'ok' ? 'text-success' : 'text-error'">
            {{ systemStore.health?.status === 'ok' ? 'Online' : 'Offline' }}
          </span>
        </div>
        <div class="info-item">
          <span class="info-label">API Version</span>
          <span class="info-value">{{ systemStore.health?.version || 'N/A' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">CPU Usage</span>
          <span class="info-value">{{ systemStore.cpuPercent?.toFixed(0) || 0 }}%</span>
        </div>
        <div class="info-item">
          <span class="info-label">RAM Usage</span>
          <span class="info-value">{{ systemStore.ramPercent?.toFixed(0) || 0 }}%</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  Settings, Cpu, Braces, Info, Plus,
} from 'lucide-vue-next'
import { useChatStore } from '../stores/chat.js'
import { useSystemStore } from '../stores/system.js'
import api from '../api/client.js'
import FreeModelsBrowser from '../components/FreeModelsBrowser.vue'

const chatStore = useChatStore()
const systemStore = useSystemStore()

const newProvider = ref({
  name: '',
  base_url: '',
  api_key: '',
  model: '',
})

function formatContext(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

async function addProvider() {
  if (!newProvider.value.name || !newProvider.value.base_url) return
  try {
    await api.post('/llm/providers/', {
      name: newProvider.value.name,
      base_url: newProvider.value.base_url,
      api_key: newProvider.value.api_key || undefined,
      model: newProvider.value.model || undefined,
    })
    newProvider.value = { name: '', base_url: '', api_key: '', model: '' }
    await chatStore.fetchProviders()
    await chatStore.fetchModels()
  } catch (err) {
    alert('Failed to add provider: ' + (err.normalizedMessage || err.message))
  }
}

onMounted(() => {
  chatStore.fetchProviders()
  chatStore.fetchModels()
})
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
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

.settings-section {
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.section-title svg { color: var(--accent); }

.provider-list, .model-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.provider-item, .model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}

.provider-info, .model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.provider-name, .model-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}
.provider-base, .model-provider {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.status-badge {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.status-badge.online { background: rgba(34, 197, 94, 0.15); color: var(--color-success); }

.model-context {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
  font-variant-numeric: tabular-nums;
}

.empty-hint {
  font-size: var(--text-sm);
  color: var(--text-quaternary);
  padding: var(--space-4);
  text-align: center;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-subtle);
}

.add-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-subtle);
}
.add-form h3 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}
.form-group label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-quaternary);
}
.form-group input {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--ease-fast);
}
.form-group input:focus { border-color: var(--accent); }

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}
.info-label {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-quaternary);
}
.info-value {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}
.text-success { color: var(--color-success); }
.text-error { color: var(--color-error); }

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
.btn-primary:disabled { opacity: 0.3; cursor: not-allowed; }

@media (max-width: 640px) {
  .form-grid { grid-template-columns: 1fr; }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
