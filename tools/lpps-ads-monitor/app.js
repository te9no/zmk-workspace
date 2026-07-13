import { parseAdsLine } from "./parser.js";

const $ = (id) => document.getElementById(id);
const elements = {
  status: $("status"), connect: $("connectButton"), demo: $("demoButton"),
  chart: $("chart"), xyPad: $("xyPad"), ch0: $("ch0Value"), ch1: $("ch1Value"),
  ch0Raw: $("ch0Raw"), ch1Raw: $("ch1Raw"),
  ch2: $("ch2Value"), ch3: $("ch3Value"), ch2Raw: $("ch2Raw"), ch3Raw: $("ch3Raw"),
  ch0Meter: $("ch0Meter"), ch1Meter: $("ch1Meter"), ch0Noise: $("ch0Noise"),
  ch2Meter: $("ch2Meter"), ch3Meter: $("ch3Meter"), ch1Noise: $("ch1Noise"),
  ch2Noise: $("ch2Noise"), ch3Noise: $("ch3Noise"), samples: $("sampleCount"), rate: $("sampleRate"),
  dropped: $("droppedLines"), elapsed: $("elapsed"), rawMode: $("rawMode"),
  xyX: $("xyX"), xyY: $("xyY"), range: $("rangeInput"), rangeValue: $("rangeValue"),
  window: $("windowInput"), windowValue: $("windowValue"), center: $("centerButton"),
  clear: $("clearButton"), export: $("exportButton"), log: $("serialLog"),
  lastLine: $("lastLine"),
};

const state = {
  port: null, reader: null, demoTimer: null, connected: false, samples: [], rawLines: [],
  dropped: 0, center0: 0, center1: 0, startedAt: 0, lastFrame: 0, rateWindow: [],
};

function setStatus(label, status = "idle") {
  elements.status.dataset.state = status;
  elements.status.lastChild.textContent = label;
}

function resetData() {
  state.samples = [];
  state.rawLines = [];
  state.dropped = 0;
  state.rateWindow = [];
  state.startedAt = performance.now();
  elements.log.textContent = "";
  updateReadout(null);
}

function centerCurrent() {
  const sample = state.samples.at(-1);
  if (!sample) return;
  state.center0 += sample.ch0;
  state.center1 += sample.ch1;
  state.samples = [];
}

function appendSample(sample) {
  const normalized = {
    ...sample,
    time: (sample.receivedAt - state.startedAt) / 1000,
    ch0: sample.ch0 - state.center0,
    ch1: sample.ch1 - state.center1,
  };
  state.samples.push(normalized);
  state.rateWindow.push(sample.receivedAt);
  const cutoff = sample.receivedAt - 2000;
  while (state.rateWindow[0] < cutoff) state.rateWindow.shift();
  const maxAge = Number(elements.window.value) + 2;
  while (state.samples.length > 2 && normalized.time - state.samples[0].time > maxAge) state.samples.shift();
  updateReadout(normalized);
}

