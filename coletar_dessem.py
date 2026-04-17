<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GNA Monitor — DESSEM / ONS</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg:        #0b0e13;
    --surface:   #131820;
    --border:    #1e2733;
    --border2:   #2a3544;
    --text:      #c8d4e0;
    --muted:     #5a6a7a;
    --accent:    #00c2ff;
    --gna1:      #00c2ff;
    --gna2:      #ff6b35;
    --green:     #22d3a5;
    --yellow:    #f5c518;
    --red:       #ff4d6a;
    --mono:      'IBM Plex Mono', monospace;
    --sans:      'IBM Plex Sans', sans-serif;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:var(--sans); font-size:13px; min-height:100vh; }

  /* ─── HEADER ─────────────────────────────────────────────── */
  header {
    background:var(--surface);
    border-bottom:1px solid var(--border);
    padding:0 24px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:16px;
    height:60px;
    position:sticky;
    top:0;
    z-index:100;
    flex-wrap:wrap;
  }
  .header-brand {
    display:flex;
    align-items:center;
    gap:12px;
    flex-shrink:0;
  }
  .brand-icon {
    width:32px; height:32px;
    background:linear-gradient(135deg,var(--gna1),var(--gna2));
    border-radius:6px;
    display:flex; align-items:center; justify-content:center;
    font-family:var(--mono);
    font-size:11px;
    font-weight:600;
    color:#fff;
  }
  .brand-title {
    font-family:var(--mono);
    font-size:13px;
    font-weight:600;
    color:#fff;
    letter-spacing:2px;
    text-transform:uppercase;
  }
  .brand-sub {
    font-size:10px;
    color:var(--muted);
    letter-spacing:1px;
    margin-top:1px;
  }

  /* ─── DATE PICKER SECTION ─────────────────────────────────── */
  .header-controls {
    display:flex;
    align-items:center;
    gap:12px;
    flex-wrap:wrap;
  }
  .date-control {
    display:flex;
    align-items:center;
    gap:8px;
    background:var(--bg);
    border:1px solid var(--border2);
    border-radius:6px;
    padding:6px 12px;
  }
  .date-control label {
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
    letter-spacing:1px;
    text-transform:uppercase;
    white-space:nowrap;
  }
  .date-control input[type="date"] {
    background:transparent;
    border:none;
    color:var(--accent);
    font-family:var(--mono);
    font-size:12px;
    font-weight:500;
    outline:none;
    cursor:pointer;
    width:130px;
  }
  .date-control input[type="date"]::-webkit-calendar-picker-indicator {
    filter:invert(0.6) sepia(1) saturate(5) hue-rotate(170deg);
    cursor:pointer;
  }
  .btn-today {
    background:var(--border2);
    border:1px solid var(--border2);
    color:var(--text);
    font-family:var(--mono);
    font-size:10px;
    padding:5px 10px;
    border-radius:5px;
    cursor:pointer;
    letter-spacing:1px;
    text-transform:uppercase;
    transition:all .15s;
  }
  .btn-today:hover { background:var(--accent); color:#000; border-color:var(--accent); }

  .header-status {
    display:flex;
    align-items:center;
    gap:6px;
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
  }
  .status-dot {
    width:6px; height:6px;
    border-radius:50%;
    background:var(--green);
    animation:pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1}50%{opacity:.3} }

  /* ─── DAILY PRICE SUMMARY BANNER ─────────────────────────── */
  .price-summary {
    background:var(--surface);
    border-bottom:1px solid var(--border);
    padding:14px 24px;
    display:flex;
    align-items:center;
    gap:0;
    overflow-x:auto;
  }
  .summary-label {
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
    letter-spacing:2px;
    text-transform:uppercase;
    padding-right:20px;
    border-right:1px solid var(--border2);
    margin-right:20px;
    white-space:nowrap;
    flex-shrink:0;
  }
  .summary-date-display {
    font-family:var(--mono);
    font-size:12px;
    color:var(--accent);
    font-weight:600;
    padding-right:20px;
    border-right:1px solid var(--border2);
    margin-right:20px;
    white-space:nowrap;
    flex-shrink:0;
  }
  .summary-cards {
    display:flex;
    gap:12px;
    flex-wrap:nowrap;
    overflow-x:auto;
  }
  .summary-card {
    background:var(--bg);
    border:1px solid var(--border2);
    border-radius:6px;
    padding:10px 16px;
    min-width:160px;
    position:relative;
    overflow:hidden;
    flex-shrink:0;
  }
  .summary-card::before {
    content:'';
    position:absolute;
    left:0; top:0; bottom:0;
    width:3px;
  }
  .summary-card.cmo::before  { background:var(--accent); }
  .summary-card.cmb::before  { background:var(--yellow); }
  .summary-card.gter::before { background:var(--green); }
  .summary-card.cgter::before{ background:var(--gna2); }
  .summary-card.samples::before{ background:var(--muted); }
  .card-label {
    font-family:var(--mono);
    font-size:9px;
    color:var(--muted);
    letter-spacing:2px;
    text-transform:uppercase;
    margin-bottom:4px;
  }
  .card-value {
    font-family:var(--mono);
    font-size:20px;
    font-weight:600;
    line-height:1;
  }
  .card-unit {
    font-size:10px;
    color:var(--muted);
    margin-left:2px;
  }
  .card-detail {
    font-family:var(--mono);
    font-size:9px;
    color:var(--muted);
    margin-top:4px;
  }
  .cmo  .card-value { color:var(--accent); }
  .cmb  .card-value { color:var(--yellow); }
  .gter .card-value { color:var(--green); }
  .cgter.card-value { color:var(--gna2); }
  .cgter .card-value { color:var(--gna2); }
  .samples .card-value { color:var(--muted); font-size:16px; }

  .no-data-banner {
    display:none;
    align-items:center;
    gap:8px;
    font-family:var(--mono);
    font-size:11px;
    color:var(--muted);
    padding:8px 14px;
    background:var(--bg);
    border:1px solid var(--border2);
    border-radius:6px;
  }

  /* ─── LAYOUT ─────────────────────────────────────────────── */
  .main-wrap { padding:20px 24px; }

  /* ─── TABS ───────────────────────────────────────────────── */
  .tabs {
    display:flex;
    gap:2px;
    margin-bottom:20px;
    border-bottom:1px solid var(--border);
  }
  .tab-btn {
    background:none;
    border:none;
    color:var(--muted);
    font-family:var(--mono);
    font-size:11px;
    letter-spacing:1px;
    text-transform:uppercase;
    padding:10px 18px;
    cursor:pointer;
    border-bottom:2px solid transparent;
    margin-bottom:-1px;
    transition:all .15s;
  }
  .tab-btn:hover { color:var(--text); }
  .tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); }
  .tab-btn .pill {
    display:inline-block;
    background:var(--border2);
    color:var(--muted);
    font-size:9px;
    border-radius:3px;
    padding:1px 5px;
    margin-left:6px;
  }
  .tab-btn.active .pill { background:var(--accent); color:#000; }

  .tab-panel { display:none; }
  .tab-panel.active { display:block; }

  /* ─── SECTION HEADER ─────────────────────────────────────── */
  .section-header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:12px;
    flex-wrap:wrap;
    gap:8px;
  }
  .section-title {
    font-family:var(--mono);
    font-size:11px;
    color:var(--muted);
    letter-spacing:2px;
    text-transform:uppercase;
    display:flex;
    align-items:center;
    gap:8px;
  }
  .section-title .bar {
    width:16px; height:2px;
    background:var(--accent);
  }
  .search-box {
    display:flex;
    align-items:center;
    gap:8px;
    background:var(--surface);
    border:1px solid var(--border2);
    border-radius:5px;
    padding:5px 10px;
  }
  .search-box input {
    background:none;
    border:none;
    color:var(--text);
    font-family:var(--mono);
    font-size:12px;
    outline:none;
    width:180px;
  }
  .search-box input::placeholder { color:var(--muted); }

  /* ─── TABLE ──────────────────────────────────────────────── */
  .table-wrap {
    overflow-x:auto;
    border:1px solid var(--border);
    border-radius:8px;
  }
  table { width:100%; border-collapse:collapse; font-family:var(--mono); font-size:12px; }
  thead tr {
    background:#0d1219;
    border-bottom:1px solid var(--border2);
  }
  th {
    padding:10px 14px;
    text-align:left;
    color:var(--muted);
    font-size:10px;
    letter-spacing:1px;
    text-transform:uppercase;
    white-space:nowrap;
    cursor:pointer;
    user-select:none;
    position:relative;
  }
  th:hover { color:var(--text); }
  th .sort-icon { margin-left:4px; opacity:.4; }
  th.sorted-asc .sort-icon::after  { content:'▲'; color:var(--accent); opacity:1; }
  th.sorted-desc .sort-icon::after { content:'▼'; color:var(--accent); opacity:1; }
  tbody tr {
    border-bottom:1px solid var(--border);
    transition:background .1s;
  }
  tbody tr:last-child { border-bottom:none; }
  tbody tr:hover { background:#161e28; }
  td { padding:9px 14px; white-space:nowrap; }
  td.plant-gna1 { color:var(--gna1); font-weight:600; }
  td.plant-gna2 { color:var(--gna2); font-weight:600; }
  td.num { text-align:right; }
  td.positive { color:var(--yellow); }
  td.zero     { color:var(--muted); }
  td.negative { color:var(--red); }
  .empty-row td { text-align:center; color:var(--muted); padding:24px; }

  /* ─── PDPW TABLE ─────────────────────────────────────────── */
  .pdpw-meta {
    display:flex;
    gap:10px;
    margin-bottom:12px;
    flex-wrap:wrap;
  }
  .meta-tag {
    background:var(--bg);
    border:1px solid var(--border2);
    border-radius:4px;
    padding:4px 10px;
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
  }
  .meta-tag span { color:var(--text); }

  /* ─── HISTORY CHART AREA ─────────────────────────────────── */
  .chart-section { margin-top:28px; }
  .chart-title {
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
    letter-spacing:2px;
    text-transform:uppercase;
    margin-bottom:12px;
    display:flex;
    align-items:center;
    gap:8px;
  }
  .chart-wrap {
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:8px;
    padding:16px;
    overflow-x:auto;
  }
  canvas { display:block; width:100% !important; }

  /* ─── RAW HEADER ─────────────────────────────────────────── */
  .raw-box {
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:6px;
    padding:12px 16px;
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
    overflow-x:auto;
    white-space:pre;
    margin-top:12px;
  }
  .raw-label {
    font-size:9px;
    letter-spacing:2px;
    text-transform:uppercase;
    color:var(--border2);
    margin-bottom:6px;
  }

  /* ─── FOOTER ─────────────────────────────────────────────── */
  footer {
    border-top:1px solid var(--border);
    padding:14px 24px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    font-family:var(--mono);
    font-size:10px;
    color:var(--muted);
    flex-wrap:wrap;
    gap:8px;
  }
  footer a { color:var(--border2); text-decoration:none; }
  footer a:hover { color:var(--accent); }
  #last-update { font-size:10px; color:var(--muted); }

  @media(max-width:768px){
    header { height:auto; padding:12px 16px; }
    .main-wrap { padding:14px 16px; }
    .price-summary { padding:12px 16px; }
  }
</style>
</head>
<body>

<!-- ════════════════════ HEADER ════════════════════ -->
<header>
  <div class="header-brand">
    <div class="brand-icon">GNA</div>
    <div>
      <div class="brand-title">GNA Monitor</div>
      <div class="brand-sub">DESSEM / ONS · PDO OPER TERM</div>
    </div>
  </div>

  <div class="header-controls">
    <!-- DATE PICKER -->
    <div class="date-control">
      <label>Data</label>
      <input type="date" id="datePicker" title="Selecionar data"/>
    </div>
    <button class="btn-today" onclick="setToday()">Hoje</button>

    <div class="header-status">
      <div class="status-dot" id="statusDot"></div>
      <span id="statusTxt">carregando...</span>
    </div>
  </div>
</header>

<!-- ════════════════════ PRICE SUMMARY BANNER ════════════════════ -->
<div class="price-summary" id="priceSummary">
  <div class="summary-label">Resumo do dia</div>
  <div class="summary-date-display" id="summaryDateDisplay">—</div>
  <div class="summary-cards" id="summaryCards">
    <!-- injected by JS -->
  </div>
  <div class="no-data-banner" id="noDataBanner">
    <span>⚠</span> Sem dados para a data selecionada
  </div>
</div>

<!-- ════════════════════ MAIN ════════════════════ -->
<div class="main-wrap">

  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('dat',this)">
      PDO Oper Term <span class="pill" id="pillDat">0</span>
    </button>
    <button class="tab-btn" onclick="switchTab('pdpw',this)">
      PDO Term (PDPW) <span class="pill" id="pillPdpw">0</span>
    </button>
    <button class="tab-btn" onclick="switchTab('history',this)">
      Histórico
    </button>
    <button class="tab-btn" onclick="switchTab('raw',this)">
      Raw
    </button>
  </div>

  <!-- TAB: DAT -->
  <div class="tab-panel active" id="tab-dat">
    <div class="section-header">
      <div class="section-title"><span class="bar"></span>Registros GNA — Data selecionada</div>
      <div class="search-box">
        <span style="color:var(--muted);font-size:12px">⌕</span>
        <input type="text" id="searchDat" placeholder="filtrar..." oninput="filterTable('tableDat',this.value)"/>
      </div>
    </div>
    <div class="table-wrap">
      <table id="tableDat">
        <thead><tr id="theadDat"></tr></thead>
        <tbody id="tbodyDat"></tbody>
      </table>
    </div>
  </div>

  <!-- TAB: PDPW -->
  <div class="tab-panel" id="tab-pdpw">
    <div class="pdpw-meta" id="pdpwMeta"></div>
    <div class="section-header">
      <div class="section-title"><span class="bar" style="background:var(--yellow)"></span>PDO Term — Intervalos 30 min</div>
      <div class="search-box">
        <span style="color:var(--muted);font-size:12px">⌕</span>
        <input type="text" id="searchPdpw" placeholder="filtrar..." oninput="filterTable('tablePdpw',this.value)"/>
      </div>
    </div>
    <div class="table-wrap">
      <table id="tablePdpw">
        <thead><tr id="theadPdpw"></tr></thead>
        <tbody id="tbodyPdpw"></tbody>
      </table>
    </div>
  </div>

  <!-- TAB: HISTORY -->
  <div class="tab-panel" id="tab-history">
    <div class="chart-section">
      <div class="chart-title"><span class="bar"></span>CMO médio — Últimas 288 coletas</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="chartCMO" height="200"></canvas>
      </div>
    </div>
    <div class="chart-section">
      <div class="chart-title"><span class="bar" style="background:var(--yellow)"></span>GTER (Geração) — Histórico</div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="chartGTER" height="200"></canvas>
      </div>
    </div>
  </div>

  <!-- TAB: RAW -->
  <div class="tab-panel" id="tab-raw">
    <div class="section-title" style="margin-bottom:10px"><span class="bar" style="background:var(--muted)"></span>Cabeçalho raw do arquivo .dat</div>
    <div class="raw-box">
      <div class="raw-label">raw_header</div>
      <span id="rawHeader">—</span>
    </div>
    <div style="margin-top:16px">
      <div class="section-title"><span class="bar" style="background:var(--muted)"></span>Metadados da última coleta</div>
      <div class="raw-box" id="rawMeta" style="margin-top:8px">—</div>
    </div>
  </div>

</div>

<!-- ════════════════════ FOOTER ════════════════════ -->
<footer>
  <div>GNA MONITOR · DESSEM/ONS · <a href="pdo_oper_term.dat" download>⬇ .dat</a> &nbsp;|&nbsp; <a href="dados_gna.json" target="_blank">JSON</a></div>
  <div id="last-update">Aguardando dados...</div>
</footer>

<script>
// ─── Globals ─────────────────────────────────────────────────
let ALL_DATA = null;
let SELECTED_DATE = '';
let sortState = {};

// ─── Init ─────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  setTodayDate();
  loadData();
  setInterval(loadData, 5 * 60 * 1000);

  document.getElementById('datePicker').addEventListener('change', e => {
    SELECTED_DATE = e.target.value;
    if (ALL_DATA) renderAll(ALL_DATA);
  });
});

