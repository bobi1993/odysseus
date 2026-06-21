<template>
  <div class="task-item glass" :class="'status-' + task.status">
    <div class="task-header">
      <div class="task-status-icon">
        <Clock v-if="task.status === 'pending'" :size="14" />
        <Loader v-else-if="task.status === 'running'" :size="14" class="animate-spin" />
        <CheckCircle v-else-if="task.status === 'completed'" :size="14" />
        <XCircle v-else-if="task.status === 'failed'" :size="14" />
      </div>
      <div class="task-info">
        <h4 class="task-title">{{ task.title || task.name || 'Untitled Task' }}</h4>
        <span class="task-type">{{ task.type || task.task_type || 'task' }}</span>
      </div>
      <span class="task-status-badge" :class="task.status">{{ task.status }}</span>
    </div>

    <p v-if="task.description" class="task-desc">{{ task.description }}</p>

    <div v-if="task.result" class="task-result">
      <div class="result-label">Result:</div>
      <pre class="result-content">{{ typeof task.result === 'object' ? JSON.stringify(task.result, null, 2) : task.result }}</pre>
    </div>

    <div class="task-footer">
      <span class="task-time">{{ formatTime(task.created_at || task.updated_at) }}</span>
      <div class="task-actions">
        <button
          v-if="task.status === 'pending'"
          class="btn btn-sm btn-primary"
          @click="$emit('dispatch', task.id)"
        >
          <Play :size="12" />
          Dispatch
        </button>
        <button
          v-if="task.status === 'running'"
          class="btn btn-sm btn-success"
          @click="$emit('complete', task.id)"
        >
          <CheckCircle :size="12" />
          Complete
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Clock, Loader, CheckCircle, XCircle, Play } from 'lucide-vue-next'

defineProps({ task: { type: Object, required: true } })
defineEmits(['dispatch', 'complete'])

function formatTime(ts) {
  if (!ts) return ''
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
</script>

<style scoped>
.task-item {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  transition: all var(--ease-fast);
}
.task-item:hover {
  border-color: var(--accent-border);
}

.task-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.task-status-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.status-pending .task-status-icon { background: rgba(255, 255, 255, 0.06); color: var(--text-quaternary); }
.status-running .task-status-icon { background: rgba(59, 130, 246, 0.15); color: var(--color-info); }
.status-completed .task-status-icon { background: rgba(34, 197, 94, 0.15); color: var(--color-success); }
.status-failed .task-status-icon { background: rgba(239, 68, 68, 0.15); color: var(--color-error); }

.task-info { flex: 1; min-width: 0; }
.task-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-type {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
  text-transform: capitalize;
}

.task-status-badge {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.task-status-badge.pending { background: rgba(255, 255, 255, 0.06); color: var(--text-quaternary); }
.task-status-badge.running { background: rgba(59, 130, 246, 0.15); color: var(--color-info); }
.task-status-badge.completed { background: rgba(34, 197, 94, 0.15); color: var(--color-success); }
.task-status-badge.failed { background: rgba(239, 68, 68, 0.15); color: var(--color-error); }

.task-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  line-height: 1.5;
}

.task-result {
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.result-label {
  font-size: 10px;
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-quaternary);
  margin-bottom: var(--space-2);
}
.result-content {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}

.task-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.task-time {
  font-size: var(--text-xs);
  color: var(--text-quaternary);
}
.task-actions { display: flex; gap: var(--space-2); }

.btn-sm {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: var(--font-medium);
  transition: all var(--ease-fast);
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover { opacity: 0.85; }
.btn-success { background: var(--color-success); color: #fff; }
.btn-success:hover { opacity: 0.85; }
</style>
