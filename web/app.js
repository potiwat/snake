/**
 * AHM-CPG Snake Robot Interactive Dashboard Logic
 * Bioinspiration & Biomimetics (IOPscience, Q1)
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize KaTeX math rendering
  if (window.renderMathInElement) {
    renderMathInElement(document.body, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false }
      ],
      throwOnError: false
    });
  }

  // 2. Initialize Navigation Tabs
  initTabs();

  // 3. Initialize Interactive Kinematic Simulator
  initSimulator();

  // 4. Initialize Hill Receptor Explorer
  initHillExplorer();

  // 5. Initialize Statistical Benchmark Charts
  initBenchmarkCharts();
});

/* ==========================================================================
   NAVIGATION & TABS
   ========================================================================== */
function initTabs() {
  const tabBtns = document.querySelectorAll('.nav-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      switchTab(targetId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabId);
  });

  // Trigger resize on charts when tab becomes visible
  window.dispatchEvent(new Event('resize'));
}

/* ==========================================================================
   INTERACTIVE SIMULATOR (CANVAS & SYNCHRONIZED CHARTS)
   ========================================================================== */
let simState = {
  isPlaying: false,
  currentIndex: 0,
  speedMultiplier: 1.0,
  scenario: 'locked_j3',
  controller: 'C5',
  animationTimer: null,
  historyData: null
};

let jointChart = null;
let hormoneChart = null;