function setTodayDate() {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('datePicker').value = today;
  SELECTED_DATE = today;
}

function setToday() {
  setTodayDate();
  if (ALL_DATA) renderAll(ALL_DATA);
}

// ─── Load Data ────────────────────────────────────────────────
async function loadData() {
  try {
    const r = await fetch('dados_gna.json?t=' + Date.now());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    ALL_DATA = data;
    renderAll(data);
    setStatus('ok', data.ultima_coleta);
  } catch(e) {
    setStatus('err', 'erro ao carregar');
  }
}

function setStatus(state, msg) {
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusTxt');
  if (state === 'ok') {
    dot.style.background = 'var(--green)';
    const ts = msg ? new Date(msg) : new Date();
    txt.textContent = formatTS(ts);
    document.getElementById('last-update').textContent = 'Última coleta: ' + formatTS(ts);
  } else {
    dot.style.background = 'var(--red)';
    txt.textContent = msg || 'erro';
  }
}

// ─── Render All ───────────────────────────────────────────────
function renderAll(data) {
  // Find history entries for selected date
  const dayEntries = getEntriesForDate(data, SELECTED_DATE);

  renderSummary(dayEntries, data);
  renderDatTable(data, dayEntries);
  renderPdpwTable(data);
  renderCharts(data);
  renderRaw(data);
}

