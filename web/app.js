import { imagePoint, distance, calibratedScale, zoomAt } from './geometry.js';

const $ = (id) => document.getElementById(id);
const canvas = $('viewer');
const ctx = canvas.getContext('2d');
const source = document.createElement('canvas');
const pixels = source.getContext('2d', { willReadFrequently: true });
let hasImage = false;
let imageName = '';
let view = { x: 0, y: 0, scale: 1 };
let line = null;
let micrometersPerPixel = null;
let measureMode = false;
let showCrosshair = false;
let drag = null;
let report = null;
let checking = false;
let loadSequence = 0;
let live = false;
let liveGeneration = 0;
let liveBusy = false;
let settingsQueue = Promise.resolve();
let settingsPending = 0;
let processingBusy = false;
let whiteBalanceGains = [1, 1, 1];
let sourceDisplayMode = 'raw';
let sourceType = 'camera';
let sourceRecordedFile = '';
const replayMode = () => report?.acquisition?.source_type === 'replay';
const streamingImage = () => /^(LIVE|REPLAY) ·/.test($('source-tag').textContent);

function feedback(message, error = false) {
  $('feedback').textContent = message;
  $('feedback').classList.toggle('error', error);
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

async function refreshStatus() {
  if (checking) return;
  checking = true;
  $('refresh').disabled = true;
  try {
    const response = await fetch('/api/status', { signal: AbortSignal.timeout(10000) });
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    report = await response.json();
    const connected = report.usb_state === 'connected';
    const unknown = report.usb_state === 'unknown';
    const replay = replayMode();
    $('refresh').title = replay ? 'Refresh replay status' : 'Refresh USB status';
    $('refresh').setAttribute('aria-label', $('refresh').title);
    $('connection-text').textContent = replay ? 'Offline replay · camera not used' : connected ? (report.capture_available ? 'USB connected · native SDK' : 'USB detected · SDK unavailable') : unknown ? 'USB status unavailable' : 'Camera disconnected';
    $('status-dot').className = `dot ${connected || replay ? 'connected' : 'error'}`;
    $('device-state').textContent = replay ? 'Recorded data' : connected ? (report.capture_available ? 'Ready for capture' : 'Build the SDK to capture') : unknown ? 'Unable to check USB' : 'Camera not detected';
    $('device-message').textContent = report.message;
    $('live-view').disabled = !report.capture_available || liveBusy;
    $('acquisition-controls').disabled = replay || !report.capture_available || liveBusy;
    $('recording-field').hidden = !replay;
    $('recording').disabled = !report.capture_available || liveBusy;
    $('acquisition-note').textContent = replay
      ? 'Exposure and gain were fixed at capture. Choose a recording to compare settings. Playback loops the saved frames.'
      : 'Exposure is in sensor lines; its duration changes with resolution.';
    if (!live) $('live-view').textContent = replay ? '▶ Play recording' : '▶ Start live view';
    $('empty-message').textContent = replay ? 'Play the saved raw frames to inspect and measure them. No camera connection is needed.' : 'Open a microscope image to inspect and measure it. Start live view to inspect the connected camera.';
    if (replay && !liveBusy) {
      const choices = report.acquisition.recordings;
      const optionsKey = JSON.stringify(choices);
      if ($('recording').dataset.optionsKey !== optionsKey) {
        $('recording').replaceChildren(...choices.map(choice => {
          const option = document.createElement('option');
          option.value = choice.id;
          option.textContent = `${choice.resolution.replace('x', ' × ')} · ${choice.settings.exposure_lines} lines · gain ${choice.settings.gain} · ${choice.frame_count} frames`;
          return option;
        }));
        $('recording').dataset.optionsKey = optionsKey;
      }
      $('recording').value = report.acquisition.recording_id;
    }
    $('color-controls').disabled = !report.capture_available || processingBusy;
    if (!processingBusy) updateProcessingControls(report.acquisition);
    if (live && !liveBusy && !report.acquisition.running) finishLive();
    if (report.acquisition && !settingsPending && !liveBusy && !['exposure', 'gain', 'resolution'].includes(document.activeElement?.id)) {
      $('exposure').value = report.acquisition.settings.exposure_lines;
      $('gain').value = report.acquisition.settings.gain;
      $('resolution').value = report.acquisition.resolution;
      $('exposure-value').textContent = `${$('exposure').value} lines`;
      $('gain-value').textContent = $('gain').value;
    }
    const device = report.devices[0];
    const rows = replay ? {
      'Source': 'Recorded RAW8 RGGB · USB disabled',
      'Dataset': report.acquisition.dataset,
      'Scene': report.acquisition.description,
      'Playback': report.capture_state,
      'Frame size': `${report.acquisition.width} × ${report.acquisition.height}`,
    } : {
      'USB ID': '0547:c004',
      'USB name': device?.name ?? '—',
      'Vendor string': device?.manufacturer ?? '—',
      'Serial number': device?.serial ?? 'Not reported',
      'Link speed': device?.link_mbps ? `${device.link_mbps} Mb/s` : '—',
      'Interface': device?.interface_classes.includes(255) ? 'Vendor-specific (0xff)' : '—',
      'Host': `${report.platform} / ${report.architecture}`,
      'Live capture': report.capture_state,
      'SDK preview': `${report.acquisition.width} × ${report.acquisition.height} · ${report.acquisition.preview}`,
    };
    $('device-details').replaceChildren();
    for (const [label, value] of Object.entries(rows)) {
      const dt = document.createElement('dt'); dt.textContent = label;
      const dd = document.createElement('dd'); dd.textContent = value;
      $('device-details').append(dt, dd);
    }
  } catch (error) {
    report = null;
    $('live-view').disabled = true;
    $('acquisition-controls').disabled = true;
    $('color-controls').disabled = true;
    $('recording').disabled = true;
    $('connection-text').textContent = 'Local server unavailable';
    $('status-dot').className = 'dot error';
    $('device-state').textContent = 'Cannot read camera status';
    $('device-message').textContent = 'Run python3 server.py, then refresh the connection.';
    $('device-details').replaceChildren();
  } finally {
    checking = false;
    $('refresh').disabled = false;
    $('diagnostics').disabled = !report;
  }
}

function size() {
  return { width: $('stage').clientWidth, height: $('stage').clientHeight };
}

function fit() {
  if (!hasImage) return;
  const { width, height } = size();
  const scale = Math.min((width - 32) / source.width, (height - 32) / source.height);
  view = { scale, x: (width - source.width * scale) / 2, y: (height - source.height * scale) / 2 };
  render();
}

function resize() {
  const { width, height } = size();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  render();
}

function measurementText() {
  if (!line) return '— px';
  const length = distance(line);
  return micrometersPerPixel === null ? `${length.toFixed(1)} px` : `${(length * micrometersPerPixel).toFixed(2)} µm`;
}

function updateMeasurement() {
  $('measurement').textContent = measurementText();
  $('clear').disabled = live || !line;
  $('calibrate').disabled = live || !line || distance(line) < 1;
  $('reset-scale').disabled = live || micrometersPerPixel === null;
  $('measure').disabled = live || !hasImage;
  $('known-distance').disabled = live || !hasImage;
  $('scale-tag').textContent = micrometersPerPixel === null ? 'PIXELS' : 'CALIBRATED';
  $('scale-value').textContent = micrometersPerPixel === null ? 'Not set' : `${micrometersPerPixel.toPrecision(5)} µm/px`;
  $('calibration-note').textContent = micrometersPerPixel === null
    ? 'No calibration. Measurements are in image pixels.'
    : `${micrometersPerPixel.toPrecision(5)} µm per image pixel. Valid for this image’s optical setup.`;
}

function drawLine(target, scale, offsetX, offsetY, textScale = 1) {
  if (!line || distance(line) < 1) return;
  const a = { x: offsetX + line.a.x * scale, y: offsetY + line.a.y * scale };
  const b = { x: offsetX + line.b.x * scale, y: offsetY + line.b.y * scale };
  target.save();
  target.strokeStyle = '#d5fba9';
  target.fillStyle = '#d5fba9';
  target.lineWidth = 2 * textScale;
  target.beginPath(); target.moveTo(a.x, a.y); target.lineTo(b.x, b.y); target.stroke();
  for (const p of [a, b]) {
    target.beginPath(); target.arc(p.x, p.y, 3 * textScale, 0, Math.PI * 2); target.fill();
  }
  target.font = `${12 * textScale}px -apple-system, sans-serif`;
  const text = measurementText();
  const textWidth = target.measureText(text).width;
  const bounds = target === ctx ? size() : { width: source.width, height: source.height };
  const x = Math.max(0, Math.min(bounds.width - textWidth - 14 * textScale, (a.x + b.x) / 2 - textWidth / 2 - 7 * textScale));
  const y = Math.max(0, Math.min(bounds.height - 24 * textScale, (a.y + b.y) / 2 - 30 * textScale));
  target.fillStyle = '#162116'; target.fillRect(x, y, textWidth + 14 * textScale, 24 * textScale);
  target.fillStyle = '#d5fba9'; target.fillText(text, x + 7 * textScale, y + 16 * textScale);
  target.restore();
}

function render() {
  const { width, height } = size();
  ctx.clearRect(0, 0, width, height);
  if (!hasImage) return;
  ctx.imageSmoothingEnabled = view.scale < 2;
  ctx.drawImage(source, view.x, view.y, source.width * view.scale, source.height * view.scale);
  if (showCrosshair) {
    const x = view.x + source.width * view.scale / 2;
    const y = view.y + source.height * view.scale / 2;
    ctx.save(); ctx.strokeStyle = '#d5fba980'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, view.y); ctx.lineTo(x, view.y + source.height * view.scale);
    ctx.moveTo(view.x, y); ctx.lineTo(view.x + source.width * view.scale, y); ctx.stroke(); ctx.restore();
  }
  drawLine(ctx, view.scale, view.x, view.y);
  $('zoom-value').textContent = `${Math.round(view.scale * 100)}%`;
  updateMeasurement();
}

