<template>
  <div class="chat-view">
    <!-- Header -->
    <div class="chat-header">
      <div class="model-selectors">
        <div class="select-group">
          <label>Provider</label>
          <select v-model="chatStore.selectedProvider" class="glass-select">
            <option v-for="p in chatStore.providers" :key="p.id || p.name" :value="p.id || p.name">
              {{ p.name || p.id }}
            </option>
            <option v-if="!chatStore.providers.length" value="">Default</option>
          </select>
        </div>
        <div class="select-group">
          <label>Model</label>
          <select v-model="chatStore.selectedModel" class="glass-select">
            <option v-for="m in chatStore.models" :key="m.id || m.name" :value="m.id || m.name">
              {{ m.name || m.id }}
            </option>
            <option v-if="!chatStore.models.length" value="">Default</option>
          </select>
        </div>
      </div>
      <button class="btn btn-ghost btn-sm" @click="chatStore.clearChat()">
        <Trash2 :size="14" />
        Clear
      </button>
    </div>

    <!-- Messages -->
    <div class="chat-messages" ref="messagesEl">
      <div v-if="!chatStore.chatHistory.length" class="chat-empty">
        <MessageSquare :size="48" />
        <h3>Start a conversation</h3>
        <p>Send a message to begin chatting with the AI assistant.</p>
      </div>

      <ChatBubble
        v-for="(msg, i) in chatStore.chatHistory"
        :key="i"
        :role="msg.role"
        :content="msg.content"
        :streaming="msg.role === 'assistant' && i === chatStore.chatHistory.length - 1 && chatStore.streaming"
      />

      <div v-if="chatStore.loading && !chatStore.streaming" class="chat-loading">
        <div class="typing-indicator">
          <span /><span /><span />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="chatStore.error" class="chat-error">
      <AlertCircle :size="14" />
      {{ chatStore.error }}
    </div>

    <!-- Input -->
    <div class="chat-input-area">
      <div class="input-wrapper glass">
        <textarea
          v-model="inputText"
          ref="inputEl"
          placeholder="Type your message..."
          @keydown.enter.exact.prevent="send"
          :disabled="chatStore.loading"
          rows="1"
        />
        <button
          class="send-btn"
          :disabled="!inputText.trim() || chatStore.loading"
          @click="send"
        >
          <Send :size="18" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import {
  Trash2, MessageSquare, AlertCircle, Send,
} from 'lucide-vue-next'
import ChatBubble from '../components/ChatBubble.vue'
import { useChatStore } from '../stores/chat.js'

const chatStore = useChatStore()
const inputText = ref('')
const inputEl = ref(null)
const messagesEl = ref(null)

onMounted(() => {
  chatStore.fetchProviders()
  chatStore.fetchModels()
})

watch(() => chatStore.chatHistory.length, async () => {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
})

async function send() {
  if (!inputText.value.trim() || chatStore.loading) return
  const text = inputText.value.trim()
  inputText.value = ''
  await chatStore.sendMessage(text)
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 900px;
  margin: 0 auto;
  gap: var(--space-4);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-shrink: 0;
}

.model-selectors {
  display: flex;
  gap: var(--space-3);
}
.select-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.select-group label {
  font-size: 10px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-quaternary);
}
.glass-select {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
  min-width: 140px;
  transition: border-color var(--ease-fast);
}
.glass-select:focus { border-color: var(--accent); }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 0;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  color: var(--text-quaternary);
}
.chat-empty h3 {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-tertiary);
}
.chat-empty p { font-size: var(--text-sm); }

.chat-loading {
  padding: var(--space-4);
}
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: var(--space-2) 0;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-quaternary);
  animation: bounce 1.4s infinite ease-in-out;
}
.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.chat-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-error);
  flex-shrink: 0;
}

.chat-input-area {
  flex-shrink: 0;
  padding-bottom: var(--space-2);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
  padding: var(--space-3);
  gap: var(--space-2);
}
.input-wrapper textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  font-size: var(--text-sm);
  line-height: 1.5;
  max-height: 120px;
  min-height: 24px;
  color: var(--text-primary);
}
.input-wrapper textarea::placeholder { color: var(--text-quaternary); }

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--ease-fast);
}
.send-btn:hover:not(:disabled) { opacity: 0.85; transform: scale(1.05); }
.send-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.btn-sm {
  padding: var(--space-1-5) var(--space-3);
  font-size: var(--text-xs);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  font-weight: var(--font-medium);
}
.btn-ghost {
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  border: 1px solid var(--border-subtle);
}
.btn-ghost:hover { color: var(--text-primary); border-color: var(--border-strong); }

@media (max-width: 640px) {
  .model-selectors { flex-direction: column; gap: var(--space-2); }
  .glass-select { min-width: 100%; }
}
</style>