// ─── Filter history by date ────────────────────────────────────
function getEntriesForDate(data, dateStr) {
  if (!dateStr || !data.historico) return [];
  return data.historico.filter(entry => {
    const ts = entry.timestamp || '';
    // ISO timestamp: 2025-04-17T... or localdate
    const entryDate = ts.substring(0, 10);
    return entryDate === dateStr;
  });
}

// ─── Price Summary Banner ─────────────────────────────────────
function renderSummary(entries, data) {
  const dp = document.getElementById('summaryDateDisplay');
  const cards = document.getElementById('summaryCards');
  const noData = document.getElementById('noDataBanner');

  // Format display date
  if (SELECTED_DATE) {
    const [y, m, d] = SELECTED_DATE.split('-');
    dp.textContent = d + '/' + m + '/' + y;
  }

  // Collect all registros from selected date entries
  let allRegs = [];
  entries.forEach(e => {
    if (e.registros) allRegs = allRegs.concat(e.registros);
  });

  // Also include current registros if date is today
  const todayStr = new Date().toISOString().substring(0, 10);
  if (SELECTED_DATE === todayStr && data.registros) {
    allRegs = allRegs.concat(data.registros);
  }

  // Deduplicate roughly (by JSON string)
  const seen = new Set();
  allRegs = allRegs.filter(r => {
    const k = JSON.stringify(r);
    if (seen.has(k)) return false;
    seen.add(k); return true;
  });

  if (allRegs.length === 0) {
    // try current data if no history
    if (data.registros && data.registros.length > 0) {
      allRegs = data.registros;
    }
  }

  if (allRegs.length === 0) {
    cards.style.display = 'none';
    noData.style.display = 'flex';
    return;
  }
  cards.style.display = 'flex';
  noData.style.display = 'none';

  const avg = (field) => {
    const vals = allRegs.map(r => r[field]).filter(v => v !== null && v !== undefined && !isNaN(v));
    if (!vals.length) return null;
    return vals.reduce((a,b) => a + b, 0) / vals.length;
  };
  const avgGNA = (field, planta) => {
    const vals = allRegs.filter(r => r.planta_id === planta).map(r => r[field]).filter(v => v !== null && !isNaN(v));
    if (!vals.length) return null;
    return vals.reduce((a,b) => a + b, 0) / vals.length;
  };

  const cmo  = avg('CMO');
  const cmb  = avg('CMB');
  const gter = avg('GTER');
  const cgter= avg('ClinGter');
  const nSamples = entries.length || 1;

  function fmtBRL(v) {
    if (v === null) return '—';
    return v.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});
  }

  const cmoGna1  = avgGNA('CMO','GNA I');
  const cmoGna2  = avgGNA('CMO','GNA II');
  const gterGna1 = avgGNA('GTER','GNA I');
  const gterGna2 = avgGNA('GTER','GNA II');

  cards.innerHTML = `
    <div class="summary-card cmo">
      <div class="card-label">CMO Médio</div>
      <div class="card-value">${fmtBRL(cmo)}<span class="card-unit">R$/MWh</span></div>
      <div class="card-detail">GNA I: ${fmtBRL(cmoGna1)} · GNA II: ${fmtBRL(cmoGna2)}</div>
    </div>
    <div class="summary-card cmb">
      <div class="card-label">CMB Médio</div>
      <div class="card-value">${fmtBRL(cmb)}<span class="card-unit">R$/MWh</span></div>
      <div class="card-detail">${allRegs.length} reg · ${nSamples} coletas</div>
    </div>
    <div class="summary-card gter">
      <div class="card-label">GTER Média</div>
      <div class="card-value">${fmtBRL(gter)}<span class="card-unit">MW</span></div>
      <div class="card-detail">GNA I: ${fmtBRL(gterGna1)} · GNA II: ${fmtBRL(gterGna2)}</div>
    </div>
    <div class="summary-card cgter">
      <div class="card-label">ClinGter Médio</div>
      <div class="card-value">${fmtBRL(cgter)}<span class="card-unit">R$/MWh</span></div>
      <div class="card-detail">Custo linear de geração</div>
    </div>
    <div class="summary-card samples">
      <div class="card-label">Amostras</div>
      <div class="card-value">${nSamples}</div>
      <div class="card-detail">coletas do dia</div>
    </div>
  `;
}