function histogram() {
  const data = pixels.getImageData(0, 0, source.width, source.height).data;
  const bins = new Array(256).fill(0);
  let total = 0;
  let count = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] === 0) continue;
    const luminance = Math.round(0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]);
    bins[luminance]++; total += luminance; count++;
  }
  const histogramCanvas = $('histogram');
  const plot = histogramCanvas.getContext('2d');
  const { width, height } = histogramCanvas;
  plot.clearRect(0, 0, width, height);
  const maximum = Math.max(...bins, 1);
  plot.fillStyle = '#a8c28e';
  bins.forEach((bin, i) => {
    const barHeight = bin / maximum * (height - 3);
    plot.fillRect(i * width / 256, height - barHeight, width / 256, barHeight);
  });
  $('mean').textContent = count ? `${(total / count).toFixed(1)} / 255` : 'Transparent';
}

async function openImage(file) {
  if (!file) return;
  if (file.size > 50 * 1024 * 1024) return feedback('Choose an image smaller than 50 MB.', true);
  if (!['image/png', 'image/jpeg', 'image/webp', 'image/bmp', 'image/x-ms-bmp'].includes(file.type)) {
    return feedback('Choose a PNG, JPEG, WebP, or BMP image.', true);
  }
  if (live) {
    try { await stopLive(); } catch (error) { feedback(error.message, true); return; }
  }
  const sequence = ++loadSequence;
  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    image.src = url;
    await image.decode();
    if (sequence !== loadSequence) return;
    if (image.naturalWidth * image.naturalHeight > 40_000_000) throw new Error('Choose an image with no more than 40 megapixels.');
    source.width = image.naturalWidth; source.height = image.naturalHeight;
    pixels.drawImage(image, 0, 0);
    hasImage = true; imageName = file.name; line = null; micrometersPerPixel = null; drag = null;
    $('known-distance').value = '';
    $('empty').hidden = true; canvas.hidden = false; $('image-hint').hidden = false;
    $('image-title').textContent = imageName;
    $('source-tag').textContent = 'IMPORTED IMAGE';
    $('dimensions').textContent = `${source.width} × ${source.height} px · imported image`;
    $('image-size').textContent = `${(source.width * source.height / 1_000_000).toFixed(2)} MP`;
    for (const id of ['fit', 'actual', 'zoom-in', 'zoom-out', 'crosshair', 'export', 'measure', 'known-distance']) $(id).disabled = false;
    resize(); fit(); histogram();
    feedback('Image opened locally. Draw a line to measure; set a known length to calibrate.');
  } catch (error) {
    if (sequence === loadSequence) feedback(error.message || 'This image could not be opened.', true);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function point(event) {
  const rect = canvas.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function inside(p) {
  return p.x >= 0 && p.y >= 0 && p.x < source.width && p.y < source.height;
}

function clampPoint(p) {
  return { x: Math.max(0, Math.min(source.width - 1, p.x)), y: Math.max(0, Math.min(source.height - 1, p.y)) };
}

function zoom(factor, anchor = { x: size().width / 2, y: size().height / 2 }) {
  if (!hasImage) return;
  view = zoomAt(view, anchor, factor); render();
}

canvas.addEventListener('pointerdown', (event) => {
  if (!hasImage || event.button !== 0) return;
  const p = point(event);
  const imageP = imagePoint(p, view);
  if (measureMode && !inside(imageP)) return;
  canvas.setPointerCapture(event.pointerId);
  drag = { start: p, view: { ...view }, measuring: measureMode };
  if (measureMode) { line = { a: imageP, b: imageP }; render(); }
});
canvas.addEventListener('pointermove', (event) => {
  if (!hasImage) return;
  const p = point(event);
  if (drag) {
    if (drag.measuring) line.b = clampPoint(imagePoint(p, view));
    else view = { ...view, x: drag.view.x + p.x - drag.start.x, y: drag.view.y + p.y - drag.start.y };
    render();
  }
  const imageP = imagePoint(p, view);
  if (inside(imageP)) {
    const x = Math.floor(imageP.x), y = Math.floor(imageP.y);
    const [r, g, b] = pixels.getImageData(x, y, 1, 1).data;
    $('cursor-value').textContent = `x ${x} · y ${y} · RGB ${r}, ${g}, ${b}`;
  } else $('cursor-value').textContent = 'Outside image';
});
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(event, () => { drag = null; });
canvas.addEventListener('wheel', (event) => {
  if (!hasImage) return;
  event.preventDefault(); zoom(Math.exp(-event.deltaY * 0.001), point(event));
}, { passive: false });
$('fit').onclick = fit;
$('actual').onclick = () => zoom(1 / view.scale);
$('zoom-in').onclick = () => zoom(1.25);
$('zoom-out').onclick = () => zoom(0.8);
$('crosshair').onclick = () => {
  showCrosshair = !showCrosshair; $('crosshair').setAttribute('aria-pressed', String(showCrosshair)); render();
};
$('measure').onclick = () => {
  measureMode = !measureMode; $('measure').setAttribute('aria-pressed', String(measureMode));
  canvas.classList.toggle('measuring', measureMode);
  $('image-hint').textContent = measureMode ? 'Drag across the image to measure' : 'Scroll to zoom · Drag to pan';
};
$('clear').onclick = () => { line = null; render(); };
$('calibrate').onclick = () => {
  try {
    micrometersPerPixel = calibratedScale(line, Number($('known-distance').value));
    render(); feedback('Scale set. New lines use this calibration until another image is opened.');
  } catch (error) { feedback(error.message, true); }
};
$('reset-scale').onclick = () => { micrometersPerPixel = null; $('known-distance').value = ''; render(); };
$('export').title = 'Save at full image resolution, including the measurement line. Crosshair is display-only.';
$('export').onclick = () => {
  if (!hasImage) return;
  const output = document.createElement('canvas'); output.width = source.width; output.height = source.height;
  const target = output.getContext('2d'); target.drawImage(source, 0, 0);
  drawLine(target, 1, 0, 0, Math.max(1, source.width / 1200));
  output.toBlob((blob) => {
    if (blob) {
      download(blob, `${imageName.replace(/\.[^.]+$/, '')}${line ? '-measured' : '-export'}.png`);
      feedback('Full-resolution PNG prepared for download. The original image is unchanged.');
    } else feedback('The image could not be exported.', true);
  }, 'image/png');
};
$('image-file').onchange = (event) => { openImage(event.target.files[0]); event.target.value = ''; };
for (const id of ['open-image', 'empty-open']) $(id).onclick = () => $('image-file').click();
$('stage').addEventListener('dragover', (event) => { event.preventDefault(); $('stage').classList.add('drag-over'); });
$('stage').addEventListener('dragleave', () => $('stage').classList.remove('drag-over'));
$('stage').addEventListener('drop', (event) => {
  event.preventDefault(); $('stage').classList.remove('drag-over'); openImage(event.dataTransfer.files[0]);
});
$('refresh').onclick = refreshStatus;
$('diagnostics').onclick = () => {
  if (report) download(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }), 'microscope-diagnostics.json');
};

