<template>
  <div class="system-stats">
    <!-- CPU -->
    <div class="stat-card glass">
      <div class="stat-header">
        <Cpu :size="16" class="stat-icon" />
        <span class="stat-label">CPU</span>
      </div>
      <div class="stat-value">{{ cpuPercent }}%</div>
      <div class="stat-bar">
        <div class="stat-bar-fill" :style="{ width: cpuPercent + '%' }" :class="barClass(cpuPercent)" />
      </div>
    </div>

    <!-- RAM -->
    <div class="stat-card glass">
      <div class="stat-header">
        <MemoryStick :size="16" class="stat-icon" />
        <span class="stat-label">RAM</span>
      </div>
      <div class="stat-value">{{ ramUsed }} / {{ ramTotal }} GB</div>
      <div class="stat-bar">
        <div class="stat-bar-fill" :style="{ width: ramPercent + '%' }" :class="barClass(ramPercent)" />
      </div>
    </div>

    <!-- Disk -->
    <div class="stat-card glass">
      <div class="stat-header">
        <HardDrive :size="16" class="stat-icon" />
        <span class="stat-label">Disk</span>
      </div>
      <div class="stat-value">{{ diskUsed }} / {{ diskTotal }} GB</div>
      <div class="stat-bar">
        <div class="stat-bar-fill" :style="{ width: diskPercent + '%' }" :class="barClass(diskPercent)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Cpu, MemoryStick, HardDrive } from 'lucide-vue-next'
import { useSystemStore } from '../stores/system.js'

const store = useSystemStore()

const cpuPercent = computed(() => Math.round(store.cpuPercent))
const ramPercent = computed(() => Math.round(store.ramPercent))
const diskPercent = computed(() => Math.round(store.diskPercent))
const ramUsed = computed(() => store.ramUsed?.toFixed(1) || '0')
const ramTotal = computed(() => store.ramTotal?.toFixed(1) || '0')
const diskUsed = computed(() => store.diskUsed?.toFixed(1) || '0')
const diskTotal = computed(() => store.diskTotal?.toFixed(1) || '0')

function barClass(pct) {
  if (pct >= 90) return 'danger'
  if (pct >= 70) return 'warning'
  return 'ok'
}
</script>

<style scoped>
.system-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.stat-card {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.stat-icon { color: var(--accent); opacity: 0.8; }

.stat-value {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.stat-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-full);
  overflow: hidden;
}
.stat-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.5s ease;
}
.stat-bar-fill.ok { background: var(--accent); }
.stat-bar-fill.warning { background: var(--color-warning); }
.stat-bar-fill.danger { background: var(--color-error); }

@media (max-width: 768px) {
  .system-stats { grid-template-columns: 1fr; }
}
</style>