// ─── DAT Table ────────────────────────────────────────────────
function renderDatTable(data, dayEntries) {
  // Show records from selected date, fall back to current
  let regs = [];
  if (dayEntries.length > 0) {
    // Use latest entry from that day
    const latest = dayEntries[dayEntries.length - 1];
    regs = latest.registros || [];
  }
  if (regs.length === 0 && data.registros) regs = data.registros;

  const cols = data.colunas || [];
  document.getElementById('pillDat').textContent = regs.length;

  const thead = document.getElementById('theadDat');
  const allCols = ['Planta', ...cols];
  thead.innerHTML = allCols.map((c,i) =>
    `<th onclick="sortTable('tableDat',${i})" data-col="${i}">
      ${c}<span class="sort-icon"></span>
    </th>`
  ).join('');

  const tbody = document.getElementById('tbodyDat');
  if (regs.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="${allCols.length}">Sem dados para a data selecionada</td></tr>`;
    return;
  }
  tbody.innerHTML = regs.map(reg => {
    const cls = reg.planta_id === 'GNA I' ? 'plant-gna1' : 'plant-gna2';
    let cells = `<td class="${cls}">${reg.planta_id || '—'}</td>`;
    for (const c of cols) {
      const v = reg[c];
      cells += `<td class="${numClass(v)} num">${fmt(v)}</td>`;
    }
    return `<tr>${cells}</tr>`;
  }).join('');
}

// ─── PDPW Table ───────────────────────────────────────────────
function renderPdpwTable(data) {
  const pdo = data.pdo_term || {};
  const regs = pdo.registros || [];
  const cols = (pdo.colunas || []).filter(c => !['data_pdpw','empresa','data','intervalo'].some(e => c.toLowerCase().includes(e.toLowerCase())));
  document.getElementById('pillPdpw').textContent = regs.length;

  // Meta
  document.getElementById('pdpwMeta').innerHTML = `
    <div class="meta-tag">Data: <span>${pdo.data || '—'}</span></div>
    <div class="meta-tag">Empresa: <span>${pdo.empresa || '—'}</span></div>
    <div class="meta-tag">Registros: <span>${regs.length}</span></div>
  `;

  const thead = document.getElementById('theadPdpw');
  thead.innerHTML = cols.map((c,i) =>
    `<th onclick="sortTable('tablePdpw',${i})" data-col="${i}">${c}<span class="sort-icon"></span></th>`
  ).join('');

  const tbody = document.getElementById('tbodyPdpw');
  if (regs.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="${cols.length || 1}">Sem dados PDPW</td></tr>`;
    return;
  }
  tbody.innerHTML = regs.map(reg => {
    const cells = cols.map(c => {
      const v = reg[c];
      return `<td class="${numClass(v)} num">${fmt(v)}</td>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');
}

// ─── Charts ──────────────────────────────────────────────────
function renderCharts(data) {
  const hist = data.historico || [];
  if (!hist.length) return;

  // Last 288 entries
  const entries = hist.slice(-288);

  const labels = entries.map(e => {
    const ts = new Date(e.timestamp);
    return ts.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit'});
  });

  // CMO per entry: average across registros
  const cmoVals = entries.map(e => {
    const regs = e.registros || [];
    const vals = regs.map(r => r['CMO']).filter(v => v !== null && !isNaN(v));
    return vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
  });

  const gterVals = entries.map(e => {
    const regs = e.registros || [];
    const vals = regs.map(r => r['GTER']).filter(v => v !== null && !isNaN(v));
    return vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
  });

  drawLineChart('chartCMO', labels, [
    {label:'CMO (R$/MWh)', data:cmoVals, color:'#00c2ff'}
  ]);
  drawLineChart('chartGTER', labels, [
    {label:'GTER (MW)', data:gterVals, color:'#22d3a5'}
  ]);
}

function drawLineChart(id, labels, series) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.parentElement.offsetWidth || 800;
  const H = 180;
  canvas.width = W;
  canvas.height = H;

  ctx.clearRect(0, 0, W, H);
  const PAD = {top:16, right:20, bottom:32, left:60};
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  // Collect all values
  const allVals = series.flatMap(s => s.data.filter(v => v !== null));
  if (!allVals.length) return;
  const mn = Math.min(...allVals), mx = Math.max(...allVals);
  const range = mx - mn || 1;

  const xOf = i => PAD.left + (i / (labels.length - 1 || 1)) * cW;
  const yOf = v => PAD.top + cH - ((v - mn) / range) * cH;

  // Grid
  ctx.strokeStyle = '#1e2733';
  ctx.lineWidth = 1;
  for (let j = 0; j <= 4; j++) {
    const y = PAD.top + (j / 4) * cH;
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + cW, y); ctx.stroke();
    const val = mx - (j / 4) * range;
    ctx.fillStyle = '#5a6a7a';
    ctx.font = '10px IBM Plex Mono, monospace';
    ctx.textAlign = 'right';
    ctx.fillText(fmtShort(val), PAD.left - 6, y + 3);
  }

  // X labels (sparse)
  const step = Math.ceil(labels.length / 8);
  ctx.fillStyle = '#5a6a7a';
  ctx.font = '9px IBM Plex Mono, monospace';
  ctx.textAlign = 'center';
  for (let i = 0; i < labels.length; i += step) {
    ctx.fillText(labels[i], xOf(i), H - 8);
  }

  // Lines
  series.forEach(s => {
    ctx.beginPath();
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 1.5;
    let first = true;
    s.data.forEach((v, i) => {
      if (v === null) { first = true; return; }
      const x = xOf(i), y = yOf(v);
      if (first) { ctx.moveTo(x, y); first = false; }
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill area
    ctx.save();
    ctx.beginPath();
    let started = false;
    let lastX = PAD.left;
    s.data.forEach((v, i) => {
      if (v === null) return;
      const x = xOf(i), y = yOf(v);
      if (!started) { ctx.moveTo(x, PAD.top + cH); ctx.lineTo(x, y); started = true; }
      else ctx.lineTo(x, y);
      lastX = x;
    });
    ctx.lineTo(lastX, PAD.top + cH);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, PAD.top, 0, PAD.top + cH);
    grad.addColorStop(0, s.color + '33');
    grad.addColorStop(1, s.color + '00');
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.restore();
  });
}

function fmtShort(v) {
  if (v === null || v === undefined) return '—';
  if (Math.abs(v) >= 1000) return (v/1000).toFixed(1) + 'k';
  return v.toFixed(0);
}

// ─── Raw Tab ─────────────────────────────────────────────────
function renderRaw(data) {
  document.getElementById('rawHeader').textContent = data.raw_header || '(sem cabeçalho)';
  document.getElementById('rawMeta').textContent = JSON.stringify({
    ultima_coleta: data.ultima_coleta,
    status: data.status,
    arquivo: data.arquivo,
    total_linhas_arquivo: data.total_linhas_arquivo,
    total_registros_gna: data.total_registros_gna,
    colunas: data.colunas,
  }, null, 2);
}

// ─── Helpers ─────────────────────────────────────────────────
function fmt(v) {
  if (v === null || v === undefined || v === '') return '<span style="color:var(--border2)">—</span>';
  if (typeof v === 'number') return v.toLocaleString('pt-BR', {minimumFractionDigits:2, maximumFractionDigits:2});
  return v;
}

function numClass(v) {
  if (typeof v !== 'number') return '';
  if (v > 0) return 'positive';
  if (v < 0) return 'negative';
  return 'zero';
}

function formatTS(d) {
  if (!(d instanceof Date) || isNaN(d)) return '—';
  return d.toLocaleString('pt-BR', {day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
}

// ─── Tab Switch ───────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if (name === 'history' && ALL_DATA) renderCharts(ALL_DATA);
}

// ─── Table Filter ─────────────────────────────────────────────
function filterTable(tableId, q) {
  const t = document.getElementById(tableId);
  const rows = t.querySelectorAll('tbody tr');
  const lq = q.toLowerCase();
  rows.forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(lq) ? '' : 'none';
  });
}

// ─── Table Sort ───────────────────────────────────────────────
function sortTable(tableId, colIdx) {
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr:not(.empty-row)'));
  if (!rows.length) return;

  const key = tableId + '_' + colIdx;
  const asc = sortState[key] !== true;
  sortState[key] = asc;

  // Update header icons
  table.querySelectorAll('th').forEach((th,i) => {
    th.classList.remove('sorted-asc','sorted-desc');
    if (i === colIdx) th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
  });

  rows.sort((a, b) => {
    const av = a.cells[colIdx]?.textContent.trim() || '';
    const bv = b.cells[colIdx]?.textContent.trim() || '';
    const an = parseFloat(av.replace(/\./g,'').replace(',','.'));
    const bn = parseFloat(bv.replace(/\./g,'').replace(',','.'));
    if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv,'pt-BR') : bv.localeCompare(av,'pt-BR');
  });

  rows.forEach(r => tbody.appendChild(r));
}
</script>
</body>
</html>
