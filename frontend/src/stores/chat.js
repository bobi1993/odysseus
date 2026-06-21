import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client.js'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const loading = ref(false)
  const streaming = ref(false)
  const selectedProvider = ref('')
  const selectedModel = ref('')
  const providers = ref([])
  const models = ref([])
  const error = ref(null)

  const chatHistory = computed(() =>
    messages.value.filter(m => m.role === 'user' || m.role === 'assistant')
  )

  async function fetchProviders() {
    try {
      const { data } = await api.get('/llm/providers/')
      providers.value = data
      if (data.length && !selectedProvider.value) {
        selectedProvider.value = data[0].id || data[0].name
      }
    } catch (err) {
      error.value = err.normalizedMessage
    }
  }

  async function fetchModels() {
    try {
      const { data } = await api.get('/llm/models/')
      models.value = data
      if (data.length && !selectedModel.value) {
        selectedModel.value = data[0].id || data[0].name
      }
    } catch (err) {
      error.value = err.normalizedMessage
    }
  }

  async function sendMessage(content) {
    if (!content.trim()) return

    messages.value.push({ role: 'user', content })
    messages.value.push({ role: 'assistant', content: '' })
    loading.value = true
    streaming.value = true
    error.value = null

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messages.value.slice(0, -1),
          provider: selectedProvider.value,
          model: selectedModel.value,
        }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      const assistantMsg = messages.value[messages.value.length - 1]

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        assistantMsg.content += chunk
      }
    } catch (err) {
      error.value = err.message || 'Stream failed'
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === 'assistant') {
        lastMsg.content = '⚠️ Error: ' + error.value
      }
    } finally {
      loading.value = false
      streaming.value = false
    }
  }

  function clearChat() {
    messages.value = []
    error.value = null
  }

  return {
    messages, loading, streaming,
    selectedProvider, selectedModel,
    providers, models, error,
    chatHistory,
    fetchProviders, fetchModels,
    sendMessage, clearChat,
  }
})
