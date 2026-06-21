<template>
  <div class="free-models-browser">
    <div class="browser-header">
      <h3 class="header-title">Free Models Browser</h3>
      <p class="header-subtitle">
        Browse and configure free models from multiple providers
      </p>
    </div>

    <div class="browser-controls">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search models, providers, or features..."
        class="search-input"
      />
      <select v-model="selectedApi" class="api-filter">
        <option value="">All Providers</option>
        <option v-for="api in allApis" :key="api" :value="api">
          {{ api }}
        </option>
      </select>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      Loading free models...
    </div>

    <div v-else-if="freeModelsData" class="categories-container">
      <div v-if="filteredCategories.length === 0" class="empty-state">
        <p>No models found matching your criteria</p>
      </div>

      <div v-else class="categories-grid">
        <div
          v-for="category in filteredCategories"
          :key="category.id"
          class="category-section"
        >
          <div class="category-header">
            <span class="category-icon">{{ category.icon }}</span>
            <div class="category-info">
              <h4 class="category-name">{{ category.name }}</h4>
              <p class="category-description">{{ category.description }}</p>
            </div>
            <span class="model-count">{{ category.models.length }}</span>
          </div>

          <div class="models-list">
            <div
              v-for="model in category.models"
              :key="model.id"
              class="model-card"
            >
              <div class="model-header">
                <div class="model-name-section">
                  <h5 class="model-name">{{ model.name }}</h5>
                  <span class="api-tag" :style="{ backgroundColor: getApiColor(model.api) }">
                    {{ model.api }}
                  </span>
                </div>
                <button class="btn btn-select" @click="selectModel(model)">
                  Select
                </button>
              </div>

              <div class="model-details">
                <div class="detail-row">
                  <span class="label">Provider:</span>
                  <span class="value">{{ model.provider }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Context:</span>
                  <span class="value">{{ formatContext(model.ctx) }}</span>
                </div>
                <div v-if="model.size" class="detail-row">
                  <span class="label">Size:</span>
                  <span class="value">{{ model.size }}</span>
                </div>
                <div class="detail-row">
                  <span class="label">Model ID:</span>
                  <code class="model-id">{{ model.id }}</code>
                </div>
                <div class="detail-row notes">
                  <span class="label">Notes:</span>
                  <span class="value">{{ model.notes }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="last-updated">
        Last updated: {{ freeModelsData.last_updated }}
      </div>
    </div>

    <div v-else class="error">
      <p>Failed to load free models</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface ModelData {
  id: string
  name: string
  provider: string
  ctx: number
  free: boolean
  api: string
  notes: string
  size?: string
}

interface CategoryData {
  id: string
  name: string
  icon: string
  description: string
  models: ModelData[]
}

interface FreeModelsData {
  last_updated: string
  categories: CategoryData[]
}

const loading = ref(false)
const freeModelsData = ref<FreeModelsData | null>(null)
const searchQuery = ref('')
const selectedApi = ref('')

const categories = computed(() => freeModelsData.value?.categories || [])

const allApis = computed(() => {
  const apis = new Set<string>()
  categories.value.forEach(cat => {
    cat.models.forEach(model => {
      apis.add(model.api)
    })
  })
  return Array.from(apis).sort()
})

const filteredCategories = computed(() => {
  const query = searchQuery.value.toLowerCase()
  const api = selectedApi.value

  return categories.value.map(cat => ({
    ...cat,
    models: cat.models.filter(model => {
      const matchesSearch = !query ||
        model.name.toLowerCase().includes(query) ||
        model.provider.toLowerCase().includes(query) ||
        model.notes.toLowerCase().includes(query)
      const matchesApi = !api || model.api === api
      return matchesSearch && matchesApi
    })
  })).filter(cat => cat.models.length > 0)
})

function formatContext(ctx: number): string {
  if (ctx >= 1000000) return `${(ctx / 1000000).toFixed(1)}M`
  if (ctx >= 1000) return `${(ctx / 1000).toFixed(0)}K`
  return `${ctx}`
}

function getApiColor(api: string): string {
  const colors: Record<string, string> = {
    openrouter: '#3B82F6',
    ollama: '#8B5CF6',
    gemini: '#EA4335',
    cloudflare: '#F97316',
    together: '#059669',
    huggingface: '#FFB800',
    perplexity: '#0EA5E9',
    fireworks: '#F59E0B',
    venice: '#EC4899',
  }
  return colors[api] || '#6B7280'
}

function selectModel(model: ModelData) {
  console.log('Selected model:', model)
  // TODO: Implement model selection logic
}

async function loadFreeModels() {
  loading.value = true
  try {
    const response = await fetch('/api/free-models')
    if (!response.ok) throw new Error('Failed to load free models')
    freeModelsData.value = await response.json()
  } catch (err: any) {
    console.error('Failed to load free models:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadFreeModels()
})
</script>

<style scoped>
.free-models-browser {
  padding: 16px;
}

.browser-header {
  margin-bottom: 24px;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.header-subtitle {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.browser-controls {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.search-input,
.api-filter {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
}

.search-input {
  flex: 1;
}

.api-filter {
  width: 200px;
}

.loading,
.error {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e5e7eb;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.categories-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #9ca3af;
}

.categories-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.category-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}

.category-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.category-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.category-info {
  flex: 1;
}

.category-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.category-description {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}

.model-count {
  background: #3b82f6;
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.models-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.model-card {
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  transition: all 0.2s ease;
}

.model-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.model-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.model-name-section {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  word-break: break-word;
}

.api-tag {
  padding: 2px 8px;
  border-radius: 12px;
  color: white;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.btn-select {
  padding: 4px 12px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-select:hover {
  background: #2563eb;
}

.model-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
}

.label {
  color: #6b7280;
  font-weight: 500;
  min-width: 70px;
  flex-shrink: 0;
}

.value {
  color: #1f2937;
  flex: 1;
  word-break: break-word;
}

.model-id {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 11px;
  color: #6b7280;
  word-break: break-all;
}

.detail-row.notes {
  padding-top: 8px;
  border-top: 1px solid #e5e7eb;
}

.last-updated {
  text-align: center;
  font-size: 11px;
  color: #6b7280;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}
</style>
