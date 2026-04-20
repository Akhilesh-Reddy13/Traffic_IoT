/**
 * Traffic Density Controller — Dashboard Client
 * Connects via WebSocket to receive annotated frames and traffic state.
 */
(function () {
  "use strict";

  // ── DOM refs ────────────────────────────────────────────
  const $  = (id) => document.getElementById(id);
  const videoFrame   = $("videoFrame");
  const videoOverlay = $("videoOverlay");
  const statusDot    = $("statusDot");
  const statusLabel  = $("statusLabel");
  const fpsValue     = $("fpsValue");
  const totalVehicles= $("totalVehicles");
  const sourceBadge  = $("sourceBadge");

  // Signals
  const lights = {
    lane_1: { red: $("lightA_red"), yellow: $("lightA_yellow"), green: $("lightA_green") },
    lane_2: { red: $("lightB_red"), yellow: $("lightB_yellow"), green: $("lightB_green") },
  };
  const timerA = $("timerA"), timerB = $("timerB");
  const allocA = $("allocA"), allocB = $("allocB");

  // Density
  const barA = $("barA"), barB = $("barB");
  const countA = $("countA"), countB = $("countB");
  const badgeA = $("badgeA"), badgeB = $("badgeB");

  // Chart
  const chartCanvas = $("densityChart");
  const chartCtx    = chartCanvas.getContext("2d");

  // Settings
  const settingsToggle = $("settingsToggle");
  const settingsBody   = $("settingsBody");
  const settingsIcon   = $("settingsIcon");
  const inputSource    = $("inputSource");
  const inputConf      = $("inputConf");
  const confValue      = $("confValue");
  const inputGpu       = $("inputGpu");
  const btnApply       = $("btnApply");

  // ── Chart history ───────────────────────────────────────
  const MAX_HISTORY = 60;
  const historyA = [];
  const historyB = [];

  // ── WebSocket ───────────────────────────────────────────
  let ws = null;
  let reconnectTimer = null;

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => {
      statusDot.classList.add("connected");
      statusLabel.textContent = "Connected";
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    ws.onclose = () => {
      statusDot.classList.remove("connected");
      statusLabel.textContent = "Reconnecting…";
      reconnectTimer = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        render(data);
      } catch (e) {
        console.error("Parse error:", e);
      }
    };
  }

  // ── Render state ────────────────────────────────────────
  function render(state) {
    // 1. Video frame
    if (state.frame) {
      videoFrame.src = "data:image/jpeg;base64," + state.frame;
      videoOverlay.classList.add("hidden");
    }

    // 2. Stats
    fpsValue.textContent = state.fps ?? "--";
    totalVehicles.textContent = state.total_vehicles ?? 0;

    // 3. Traffic signals
    if (state.signal_state && state.signal_state.signals) {
      const sigs = state.signal_state.signals;
      updateSignal("lane_1", sigs.lane_1, timerA, allocA);
      updateSignal("lane_2", sigs.lane_2, timerB, allocB);
    }

    // 4. Lane density
    const counts = state.lane_counts || {};
    const density = state.density || {};
    updateDensity(counts.lane_1 || 0, density.lane_1 || "empty", barA, countA, badgeA);
    updateDensity(counts.lane_2 || 0, density.lane_2 || "empty", barB, countB, badgeB);

    // 5. Chart
    historyA.push(counts.lane_1 || 0);
    historyB.push(counts.lane_2 || 0);
    if (historyA.length > MAX_HISTORY) historyA.shift();
    if (historyB.length > MAX_HISTORY) historyB.shift();
    drawChart();
  }

  function updateSignal(laneId, sig, timerEl, allocEl) {
    if (!sig) return;
    const l = lights[laneId];
    l.red.classList.toggle("active", sig.state === "red");
    l.yellow.classList.toggle("active", sig.state === "yellow");
    l.green.classList.toggle("active", sig.state === "green");

    if (sig.state === "green" || sig.state === "yellow") {
      timerEl.textContent = sig.time_remaining.toFixed(1) + "s";
    } else {
      timerEl.textContent = "—";
    }
    allocEl.textContent = sig.green_time;
  }

  function updateDensity(count, level, bar, countEl, badge) {
    const pct = Math.min(100, (count / 15) * 100);
    bar.style.width = pct + "%";

    // Color class
    bar.className = "bar-fill";
    if (level === "medium") bar.classList.add("medium");
    else if (level === "high" || level === "critical") bar.classList.add(level);

    countEl.textContent = count;

    badge.textContent = level;
    badge.className = "density-badge";
    if (level !== "empty" && level !== "low") badge.classList.add(level);
  }

  // ── Mini Chart ──────────────────────────────────────────
  function drawChart() {
    const W = chartCanvas.width  = chartCanvas.clientWidth * 2;
    const H = chartCanvas.height = chartCanvas.clientHeight * 2;
    chartCtx.clearRect(0, 0, W, H);

    const pad = { t: 16, r: 16, b: 24, l: 36 };
    const cw = W - pad.l - pad.r;
    const ch = H - pad.t - pad.b;

    const maxVal = Math.max(8, ...historyA, ...historyB);

    // Grid lines
    chartCtx.strokeStyle = "rgba(255,255,255,0.05)";
    chartCtx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.t + (ch / 4) * i;
      chartCtx.beginPath();
      chartCtx.moveTo(pad.l, y);
      chartCtx.lineTo(W - pad.r, y);
      chartCtx.stroke();
    }

    // Y-axis labels
    chartCtx.fillStyle = "rgba(255,255,255,0.25)";
    chartCtx.font = "18px Inter";
    chartCtx.textAlign = "right";
    for (let i = 0; i <= 4; i++) {
      const val = Math.round(maxVal * (1 - i / 4));
      const y = pad.t + (ch / 4) * i + 6;
      chartCtx.fillText(val, pad.l - 8, y);
    }

    drawLine(historyA, maxVal, cw, ch, pad, "rgba(72,209,204,0.9)", "rgba(72,209,204,0.08)");
    drawLine(historyB, maxVal, cw, ch, pad, "rgba(255,107,53,0.9)", "rgba(255,107,53,0.08)");

    // Legend
    chartCtx.font = "bold 17px Inter";
    chartCtx.fillStyle = "rgba(72,209,204,0.9)";
    chartCtx.textAlign = "left";
    chartCtx.fillText("● Dir A", pad.l, H - 4);
    chartCtx.fillStyle = "rgba(255,107,53,0.9)";
    chartCtx.fillText("● Dir B", pad.l + 90, H - 4);
  }

  function drawLine(data, maxVal, cw, ch, pad, color, fillColor) {
    if (data.length < 2) return;
    const ctx = chartCtx;
    const step = cw / (MAX_HISTORY - 1);

    ctx.beginPath();
    data.forEach((v, i) => {
      const x = pad.l + i * step;
      const y = pad.t + ch - (v / maxVal) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    ctx.stroke();

    // Fill under curve
    const lastX = pad.l + (data.length - 1) * step;
    ctx.lineTo(lastX, pad.t + ch);
    ctx.lineTo(pad.l, pad.t + ch);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }

  // ── Settings Panel ──────────────────────────────────────
  settingsToggle.addEventListener("click", () => {
    settingsBody.classList.toggle("open");
    settingsIcon.classList.toggle("open");
  });

  inputConf.addEventListener("input", () => {
    confValue.textContent = parseFloat(inputConf.value).toFixed(2);
  });

  btnApply.addEventListener("click", async () => {
    const body = {};
    if (inputSource.value.trim()) body.video_source = inputSource.value.trim();
    body.confidence = parseFloat(inputConf.value);
    body.use_gpu = inputGpu.checked;

    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        btnApply.textContent = "✓ Applied";
        setTimeout(() => (btnApply.textContent = "Apply Settings"), 1500);
      }
    } catch (e) {
      console.error("Settings error:", e);
    }
  });

  // ── Init ────────────────────────────────────────────────
  connect();
})();