async function cameraCommand(action, data = {}) {
  const response = await fetch(`/api/camera/${action}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Microscope-Client': 'local-ui' },
    body: JSON.stringify(data), signal: AbortSignal.timeout(20000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Camera request failed (${response.status})`);
  return result;
}

function finishLive() {
  live = false; liveGeneration++;
  $('live-view').textContent = replayMode() ? '▶ Play recording' : '▶ Start live view';
  if (streamingImage()) {
    $('source-tag').textContent = `${sourceType === 'replay' ? 'RECORDED' : 'CAPTURED'} · ${sourceDisplayMode === 'color' ? 'RGB' : 'RAW'}`;
    $('image-title').textContent = sourceType === 'replay' ? 'Recorded sensor image' : 'Captured sensor image';
    $('dimensions').textContent = `${source.width} × ${source.height} px · ${sourceDisplayMode === 'color' ? 'RGB image' : 'raw sensor image'}${sourceRecordedFile ? ` · ${sourceRecordedFile}` : ''}`;
  }
  updateMeasurement();
}

async function stopLive() {
  finishLive();
  await cameraCommand('stop');
}

async function nextFrame(generation) {
  if (!live || generation !== liveGeneration) return;
  try {
    const response = await fetch('/api/camera/frame.png', { signal: AbortSignal.timeout(10000) });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || 'Frame capture failed');
    }
    const frameMode = response.headers.get('X-Camera-Display') === 'color' ? 'color' : 'raw';
    const frameSource = response.headers.get('X-Camera-Source') === 'replay' ? 'replay' : 'camera';
    const bitmap = await createImageBitmap(await response.blob());
    if (!live || generation !== liveGeneration) { bitmap.close(); return; }
    const sizeChanged = source.width !== bitmap.width || source.height !== bitmap.height;
    const first = !streamingImage() || sizeChanged;
    if (sizeChanged) { line = null; micrometersPerPixel = null; drag = null; $('known-distance').value = ''; }
    if (source.width !== bitmap.width || source.height !== bitmap.height) {
      source.width = bitmap.width; source.height = bitmap.height;
    }
    pixels.drawImage(bitmap, 0, 0); bitmap.close();
    sourceDisplayMode = frameMode;
    sourceType = frameSource;
    sourceRecordedFile = response.headers.get('X-Camera-Recorded-File') || '';
    hasImage = true; imageName = frameSource === 'replay' ? `recorded-${sourceRecordedFile.replace(/\.raw$/, '')}-${frameMode}` : `microscope-${new Date().toISOString().replaceAll(':', '-')}-${frameMode}`;
    $('empty').hidden = true; canvas.hidden = false; $('image-hint').hidden = false;
    $('image-title').textContent = frameSource === 'replay' ? 'Recorded sensor playback' : 'Live sensor preview';
    $('source-tag').textContent = `${frameSource === 'replay' ? 'REPLAY' : 'LIVE'} · ${frameMode === 'color' ? 'RGB' : 'RAW'}`;
    $('dimensions').textContent = `${source.width} × ${source.height} px · ${frameMode === 'color' ? 'demosaiced RGB · uncalibrated color' : 'unprocessed grayscale'}${sourceRecordedFile ? ` · ${sourceRecordedFile} · ${response.headers.get('X-Camera-Exposure-Lines')} lines` : ''}`;
    $('cursor-value').textContent = ''; // Discard the previous frame's pixel readout.
    $('image-size').textContent = `${(source.width * source.height / 1e6).toFixed(2)} MP`;
    for (const id of ['fit', 'actual', 'zoom-in', 'zoom-out', 'crosshair', 'export']) $(id).disabled = false;
    if (first) { resize(); fit(); }
    render(); histogram();
    if (first) feedback(frameSource === 'replay' ? 'Playing saved raw frames in a loop. Stop and freeze to measure. The USB camera is not used.' : 'Receiving real camera frames. Stop and freeze to measure the image.');
    setTimeout(() => nextFrame(generation), 150);
  } catch (error) {
    if (generation !== liveGeneration) return;
    finishLive();
    try { await cameraCommand('stop'); } catch { /* server lease closes an unreachable device */ }
    feedback(error.message, true);
    refreshStatus();
  }
}

