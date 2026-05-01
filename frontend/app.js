/**
 * Bombardment Engine — Dashboard Client
 * ======================================
 * Connects to FastAPI WebSocket and drives the UI.
 * Flow: Analyze (Gemini) → Start (bombardment) → Stop
 */

// ── State ──────────────────────────────────────────────────────
let ws = null;
let isRunning = false;
let selectedAlgos = null;  // set by Gemini analysis
let consoleLineCount = 0;
const MAX_CONSOLE_LINES = 200;
const MAX_CRASH_ENTRIES = 50;

const ALGO_DISPLAY = {
  bit_flip:   '⚡ Bit Flip',
  arithmetic: '🔢 Arithmetic',
  block:      '📦 Block',
  dictionary: '📖 Dictionary',
};

// ── DOM refs ───────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const dom = {
  statusDot:     $('status-dot'),
  statusText:    $('status-text'),
  btnAnalyze:    $('btn-analyze'),
  btnStart:      $('btn-start'),
  btnStop:       $('btn-stop'),
  iterations:    $('stat-iterations'),
  iterSub:       $('stat-iterations-sub'),
  crashes:       $('stat-crashes'),
  crashesSub:    $('stat-crashes-sub'),
  rate:          $('stat-rate'),
  speed:         $('stat-speed'),
  uptime:        $('stat-uptime'),
  seed:          $('stat-seed'),
  crashFeed:     $('crash-feed'),
  crashEmpty:    $('crash-empty'),
  crashBadge:    $('crash-badge'),
  console:       $('console'),
  consoleCount:  $('console-count'),
  analysisPanel: $('analysis-panel'),
  analysisContent: $('analysis-content'),
  analysisStatus:  $('analysis-status'),
  algoBadge:     $('algo-badge'),
  targetInput:   $('target-input'),
};

// ── Formatting ─────────────────────────────────────────────────
function fmtNumber(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function fmtUptime(seconds) {
  if (seconds < 60)   return Math.floor(seconds) + 's';
  if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + Math.floor(seconds % 60) + 's';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h + 'h ' + m + 'm';
}

// ── WebSocket ──────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    dom.statusDot.classList.add('active');
    dom.statusText.textContent = 'Connected';
    addConsoleLine('WebSocket connected to server.');
  };

  ws.onclose = () => {
    dom.statusDot.classList.remove('active');
    dom.statusText.textContent = 'Disconnected';
    addConsoleLine('WebSocket disconnected. Reconnecting…');
    setTimeout(connectWS, 2000);
  };

  ws.onerror = () => addConsoleLine('WebSocket error.', true);

  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'stats_update')    handleStats(msg.data);
      if (msg.type === 'crash_event')     handleCrash(msg.data);
      if (msg.type === 'log_message')     addConsoleLine(msg.data.message);
      if (msg.type === 'analysis_result') handleAnalysis(msg.data);
    } catch (e) {
      console.error('WS parse error:', e);
    }
  };
}

// ── Handlers ───────────────────────────────────────────────────
function handleStats(s) {
  dom.iterations.textContent = fmtNumber(s.total_iterations);
  dom.iterSub.textContent    = s.total_iterations.toLocaleString() + ' total';
  dom.crashes.textContent    = s.crashes_found;
  dom.crashesSub.textContent = s.crash_rate.toFixed(3) + '% rate';
  dom.rate.textContent       = s.crash_rate.toFixed(2) + '%';
  dom.speed.textContent      = s.speed.toFixed(0);
  dom.uptime.textContent     = fmtUptime(s.uptime_seconds);
  dom.seed.textContent       = s.current_seed || '—';

  const ms = s.mutation_stats;
  const maxVal = Math.max(1, ...Object.values(ms));
  for (const [key, count] of Object.entries(ms)) {
    const bar = $('bar-' + key);
    const cnt = $('count-' + key);
    if (bar) bar.style.width = (count / maxVal * 100) + '%';
    if (cnt) cnt.textContent = fmtNumber(count);
  }
}

let totalCrashEvents = 0;

function handleCrash(c) {
  if (dom.crashEmpty) dom.crashEmpty.style.display = 'none';

  totalCrashEvents++;
  dom.crashBadge.textContent = totalCrashEvents + ' crash' + (totalCrashEvents !== 1 ? 'es' : '');

  const entry = document.createElement('div');
  entry.className = 'crash-entry';
  entry.innerHTML = `
    <span class="crash-entry__icon">💥</span>
    <div class="crash-entry__body">
      <div class="crash-entry__title">${c.id} — ${c.signal_name}</div>
      <div class="crash-entry__meta">
        <span class="crash-entry__tag">algo: ${c.algorithm}</span>
        <span class="crash-entry__tag">seed: ${c.seed_file}</span>
        <span class="crash-entry__tag">size: ${c.payload_size}B</span>
        <span class="crash-entry__tag">sha: ${c.payload_hash}</span>
      </div>
    </div>
  `;
  dom.crashFeed.prepend(entry);

  while (dom.crashFeed.querySelectorAll('.crash-entry').length > MAX_CRASH_ENTRIES) {
    dom.crashFeed.lastElementChild.remove();
  }

  addConsoleLine(`CRASH ${c.id}: ${c.signal_name} via ${c.algorithm} — hash ${c.payload_hash}`, true);
}

