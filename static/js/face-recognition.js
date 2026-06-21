// static/js/face-recognition.js
// Face Recognition Dashboard — connects to VR Video backend API

(function() {
  'use strict';

  const API_BASE = '';  // same origin
  let _scanInProgress = false;

  // ─── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Tab click handler
    const tab = document.querySelector('[data-settings-tab="faces"]');
    if (tab) {
      tab.addEventListener('click', () => { showPanel('faces'); loadStatus(); });
    }

    // Also handle go-settings-tab links
    document.addEventListener('click', (e) => {
      const link = e.target.closest('[data-go-settings-tab="faces"]');
      if (link) { e.preventDefault(); showPanel('faces'); loadStatus(); }
    });

    // Button handlers
    const scanBtn = document.getElementById('face-scan-all-btn');
    if (scanBtn) scanBtn.addEventListener('click', startScan);

    const refreshBtn = document.getElementById('face-refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => { loadStatus(); });

    const clearBtn = document.getElementById('face-clear-offline-btn');
    if (clearBtn) clearBtn.addEventListener('click', clearOffline);

    // Config sliders
    ['ssd-conf', 'min-size', 'thresh-high', 'thresh-low'].forEach(id => {
      const el = document.getElementById('face-config-' + id);
      if (el) {
        el.addEventListener('input', () => {
          const val = document.getElementById('face-config-' + id + '-val');
          if (val) val.textContent = el.value;
        });
      }
    });

    const saveConfig = document.getElementById('face-config-save');
    if (saveConfig) saveConfig.addEventListener('click', saveConfiguration);
  }

  function showPanel(name) {
    document.querySelectorAll('.settings-nav-item[data-settings-tab]').forEach(t => {
      t.classList.toggle('active', t.dataset.settingsTab === name);
    });
    document.querySelectorAll('[data-settings-panel]').forEach(p => {
      p.classList.toggle('hidden', p.dataset.settingsPanel !== name);
    });
  }

  // ─── API Calls ──────────────────────────────────────────────────────────────

  async function apiGet(path) {
    try {
      const r = await fetch(API_BASE + path, { credentials: 'same-origin' });
      if (r.ok) return await r.json();
    } catch (e) { console.warn('API GET failed:', path, e); }
    return null;
  }

  async function apiPost(path, body) {
    try {
      const r = await fetch(API_BASE + path, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {}),
      });
      if (r.ok) return await r.json();
    } catch (e) { console.warn('API POST failed:', path, e); }
    return null;
  }

  // ─── Status & Stats ─────────────────────────────────────────────────────────

  async function loadStatus() {
    const status = await apiGet('/api/performers/status');
    if (!status) {
      setStatus('error', 'VR Video backend not reachable');
      return;
    }

    setStatus(status.modelsLoaded ? 'ready' : 'loading',
      status.modelsLoaded ? `Models loaded (${status.modelSource})` : 'Models loading...');

    // Update stats
    const stats = await apiGet('/api/performers/stats');
    if (stats) {
      setText('face-stat-clusters', stats.totalClusters || 0);
      setText('face-stat-named', stats.namedPerformers || 0);
      setText('face-stat-detections', stats.totalDetections || 0);
      setText('face-stat-videos', stats.totalVideos || 0);
    }

    // Load named performers
    const named = await apiGet('/api/performers/named');
    renderNamedList(named || []);

    // Load unnamed clusters
    const unnamed = await apiGet('/api/performers/unnamed');
    renderUnnamedList(unnamed || []);

    // Load config
    const config = await apiGet('/api/performers/config');
    if (config) {
      setVal('face-config-detector', config.detector || 'ssd');
      setVal('face-config-ssd-conf', config.ssdMinConfidence || 0.4);
      setVal('face-config-min-size', config.minFaceSize || 60);
      setVal('face-config-thresh-high', config.matchThresholdHigh || 0.45);
      setVal('face-config-thresh-low', config.matchThresholdLow || 0.55);
    }
  }

  function setStatus(type, text) {
    const el = document.getElementById('face-model-status');
    if (!el) return;
    el.textContent = text;
    el.style.color = type === 'ready' ? 'var(--accent, #4caf50)' :
                     type === 'error' ? 'var(--color-error, #f44)' : 'var(--fg)';
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) {
      el.value = val;
      const label = document.getElementById(id + '-val');
      if (label) label.textContent = val;
    }
  }

  // ─── Lists ──────────────────────────────────────────────────────────────────

  function renderNamedList(performers) {
    const container = document.getElementById('face-named-list');
    if (!container) return;
    if (!performers.length) {
      container.innerHTML = '<div class="admin-empty">No named performers yet.</div>';
      return;
    }
    // XSS-safe: data from our own API, all dynamic values escaped via esc()
    container.innerHTML = performers.map(p => {
      const row = document.createElement('div');
      row.className = 'face-performer-row';
      row.dataset.id = p.id;
      row.innerHTML = `
        <div class="face-performer-thumb">
          ${p.thumbnail ? `<img src="${esc(p.thumbnail)}" alt="">` : '<div class="no-thumb"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/></svg></div>'}
        </div>
        <div class="face-performer-info">
          <div class="face-performer-name">${esc(p.name)}</div>
          <div class="face-performer-meta">${p.videoCount || 0} videos · ${p.detectionCount || 0} faces</div>
        </div>
        <div class="face-performer-actions">
          <button class="admin-btn-sm face-merge-btn" title="Merge with another performer">Merge</button>
          <button class="admin-btn-sm face-unname-btn" title="Remove name">Unname</button>
          <button class="admin-btn-delete face-delete-btn" title="Delete performer">✕</button>
        </div>
      `;
      return row.outerHTML;
    }).join('');

    // Attach handlers
    container.querySelectorAll('.face-unname-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const row = e.target.closest('.face-performer-row');
        const id = row?.dataset?.id;
        if (id && confirm('Remove name from this performer?')) {
          await apiPost(`/api/performers/unname-cluster`, { clusterId: id });
          loadStatus();
        }
      });
    });
    container.querySelectorAll('.face-delete-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const row = e.target.closest('.face-performer-row');
        const id = row?.dataset?.id;
        if (id && confirm('Delete this performer and all their data?')) {
          await fetch(`/api/performers/cluster/${id}`, { method: 'DELETE', credentials: 'same-origin' });
          loadStatus();
        }
      });
    });
  }

  function renderUnnamedList(clusters) {
    const container = document.getElementById('face-unnamed-list');
    if (!container) return;
    if (!clusters.length) {
      container.innerHTML = '<div class="admin-empty">No clusters detected. Scan videos first.</div>';
      return;
    }
    container.innerHTML = clusters.map(c => `
      <div class="face-cluster-row" data-id="${c.id}">
        <div class="face-cluster-thumbs">
          ${(c.thumbnails || []).slice(0, 4).map(t =>
            `<img src="${t}" alt="" class="face-cluster-thumb">`
          ).join('')}
          ${!c.thumbnails?.length ? '<div class="no-thumb small"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/></svg></div>' : ''}
        </div>
        <div class="face-cluster-info">
          <div class="face-cluster-name">Cluster #${c.id.slice(0, 8)}</div>
          <div class="face-cluster-meta">${c.faceCount || 0} faces · ${c.videoCount || 0} videos · quality: ${c.avgQuality || 'n/a'}</div>
        </div>
        <div class="face-cluster-actions">
          <input type="text" class="face-name-input" placeholder="Name this performer..." style="width:120px;font-size:11px;padding:3px 6px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--fg);">
          <button class="admin-btn-sm face-name-btn">Name</button>
        </div>
      </div>
    `).join('');

    // Attach handlers
    container.querySelectorAll('.face-name-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const row = e.target.closest('.face-cluster-row');
        const id = row?.dataset?.id;
        const input = row?.querySelector('.face-name-input');
        const name = input?.value?.trim();
        if (id && name) {
          await apiPost('/api/performers/name-cluster', { clusterId: id, performerName: name });
          loadStatus();
        }
      });
    });
  }

  // ─── Scan ───────────────────────────────────────────────────────────────────

  async function startScan() {
    if (_scanInProgress) return;
    _scanInProgress = true;

    const btn = document.getElementById('face-scan-all-btn');
    const progress = document.getElementById('face-scan-progress');
    const bar = document.getElementById('face-scan-bar');
    const text = document.getElementById('face-scan-text');
    const pct = document.getElementById('face-scan-pct');

    if (btn) { btn.disabled = true; btn.textContent = 'Scanning...'; }
    if (progress) progress.style.display = 'block';
    if (bar) bar.style.width = '0%';
    if (text) text.textContent = 'Starting scan...';

    try {
      // Start batch scan
      const result = await apiPost('/api/performers/batch-scan?limit=500', {});
      if (result?.error) {
        alert('Scan failed: ' + result.error);
        return;
      }

      // Poll for progress
      const pollInterval = setInterval(async () => {
        const status = await apiGet('/api/performers/status');
        if (!status) return;

        const queue = status.queue || {};
        const total = (queue.pending || 0) + (queue.active || 0) + (result?.processed || 0);
        const done = result?.processed || 0;
        const pctVal = total > 0 ? Math.round((done / total) * 100) : 0;

        if (bar) bar.style.width = pctVal + '%';
        if (pct) pct.textContent = pctVal + '%';
        if (text) text.textContent = `Scanning... ${done}/${total} videos`;

        if (queue.pending === 0 && queue.active === 0) {
          clearInterval(pollInterval);
          _scanInProgress = false;
          if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg> Scan All Videos'; }
          if (progress) progress.style.display = 'none';
          loadStatus();
        }
      }, 2000);

    } catch (e) {
      console.error('Scan failed:', e);
      _scanInProgress = false;
      if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg> Scan All Videos'; }
      if (progress) progress.style.display = 'none';
    }
  }

  async function clearOffline() {
    if (!confirm('Remove all offline endpoints?')) return;
    await apiPost('/api/model-endpoints/clear-offline', {});
    loadStatus();
  }

  async function saveConfiguration() {
    const config = {
      detector: document.getElementById('face-config-detector')?.value || 'ssd',
      ssdMinConfidence: parseFloat(document.getElementById('face-config-ssd-conf')?.value || 0.4),
      minFaceSize: parseInt(document.getElementById('face-config-min-size')?.value || 60),
      matchThresholdHigh: parseFloat(document.getElementById('face-config-thresh-high')?.value || 0.45),
      matchThresholdLow: parseFloat(document.getElementById('face-config-thresh-low')?.value || 0.55),
    };
    await apiPost('/api/performers/config', config);
    alert('Configuration saved');
  }

  // ─── Helpers ────────────────────────────────────────────────────────────────

  function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  // ─── Boot ───────────────────────────────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
