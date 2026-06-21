<template>
  <div class="tasks-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <ListTodo :size="24" />
          Tasks
        </h1>
        <span class="page-subtitle">Manage and dispatch background tasks</span>
      </div>
      <button class="btn btn-primary" @click="showCreate = !showCreate">
        <Plus :size="16" />
        New Task
      </button>
    </div>

    <!-- Create Task Form -->
    <div v-if="showCreate" class="create-form glass">
      <h3>Create Task</h3>
      <div class="form-grid">
        <div class="form-group">
          <label>Title</label>
          <input v-model="newTask.title" type="text" placeholder="Task title..." />
        </div>
        <div class="form-group">
          <label>Type</label>
          <select v-model="newTask.task_type" class="glass-select">
            <option value="scrape">Scrape</option>
            <option value="transcode">Transcode</option>
            <option value="scan">Face Scan</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        <div class="form-group form-group-wide">
          <label>Description</label>
          <input v-model="newTask.description" type="text" placeholder="Optional description..." />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost btn-sm" @click="showCreate = false">Cancel</button>
        <button class="btn btn-primary btn-sm" @click="createTask" :disabled="!newTask.title">
          Create
        </button>
      </div>
    </div>

    <!-- Status Tabs -->
    <div class="status-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span class="tab-count">{{ tabCount(tab.key) }}</span>
      </button>
    </div>

    <!-- Task List -->
    <div v-if="filteredTasks.length" class="task-list">
      <TaskItem
        v-for="task in filteredTasks"
        :key="task.id"
        :task="task"
        @dispatch="onDispatch"
        @complete="onComplete"
      />
    </div>

    <!-- Empty -->
    <div v-else class="empty-state">
      <ListTodo :size="48" />
      <h3>No {{ activeTab }} tasks</h3>
      <p>Create a new task to get started.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ListTodo, Plus } from 'lucide-vue-next'
import TaskItem from '../components/TaskItem.vue'
import { useTaskStore } from '../stores/tasks.js'

const taskStore = useTaskStore()
const showCreate = ref(false)
const activeTab = ref('all')
const newTask = ref({ title: '', task_type: 'scrape', description: '' })

const tabs = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'running', label: 'Running' },
  { key: 'completed', label: 'Completed' },
  { key: 'failed', label: 'Failed' },
]

const filteredTasks = computed(() => {
  if (activeTab.value === 'all') return taskStore.tasks
  return taskStore.tasks.filter(t => t.status === activeTab.value)
})

function tabCount(key) {
  if (key === 'all') return taskStore.tasks.length
  return taskStore.tasks.filter(t => t.status === key).length
}

async function createTask() {
  if (!newTask.value.title) return
  await taskStore.createTask(newTask.value)
  newTask.value = { title: '', task_type: 'scrape', description: '' }
  showCreate.value = false
}

async function onDispatch(id) {
  await taskStore.dispatchTask(id)
}

async function onComplete(id) {
  await taskStore.completeTask(id)
}

onMounted(() => {
  taskStore.fetchTasks()
})
</script>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
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

.create-form {
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.create-form h3 {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}
.form-group-wide { grid-column: 1 / -1; }
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
.glass-select {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-primary);
  outline: none;
  cursor: pointer;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.status-tabs {
  display: flex;
  gap: var(--space-1);
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: var(--space-1);
}
.tab-btn {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-quaternary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  transition: all var(--ease-fast);
}
.tab-btn:hover { background: var(--bg-tertiary); color: var(--text-secondary); }
.tab-btn.active { background: var(--accent-soft); color: var(--accent); }
.tab-count {
  padding: 1px 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-full);
  font-size: 10px;
  font-weight: var(--font-bold);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
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
.btn-ghost { background: var(--bg-tertiary); color: var(--text-secondary); border: 1px solid var(--border-subtle); }
.btn-ghost:hover { border-color: var(--border-strong); }

@media (max-width: 640px) {
  .page-header { flex-direction: column; }
  .form-grid { grid-template-columns: 1fr; }
}
</style>