function handleAnalysis(result) {
  selectedAlgos = result.selected_algorithms;

  // Update analysis panel
  dom.analysisStatus.textContent = result.status === 'success' ? '✓ Complete' : result.status;

  let chipsHtml = selectedAlgos.map(a =>
    `<span class="algo-chip algo-chip--${a}">${ALGO_DISPLAY[a] || a}</span>`
  ).join('');

  dom.analysisContent.innerHTML = `
    <div class="analysis-result">
      <div>
        <div class="analysis-result__label">Selected Algorithms</div>
        <div class="analysis-result__algos">${chipsHtml}</div>
      </div>
      <div>
        <div class="analysis-result__label">Gemini Raw Response</div>
        <div class="analysis-result__response">${escapeHtml(result.raw_response)}</div>
      </div>
    </div>
  `;

  // Update algo badge
  dom.algoBadge.textContent = selectedAlgos.length + ' Selected';

  // Dim unselected algorithm rows in the chart
  const allAlgos = ['bit_flip', 'arithmetic', 'block', 'dictionary'];
  for (const a of allAlgos) {
    const row = $('row-' + a);
    if (row) {
      row.classList.toggle('disabled', !selectedAlgos.includes(a));
    }
  }

  // Enable start button
  dom.btnStart.disabled = false;
  dom.btnAnalyze.disabled = false;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function addConsoleLine(text, isCrash = false) {
  const line = document.createElement('div');
  line.className = 'console-line' + (isCrash ? ' console-line--crash' : '');
  const ts = new Date().toLocaleTimeString();
  line.textContent = `[${ts}] ${text}`;
  dom.console.appendChild(line);

  consoleLineCount++;
  dom.consoleCount.textContent = consoleLineCount + ' events';

  while (dom.console.children.length > MAX_CONSOLE_LINES) {
    dom.console.firstChild.remove();
  }
  dom.console.scrollTop = dom.console.scrollHeight;
}

// ── API Controls ───────────────────────────────────────────────
async function analyzeTarget() {
  const targetDesc = dom.targetInput ? dom.targetInput.value.trim() : "";
  
  dom.btnAnalyze.disabled = true;
  dom.analysisStatus.textContent = 'Analyzing…';

  dom.analysisContent.innerHTML = `
    <div class="analysis-loading">
      <div class="analysis-spinner"></div>
      <span>Sending target to Gemini 2.5 Flash…</span>
    </div>
  `;

  addConsoleLine('🧠 Requesting Gemini strategy analysis…');

  const requestBody = {};
  if (targetDesc) {
      requestBody.custom_description = targetDesc;
      addConsoleLine(`Target description provided: "${targetDesc}"`);
  }

  try {
    const res = await fetch('/api/analyze', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'}, 
        body: JSON.stringify(requestBody) 
    });
    const data = await res.json();
    // Always handle directly — don't rely on WS race
    handleAnalysis(data);
  } catch (e) {
    addConsoleLine('Analysis error: ' + e.message, true);
    dom.analysisStatus.textContent = 'Error';
    dom.analysisContent.innerHTML = `<div class="analysis-prompt">Analysis failed: ${e.message}. Click Analyze to retry.</div>`;
    dom.btnAnalyze.disabled = false;
    dom.btnStart.disabled = false;
  }
}

async function startFuzzing() {
  if (isRunning) return;
  dom.btnStart.disabled = true;
  dom.btnAnalyze.disabled = true;
  addConsoleLine('Requesting engine start…');
  try {
    const body = selectedAlgos ? JSON.stringify({ algorithms: selectedAlgos }) : '{}';
    const res = await fetch('/api/start', { method: 'POST', headers: {'Content-Type':'application/json'}, body });
    const data = await res.json();
    if (data.status === 'started' || data.status === 'already_running') {
      isRunning = true;
      dom.btnStop.disabled = false;
      dom.btnStart.disabled = true;
      addConsoleLine('🚀 Engine running with: ' + (data.algorithms || []).join(', '));
    } else {
      addConsoleLine('Start failed: ' + (data.message || data.status), true);
      dom.btnStart.disabled = false;
      dom.btnAnalyze.disabled = false;
    }
  } catch (e) {
    addConsoleLine('Network error: ' + e.message, true);
    dom.btnStart.disabled = false;
    dom.btnAnalyze.disabled = false;
  }
}

async function stopFuzzing() {
  if (!isRunning) return;
  dom.btnStop.disabled = true;
  addConsoleLine('Requesting engine stop…');
  try {
    await fetch('/api/stop', { method: 'POST' });
    isRunning = false;
    dom.btnStart.disabled = false;
    dom.btnStop.disabled = true;
    dom.btnAnalyze.disabled = false;
    addConsoleLine('🛑 Engine stopped.');
  } catch (e) {
    addConsoleLine('Network error: ' + e.message, true);
    dom.btnStop.disabled = false;
  }
}

// ── Init ───────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  addConsoleLine('Dashboard initialized. Connecting to server…');
  connectWS();
});
