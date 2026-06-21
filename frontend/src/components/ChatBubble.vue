<template>
  <div class="chat-bubble" :class="role">
    <div class="bubble-avatar">
      <Bot v-if="role === 'assistant'" :size="16" />
      <User v-else :size="16" />
    </div>
    <div class="bubble-content">
      <div class="bubble-role">{{ role === 'user' ? 'You' : 'Assistant' }}</div>
      <div class="bubble-text" v-html="formattedContent" />
      <div v-if="streaming && role === 'assistant'" class="cursor-blink">▊</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Bot, User } from 'lucide-vue-next'

const props = defineProps({
  role: { type: String, default: 'user' },
  content: { type: String, default: '' },
  streaming: { type: Boolean, default: false },
})

const formattedContent = computed(() => {
  if (!props.content) return ''
  // Simple markdown-like formatting
  let text = props.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Code blocks
  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  // Inline code
  text = text.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  // Bold
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // Line breaks
  text = text.replace(/\n/g, '<br>')
  return text
})
</script>

<style scoped>
.chat-bubble {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  animation: fadeIn 0.2s ease;
}
.chat-bubble.user { flex-direction: row-reverse; }

.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.chat-bubble.user .bubble-avatar {
  background: var(--accent-soft);
  color: var(--accent);
}
.chat-bubble.assistant .bubble-avatar {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.bubble-content {
  max-width: 75%;
  min-width: 0;
}

.bubble-role {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-quaternary);
  margin-bottom: var(--space-1);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.chat-bubble.user .bubble-role { text-align: right; }

.bubble-text {
  background: var(--bg-tertiary);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  line-height: 1.6;
  color: var(--text-primary);
  word-wrap: break-word;
}
.chat-bubble.user .bubble-text {
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
}

:deep(.code-block) {
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  margin: var(--space-2) 0;
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
:deep(.inline-code) {
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.cursor-blink {
  display: inline-block;
  color: var(--accent);
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>