$('live-view').onclick = async () => {
  if (liveBusy) return;
  liveBusy = true; $('live-view').disabled = true;
  try {
    if (live) {
      await stopLive();
      feedback('Acquisition stopped. The last frame is ready to save or measure.');
    } else {
      await settingsQueue;
      await cameraCommand('start');
      ++loadSequence;
      live = true; const generation = ++liveGeneration;
      line = null; micrometersPerPixel = null; drag = null; measureMode = false;
      $('measure').setAttribute('aria-pressed', 'false'); canvas.classList.remove('measuring');
      $('image-hint').textContent = 'Scroll to zoom · Drag to pan';
      $('known-distance').value = '';
      $('source-tag').textContent = replayMode() ? 'LOADING RECORDING' : 'WAITING FOR CAMERA';
      $('live-view').textContent = '■ Stop and freeze';
      feedback(replayMode() ? 'Loading recorded frames…' : 'Starting camera acquisition…');
      updateMeasurement();
      nextFrame(generation);
    }
  } catch (error) { feedback(error.message, true); }
  finally { liveBusy = false; $('live-view').disabled = false; refreshStatus(); }
};
for (const id of ['exposure', 'gain']) {
  $(id).oninput = () => {
    $('exposure-value').textContent = `${$('exposure').value} lines`;
    $('gain-value').textContent = $('gain').value;
  };
  $(id).onchange = () => {
    const settings = { exposure_lines: Number($('exposure').value), gain: Number($('gain').value) };
    settingsPending++;
    settingsQueue = settingsQueue.then(() => cameraCommand('settings', settings))
      .catch(error => feedback(error.message, true))
      .finally(() => { settingsPending--; });
  };
}
async function changeSampling(action, data, message) {
  if (liveBusy) return;
  liveBusy = true; settingsPending++;
  $('live-view').disabled = true; $('acquisition-controls').disabled = true;
  $('recording').disabled = true;
  const wasLive = live;
  const generation = ++liveGeneration; // Ignore any old-resolution request already in flight.
  try {
    await settingsQueue;
    await cameraCommand(action, data);
    // A change of sensor sampling invalidates all image-space calibration.
    line = null; micrometersPerPixel = null; drag = null; measureMode = false;
    $('known-distance').value = '';
    $('measure').setAttribute('aria-pressed', 'false'); canvas.classList.remove('measuring');
    $('image-hint').textContent = 'Scroll to zoom · Drag to pan';
    updateMeasurement(); render();
    feedback(message);
    if (wasLive && live) {
      $('source-tag').textContent = replayMode() ? 'LOADING RECORDING' : 'WAITING FOR CAMERA';
      nextFrame(generation);
    }
  } catch (error) {
    if (wasLive) {
      finishLive();
      try { await cameraCommand('stop'); } catch { /* idle lease handles lost connection */ }
    }
    feedback(error.message, true);
  } finally {
    liveBusy = false; settingsPending--;
    $('acquisition-controls').disabled = replayMode(); $('live-view').disabled = false;
    refreshStatus();
  }
}
$('resolution').onchange = () => changeSampling('resolution', { resolution: $('resolution').value },
  `Resolution set to ${$('resolution').value.replace('x', ' × ')}. Recalibrate measurements for this mode.`);