function processLine(line) {
  const cleaned = line.trim();
  if (!cleaned) return;
  state.rawLines.push(cleaned);
  if (state.rawLines.length > 120) state.rawLines.shift();
  elements.lastLine.textContent = cleaned.replace(/\x1b\[[0-9;]*m/g, "").slice(-90);
  elements.log.textContent = state.rawLines.join("\n");
  elements.log.scrollTop = elements.log.scrollHeight;
  const sample = parseAdsLine(cleaned);
  if (sample) appendSample(sample);
  else state.dropped += 1;
}

async function connectSerial() {
  if (state.connected) return disconnect();
  if (!("serial" in navigator)) {
    setStatus("Web Serial非対応", "error");
    return;
  }
  try {
    const port = await navigator.serial.requestPort();
    await port.open({ baudRate: 115200, bufferSize: 65536 });
    await port.setSignals({ dataTerminalReady: true, requestToSend: false });
    state.port = port;
    state.connected = true;
    state.startedAt = performance.now();
    elements.connect.textContent = "切断";
    elements.demo.disabled = true;
    setStatus("接続中", "live");
    readLoop();
  } catch (error) {
    setStatus(error.name === "NotFoundError" ? "選択なし" : "接続失敗", "error");
    console.error(error);
  }
}

async function readLoop() {
  const decoder = new TextDecoderStream();
  const closed = state.port.readable.pipeTo(decoder.writable).catch(() => {});
  state.reader = decoder.readable.getReader();
  let pending = "";
  try {
    while (state.connected) {
      const { value, done } = await state.reader.read();
      if (done) break;
      pending += value;
      const lines = pending.split(/\r?\n/);
      pending = lines.pop() ?? "";
      lines.forEach(processLine);
    }
  } catch (error) {
    if (state.connected) setStatus("受信エラー", "error");
    console.error(error);
  } finally {
    state.reader?.releaseLock();
    await closed;
    if (state.connected) await disconnect();
  }
}

async function disconnect() {
  state.connected = false;
  if (state.reader) await state.reader.cancel().catch(() => {});
  if (state.port) await state.port.close().catch(() => {});
  state.reader = null;
  state.port = null;
  elements.connect.textContent = "接続";
  elements.demo.disabled = false;
  setStatus("未接続", "idle");
}

function toggleDemo() {
  if (state.demoTimer) {
    clearInterval(state.demoTimer);
    state.demoTimer = null;
    elements.demo.textContent = "デモ";
    setStatus("未接続", "idle");
    return;
  }
  resetData();
  elements.demo.textContent = "停止";
  setStatus("デモ入力", "demo");
  let t = 0;
  state.demoTimer = setInterval(() => {
    t += 0.1;
    const ch0 = Math.round(Math.sin(t * 1.7) * 260 + Math.sin(t * 5.1) * 18);
    const ch1 = Math.round(Math.cos(t * 1.2) * 190 + Math.sin(t * 4.3) * 14);
    const ch2 = Math.round(Math.sin(t * 0.8 + 1.4) * 150);
    const ch3 = Math.round(Math.cos(t * 1.5 + 0.7) * 110);
    processLine(`[00:00:00.000,000] <inf> analog_axis_hires: ADSCSV4,${Math.round(t * 1000)},${3950000 + ch0},${3950000 + ch1},${3950000 + ch2},${3950000 + ch3},${ch0},${ch1},${ch2},${ch3},0,0,0,0`);
  }, 100);
}

function stats(key) {
  const recent = state.samples.slice(-50).map((sample) => sample[key]).filter(Number.isFinite);
  if (!recent.length) return 0;
  const mean = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  return Math.sqrt(recent.reduce((sum, value) => sum + (value - mean) ** 2, 0) / recent.length);
}

function updateReadout(sample) {
  const ch0 = sample?.ch0 ?? 0;
  const ch1 = sample?.ch1 ?? 0;
  const ch2 = sample?.ch2;
  const ch3 = sample?.ch3;
  const range = Math.max(Number(elements.range.value), 1);
  elements.ch0.textContent = ch0.toLocaleString();
  elements.ch1.textContent = ch1.toLocaleString();
  elements.ch2.textContent = Number.isFinite(ch2) ? ch2.toLocaleString() : "--";
  elements.ch3.textContent = Number.isFinite(ch3) ? ch3.toLocaleString() : "--";
  elements.ch0Raw.textContent = sample?.raw0 == null ? "RAW --" : `RAW ${sample.raw0.toLocaleString()}`;
  elements.ch1Raw.textContent = sample?.raw1 == null ? "RAW --" : `RAW ${sample.raw1.toLocaleString()}`;
  const monitorVolts = (raw) => raw / 8388607 * 2.048 * 4;
  elements.ch2Raw.textContent = sample?.raw2 == null ? "VREF --" :
    `VREF ${monitorVolts(sample.raw2).toFixed(3)} V`;
  elements.ch3Raw.textContent = sample?.raw3 == null ? "AVDD --" :
    `AVDD ${monitorVolts(sample.raw3).toFixed(3)} V`;
  elements.ch0Meter.style.transform = `scaleX(${Math.min(Math.abs(ch0) / range, 1)})`;
  elements.ch1Meter.style.transform = `scaleX(${Math.min(Math.abs(ch1) / range, 1)})`;
  elements.ch2Meter.style.transform = `scaleX(${Math.min(Math.abs(ch2 ?? 0) / range, 1)})`;
  elements.ch3Meter.style.transform = `scaleX(${Math.min(Math.abs(ch3 ?? 0) / range, 1)})`;
  elements.ch0Meter.dataset.sign = ch0 < 0 ? "negative" : "positive";
  elements.ch1Meter.dataset.sign = ch1 < 0 ? "negative" : "positive";
  elements.ch2Meter.dataset.sign = (ch2 ?? 0) < 0 ? "negative" : "positive";
  elements.ch3Meter.dataset.sign = (ch3 ?? 0) < 0 ? "negative" : "positive";
  elements.ch0Noise.textContent = `σ ${stats("ch0").toFixed(1)}`;
  elements.ch1Noise.textContent = `σ ${stats("ch1").toFixed(1)}`;
  elements.ch2Noise.textContent = Number.isFinite(ch2) ? `σ ${stats("ch2").toFixed(1)}` : "σ --";
  elements.ch3Noise.textContent = Number.isFinite(ch3) ? `σ ${stats("ch3").toFixed(1)}` : "σ --";
  elements.samples.textContent = state.samples.length.toLocaleString();
  elements.rate.textContent = `${Math.max(0, (state.rateWindow.length - 1) / 2).toFixed(1)} Hz`;
  elements.dropped.textContent = `破棄 ${state.dropped}`;
  elements.rawMode.textContent = sample?.raw0 == null ? "delta" : "raw + delta";
  elements.xyX.textContent = `X ${ch0.toLocaleString()}`;
  elements.xyY.textContent = `Y ${ch1.toLocaleString()}`;
}

function resizeCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width * ratio));
  const height = Math.max(1, Math.floor(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  return { ctx: canvas.getContext("2d"), width, height, ratio };
}

function drawChart() {
  const { ctx, width, height, ratio } = resizeCanvas(elements.chart);
  const styles = getComputedStyle(document.documentElement);
  const grid = styles.getPropertyValue("--grid").trim();
  const foreground = styles.getPropertyValue("--ink-muted").trim();
  const xColor = styles.getPropertyValue("--ch0").trim();
  const yColor = styles.getPropertyValue("--ch1").trim();
  const zColor = styles.getPropertyValue("--ch2").trim();
  const wColor = styles.getPropertyValue("--ch3").trim();
  ctx.clearRect(0, 0, width, height);
  const pad = 34 * ratio;
  const range = Number(elements.range.value);
  const seconds = Number(elements.window.value);
  const now = state.samples.at(-1)?.time ?? 0;
  ctx.strokeStyle = grid;
  ctx.lineWidth = ratio;
  ctx.fillStyle = foreground;
  ctx.font = `${11 * ratio}px ui-monospace, monospace`;
  ctx.textAlign = "right";
  [-1, -0.5, 0, 0.5, 1].forEach((step) => {
    const y = pad + (1 - (step + 1) / 2) * (height - pad * 2);
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - 12 * ratio, y); ctx.stroke();
    ctx.fillText(String(Math.round(step * range)), pad - 6 * ratio, y + 4 * ratio);
  });
  const drawSeries = (key, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 2 * ratio; ctx.beginPath();
    let started = false;
    for (const sample of state.samples) {
      if (!Number.isFinite(sample[key])) continue;
      const age = now - sample.time;
      if (age > seconds) continue;
      const x = pad + (1 - age / seconds) * (width - pad - 12 * ratio);
      const y = height / 2 - (sample[key] / range) * (height / 2 - pad);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  };
  drawSeries("ch0", xColor); drawSeries("ch1", yColor);
  drawSeries("ch2", zColor); drawSeries("ch3", wColor);
}

function drawXY() {
  const { ctx, width, height, ratio } = resizeCanvas(elements.xyPad);
  const styles = getComputedStyle(document.documentElement);
  const grid = styles.getPropertyValue("--grid").trim();
  const accent = styles.getPropertyValue("--accent").trim();
  const sample = state.samples.at(-1) ?? { ch0: 0, ch1: 0 };
  const range = Math.max(Number(elements.range.value), 1);
  const cx = width / 2; const cy = height / 2; const radius = Math.min(width, height) * 0.39;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = grid; ctx.lineWidth = ratio;
  [1, 0.66, 0.33].forEach((scale) => { ctx.beginPath(); ctx.arc(cx, cy, radius * scale, 0, Math.PI * 2); ctx.stroke(); });
  ctx.beginPath(); ctx.moveTo(cx - radius, cy); ctx.lineTo(cx + radius, cy); ctx.moveTo(cx, cy - radius); ctx.lineTo(cx, cy + radius); ctx.stroke();
  const x = cx + Math.max(-1, Math.min(1, sample.ch0 / range)) * radius;
  const y = cy + Math.max(-1, Math.min(1, sample.ch1 / range)) * radius;
  ctx.fillStyle = accent; ctx.shadowColor = accent; ctx.shadowBlur = 16 * ratio;
  ctx.beginPath(); ctx.arc(x, y, 7 * ratio, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
}

function animationLoop(timestamp) {
  if (timestamp - state.lastFrame > 33) {
    drawChart(); drawXY();
    const elapsed = Math.max(0, timestamp - state.startedAt) / 1000;
    elements.elapsed.textContent = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(Math.floor(elapsed % 60)).padStart(2, "0")}`;
    state.lastFrame = timestamp;
  }
  requestAnimationFrame(animationLoop);
}

function exportCsv() {
  if (!state.samples.length) return;
  const rows = ["time_s,ch0,ch1,ch2,ch3,raw0,raw1,raw2,raw3,out0,out1,out2,out3,source"];
  for (const s of state.samples) rows.push([s.time.toFixed(3), s.ch0, s.ch1, s.ch2 ?? "", s.ch3 ?? "", s.raw0 ?? "", s.raw1 ?? "", s.raw2 ?? "", s.raw3 ?? "", s.out0 ?? "", s.out1 ?? "", s.out2 ?? "", s.out3 ?? "", s.source].join(","));
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
  link.download = `lpps-ads-${new Date().toISOString().replace(/[:.]/g, "-")}.csv`; link.click();
  URL.revokeObjectURL(link.href);
}

elements.connect.addEventListener("click", connectSerial);
elements.demo.addEventListener("click", toggleDemo);
elements.center.addEventListener("click", centerCurrent);
elements.clear.addEventListener("click", resetData);
elements.export.addEventListener("click", exportCsv);
elements.range.addEventListener("input", () => { elements.rangeValue.value = Number(elements.range.value).toLocaleString(); updateReadout(state.samples.at(-1)); });
elements.window.addEventListener("input", () => { elements.windowValue.value = `${elements.window.value}秒`; });
navigator.serial?.addEventListener("disconnect", () => state.connected && disconnect());
resetData();
requestAnimationFrame(animationLoop);