function initSimulator() {
  const canvas = document.getElementById('snakeCanvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const btnPlayPause = document.getElementById('btnPlayPause');
  const btnReset = document.getElementById('btnReset');
  const scrubber = document.getElementById('timeScrubber');
  const speedSlider = document.getElementById('simSpeed');
  const selScenario = document.getElementById('simScenario');
  const selController = document.getElementById('simController');

  // Event Listeners
  btnPlayPause.addEventListener('click', togglePlayPause);
  btnReset.addEventListener('click', resetSimulation);

  scrubber.addEventListener('input', (e) => {
    simState.currentIndex = parseInt(e.target.value, 10);
    updateFrame();
  });

  speedSlider.addEventListener('input', (e) => {
    simState.speedMultiplier = parseFloat(e.target.value);
    document.getElementById('speedVal').textContent = `${simState.speedMultiplier.toFixed(2)}×`;
  });

  selScenario.addEventListener('change', (e) => {
    simState.scenario = e.target.value;
    loadSimulationData();
  });

  selController.addEventListener('change', (e) => {
    simState.controller = e.target.value;
    loadSimulationData();
  });

  // Initialize live telemetry charts
  initTelemetryCharts();

  // Load initial data
  loadSimulationData();
}

function loadSimulationData() {
  if (window.DASHBOARD_DATA && window.DASHBOARD_DATA.histories) {
    const scenHist = window.DASHBOARD_DATA.histories[simState.scenario] || {};
    simState.historyData = scenHist[simState.controller] || null;
  }
  simState.currentIndex = 0;
  updateFrame();
}

function togglePlayPause() {
  simState.isPlaying = !simState.isPlaying;
  const btn = document.getElementById('btnPlayPause');
  btn.textContent = simState.isPlaying ? '❚❚ Pause' : '▶ Play';

  if (simState.isPlaying) {
    playLoop();
  } else {
    cancelAnimationFrame(simState.animationTimer);
  }
}

function resetSimulation() {
  simState.isPlaying = false;
  document.getElementById('btnPlayPause').textContent = '▶ Play';
  cancelAnimationFrame(simState.animationTimer);
  simState.currentIndex = 0;
  updateFrame();
}

let lastTimestamp = 0;
function playLoop(timestamp) {
  if (!simState.isPlaying) return;

  if (!lastTimestamp) lastTimestamp = timestamp;
  const elapsed = timestamp - lastTimestamp;

  // Target 10 Hz frame rate scaled by multiplier (each step is 0.1s in downsampled history)
  if (elapsed >= (100 / simState.speedMultiplier)) {
    lastTimestamp = timestamp;
    simState.currentIndex++;
    if (simState.historyData && simState.historyData.time && simState.currentIndex >= simState.historyData.time.length) {
      simState.currentIndex = 0; // Loop around
    }
    updateFrame();
  }

  simState.animationTimer = requestAnimationFrame(playLoop);
}

function updateFrame() {
  const canvas = document.getElementById('snakeCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const scrubber = document.getElementById('timeScrubber');
  const timeVal = document.getElementById('timeVal');
  const faultStatusBox = document.getElementById('faultStatusBox');
  const statusIndicator = document.getElementById('statusIndicator');
  const statusText = document.getElementById('statusText');

  const telemetrySpeed = document.getElementById('telemetrySpeed');
  const telemetryHG = document.getElementById('telemetryHG');
  const telemetryPos = document.getElementById('telemetryPos');

  const hist = simState.historyData;
  if (!hist || !hist.time || hist.time.length === 0) {
    drawEmptyCanvas(ctx, canvas);
    return;
  }

  const idx = Math.min(simState.currentIndex, hist.time.length - 1);
  const currentTime = hist.time[idx];

  // Update controls display
  scrubber.value = idx;
  timeVal.textContent = `${currentTime.toFixed(1)} s`;

  // Check fault state (Fault injected at 18.0s)
  const isFaultActive = currentTime >= 18.0;
  if (isFaultActive) {
    statusIndicator.className = 'status-indicator fault';
    if (simState.scenario === 'locked_j3') {
      statusText.textContent = 'FAULT ACTIVE: Joint 4 Locked (0 rad)';
    } else if (simState.scenario === 'dual_locked_j3_j4') {
      statusText.textContent = 'FAULT ACTIVE: Joints 4 & 5 Locked';
    } else if (simState.scenario === 'dynamic_friction') {
      statusText.textContent = 'DYNAMIC TRANSITION: Low-Friction Slippery Ice';
    }
  } else {
    statusIndicator.className = 'status-indicator';
    statusText.textContent = 'PRE-FAULT STEADY GAIT (1.0 Hz Wave)';
  }

  // Telemetry updates
  const curSpeed = hist.speed[idx] !== undefined ? hist.speed[idx] : 0.0;
  const curPos = hist.pos[idx] || [0.0, 0.0];
  const curHormones = hist.hormones[idx] || new Array(8).fill(0);
  const curHG = curHormones.length > 0 ? (curHormones.reduce((a, b) => a + b, 0) / curHormones.length) : 0;

  telemetrySpeed.textContent = `${curSpeed.toFixed(3)} m/s`;
  telemetryHG.textContent = `${curHG.toFixed(3)}`;
  telemetryPos.textContent = `(${curPos[0].toFixed(2)}, ${curPos[1].toFixed(2)}) m`;

  // Render 2D Snake Kinematics on Canvas
  renderSnake(ctx, canvas, hist, idx, isFaultActive);

  // Update synchronized telemetry mini-charts
  updateTelemetryCharts(hist, idx, curHormones);
}

function drawEmptyCanvas(ctx, canvas) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#8b949e';
  ctx.font = '14px Inter';
  ctx.textAlign = 'center';
  ctx.fillText('No trajectory history loaded for this scenario.', canvas.width / 2, canvas.height / 2);
}

function renderSnake(ctx, canvas, hist, idx, isFaultActive) {
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Draw background grid lines (world reference)
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
  ctx.lineWidth = 1;
  const gridSize = 40;
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
  }

  // Draw Ground Trajectory Trail
  if (hist.pos && hist.pos.length > 0) {
    ctx.strokeStyle = 'rgba(56, 139, 253, 0.35)';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();

    // World to canvas coordinate transform (Scale fits 12m forward path on canvas)
    const scale = 35; // pixels per meter
    const originX = w * 0.45;
    const originY = h * 0.85;

    for (let i = 0; i <= idx; i++) {
      const p = hist.pos[i];
      const cx = originX + p[0] * scale;
      const cy = originY + p[1] * scale; // p[1] is negative in PyBullet, so +p[1] moves upwards!
      if (i === 0) ctx.moveTo(cx, cy);
      else ctx.lineTo(cx, cy);
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Kinematic Model: 9 links, 8 joints
  const numLinks = 9;
  const linkLength = 16; // pixels
  const jointAngles = hist.q_act[idx] || new Array(8).fill(0);
  const headPos = hist.pos[idx] || [0.0, 0.0];

  const scale = 35;
  const originX = w * 0.45;
  const originY = h * 0.85;

  // Base head position and orientation on canvas (Moving upwards)
  let currentX = originX + headPos[0] * scale;
  let currentY = originY + headPos[1] * scale;
  let currentHeading = Math.PI / 2; // Moving predominantly upwards (+Y in canvas)

  const jointCoords = [];
  jointCoords.push({ x: currentX, y: currentY, heading: currentHeading });

  for (let i = 0; i < 8; i++) {
    const q = jointAngles[i] || 0;
    currentHeading += q;
    currentX += linkLength * Math.sin(currentHeading);
    currentY += linkLength * Math.cos(currentHeading);
    jointCoords.push({ x: currentX, y: currentY, heading: currentHeading });
  }

  // Draw Snake Body Segments (Pills)
  for (let i = 0; i < jointCoords.length - 1; i++) {
    const p1 = jointCoords[i];
    const p2 = jointCoords[i + 1];

    ctx.strokeStyle = '#1f6feb';
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();

    // Inner core
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }

  // Draw Dynamic Spinal Bypass Bridge if C5 & Fault Active
  if (isFaultActive && (simState.controller === 'C5' || simState.controller === 'C4')) {
    if (simState.scenario === 'locked_j3') {
      // Bypass connects Joint 3 (index 2) to Joint 5 (index 4)
      const pPrev = jointCoords[2];
      const pNext = jointCoords[4];
      ctx.strokeStyle = '#2ea043';
      ctx.lineWidth = 3;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(pPrev.x, pPrev.y);
      ctx.lineTo(pNext.x, pNext.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // Draw Joint Nodes
  for (let i = 0; i < jointCoords.length; i++) {
    const p = jointCoords[i];
    ctx.fillStyle = '#388bfd';
    let radius = 6;

    // Highlight Head
    if (i === 0) {
      ctx.fillStyle = '#ffffff';
      radius = 9;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, 2 * Math.PI);
      ctx.fill();

      // Eyes
      ctx.fillStyle = '#0d1117';
      ctx.beginPath();
      ctx.arc(p.x - 3, p.y - 3, 2, 0, 2 * Math.PI);
      ctx.arc(p.x + 3, p.y - 3, 2, 0, 2 * Math.PI);
      ctx.fill();
      continue;
    }

    // Joint indices 1 to 8 map to 0-indexed joints 0 to 7
    const jIdx = i - 1;
    let isDamaged = false;
    if (isFaultActive) {
      if (simState.scenario === 'locked_j3' && jIdx === 3) isDamaged = true;
      if (simState.scenario === 'dual_locked_j3_j4' && (jIdx === 3 || jIdx === 4)) isDamaged = true;
    }

    if (isDamaged) {
      ctx.fillStyle = '#f85149'; // Red for fault
      radius = 8;
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();
    } else {
      ctx.fillStyle = '#388bfd';
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
}

function initTelemetryCharts() {
  // 1. Joint Angles Line Chart
  const ctxAngles = document.getElementById('jointAngleChart').getContext('2d');
  jointChart = new Chart(ctxAngles, {
    type: 'line',
    data: {
      labels: ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8'],
      datasets: [{
        label: 'Joint Angles q (rad)',
        data: [0, 0, 0, 0, 0, 0, 0, 0],
        borderColor: '#388bfd',
        backgroundColor: 'rgba(56, 139, 253, 0.15)',
        borderWidth: 2,
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { min: -1.1, max: 1.1, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { color: 'rgba(255,255,255,0.05)' } }
      },
      plugins: { legend: { display: false } }
    }
  });

  // 2. Hormone Bar Chart
  const ctxHormone = document.getElementById('hormoneBarChart').getContext('2d');
  hormoneChart = new Chart(ctxHormone, {
    type: 'bar',
    data: {
      labels: ['J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8'],
      datasets: [{
        label: 'Hormone Level H_i',
        data: [0, 0, 0, 0, 0, 0, 0, 0],
        backgroundColor: '#d29922',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { min: 0.0, max: 1.0, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { color: 'rgba(255,255,255,0.05)' } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function updateTelemetryCharts(hist, idx, curHormones) {
  if (jointChart && hist.q_act && hist.q_act[idx]) {
    jointChart.data.datasets[0].data = hist.q_act[idx];
    jointChart.update('none'); // Update without animation for smooth 60fps
  }
  if (hormoneChart && curHormones) {
    hormoneChart.data.datasets[0].data = curHormones;
    hormoneChart.update('none');
  }
}

/* ==========================================================================
   HILL RECEPTOR EXPLORER
   ========================================================================== */
let hillChart = null;

function initHillExplorer() {
  const ctxHill = document.getElementById('hillCurveChart').getContext('2d');
  const sliderM = document.getElementById('sliderHillM');
  const sliderKh = document.getElementById('sliderHillKh');
  const valM = document.getElementById('valHillM');
  const valKh = document.getElementById('valHillKh');

  function computeHillData(m, Kh) {
    const H_vals = [];
    const R_vals = [];
    for (let h = 0.0; h <= 1.0; h += 0.02) {
      H_vals.push(h.toFixed(2));
      const r = Math.pow(h, m) / (Math.pow(Kh, m) + Math.pow(h, m) + 1e-9);
      R_vals.push(r);
    }
    return { H_vals, R_vals };
  }

  const initial = computeHillData(4.0, 0.65);

  hillChart = new Chart(ctxHill, {
    type: 'line',
    data: {
      labels: initial.H_vals,
      datasets: [{
        label: 'Receptor Activation R(H)',
        data: initial.R_vals,
        borderColor: '#2ea043',
        backgroundColor: 'rgba(46, 160, 67, 0.2)',
        borderWidth: 3,
        fill: true,
        pointRadius: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          title: { display: true, text: 'Local Hormone Concentration H_i', color: '#8b949e' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        },
        y: {
          min: 0, max: 1.05,
          title: { display: true, text: 'Hill Receptor State R_i', color: '#8b949e' },
          grid: { color: 'rgba(255,255,255,0.05)' }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });

  function updateHillPlot() {
    const m = parseFloat(sliderM.value);
    const Kh = parseFloat(sliderKh.value);
    valM.textContent = m.toFixed(1);
    valKh.textContent = Kh.toFixed(2);

    const updated = computeHillData(m, Kh);
    hillChart.data.labels = updated.H_vals;
    hillChart.data.datasets[0].data = updated.R_vals;
    hillChart.update();
  }

  sliderM.addEventListener('input', updateHillPlot);
  sliderKh.addEventListener('input', updateHillPlot);
}

/* ==========================================================================
   STATISTICAL BENCHMARK CHARTS
   ========================================================================== */
function initBenchmarkCharts() {
  const data = window.DASHBOARD_DATA || {};
  const bench = data.benchmark || {};
  const gen = data.generalization || {};
  const abl = data.ablation || {};

  const ctrls = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6'];
  const colors = ['#8b949e', '#f85149', '#d29922', '#e3b341', '#3fb950', '#58a6ff'];

  // 1. Recovery Ratio Bar Chart
  const ctxRec = document.getElementById('benchmarkRecoveryChart').getContext('2d');
  const recData = ctrls.map(c => bench[c] ? bench[c].recovery_ratio.mean : 0);

  new Chart(ctxRec, {
    type: 'bar',
    data: {
      labels: ['C1: Fixed', 'C2: Error-Adapt', 'C3: Shape Rec', 'C4: Oracle', 'C5: Proposed AHM ⭐', 'C6: AHM No-Bypass'],
      datasets: [{
        label: 'Speed Recovery Ratio (%)',
        data: recData,
        backgroundColor: colors,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: 'Recovery Ratio (%)', color: '#8b949e' }, min: 0, max: 75, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });

  // 2. Cost of Transport (COT) Bar Chart
  const ctxCot = document.getElementById('benchmarkCotChart').getContext('2d');
  const cotData = ctrls.map(c => bench[c] ? bench[c].cot.mean : 0);

  new Chart(ctxCot, {
    type: 'bar',
    data: {
      labels: ['C1: Fixed', 'C2: Error-Adapt', 'C3: Shape Rec', 'C4: Oracle', 'C5: Proposed AHM ⭐', 'C6: AHM No-Bypass'],
      datasets: [{
        label: 'Cost of Transport (Lower is Better)',
        data: cotData,
        backgroundColor: colors,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: 'COT (Dimensionless)', color: '#8b949e' }, min: 0, max: 55, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });

  // 3. Generalization Bar Chart (Incline 10 deg vs High Slip)
  const ctxGen = document.getElementById('generalizationChart').getContext('2d');
  const inclineData = ctrls.map(c => gen['incline_10deg'] && gen['incline_10deg'][c] ? gen['incline_10deg'][c].mean : 0);
  const slipData = ctrls.map(c => gen['high_slip'] && gen['high_slip'][c] ? gen['high_slip'][c].mean : 0);

  new Chart(ctxGen, {
    type: 'bar',
    data: {
      labels: ['C1', 'C2', 'C3', 'C4', 'C5 (Ours)', 'C6'],
      datasets: [
        { label: '10° Slope Incline', data: inclineData, backgroundColor: '#388bfd', borderRadius: 4 },
        { label: 'High-Slip Friction', data: slipData, backgroundColor: '#d29922', borderRadius: 4 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: 'Recovery Ratio (%)', color: '#8b949e' }, min: 0, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { labels: { color: '#f0f6fc' } } }
    }
  });

  // 4. Ablation Study Bar Chart
  const ctxAbl = document.getElementById('ablationChart').getContext('2d');
  const ablLabels = [];
  const ablData = [];
  for (let k in abl) {
    ablLabels.push(abl[k].name);
    ablData.push(abl[k].eta_rec_mean);
  }

  new Chart(ctxAbl, {
    type: 'bar',
    data: {
      labels: ablLabels.length > 0 ? ablLabels : ['Full C5', 'Dh=0', 'm=1 (Linear)', 'KB=0 (No Bypass)', 'gw=0'],
      datasets: [{
        label: 'Ablation Speed Recovery (%)',
        data: ablData.length > 0 ? ablData : [60.5, 61.9, 58.2, 51.0, 56.4],
        backgroundColor: '#bc8cff',
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { title: { display: true, text: 'Mean Recovery Ratio (%)', color: '#8b949e' }, min: 40, max: 70, grid: { color: 'rgba(255,255,255,0.05)' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

/* ==========================================================================
   CLIPBOARD UTILITIES
   ========================================================================== */
function copyBibtex() {
  const code = document.getElementById('bibtexCode').innerText;
  navigator.clipboard.writeText(code).then(() => {
    const btn = document.querySelector('.btn-copy');
    btn.textContent = '✅ Copied to Clipboard!';
    setTimeout(() => {
      btn.textContent = '📋 Copy Citation';
    }, 2500);
  });
}