$('recording').onchange = () => changeSampling('recording', { recording_id: $('recording').value },
  'Recording selected. The displayed exposure and gain are the original capture settings.');
function updateProcessingControls(state) {
  if (!state) return;
  whiteBalanceGains = state.white_balance_gains || [1, 1, 1];
  $('display-mode').value = state.display_mode || 'raw';
  $('wb-values').textContent = `RGB gains · ${whiteBalanceGains.map(g => g.toFixed(2)).join(' / ')}`;
  $('white-balance').disabled = !state.running;
}

async function changeProcessing(action, data, message) {
  if (processingBusy) return;
  processingBusy = true; $('color-controls').disabled = true;
  try {
    const result = await cameraCommand(action, data);
    updateProcessingControls(result);
    feedback(message + (live ? '' : ' Applied to the next frame.'));
  } catch (error) { feedback(error.message, true); }
  finally {
    processingBusy = false; $('color-controls').disabled = !report?.capture_available;
    refreshStatus();
  }
}
$('display-mode').onchange = () => changeProcessing('processing', {
  display_mode: $('display-mode').value, white_balance_gains: whiteBalanceGains,
}, 'Display updated. Raw sensor data is unchanged.');
$('white-balance').onclick = () => changeProcessing('white-balance', {},
  'White balance set from the neutral reference. Gains remain fixed until changed.');
$('reset-wb').onclick = () => changeProcessing('processing', {
  display_mode: $('display-mode').value, white_balance_gains: [1, 1, 1],
}, 'White-balance gains reset to unity.');

window.addEventListener('pagehide', () => {
  if (live) fetch('/api/camera/stop', { method: 'POST', keepalive: true,
    headers: { 'Content-Type': 'application/json', 'X-Microscope-Client': 'local-ui' }, body: '{}' }).catch(() => {});
});

new ResizeObserver(resize).observe($('stage'));
refreshStatus();
setInterval(() => { if (!document.hidden) refreshStatus(); }, 15000);
