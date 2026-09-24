import { $, request, cameraCommand, feedback, download } from "./api.js";
import { Markers } from "./markers.js";
import { Viewer } from "./viewer.js";
import { CalibrationUI } from "./calibration-ui.js";
import { Inspection } from "./inspection.js";

let report = null,
  live = false,
  generation = 0,
  busy = false,
  checking = false,
  frameId = null,
  frameMetadata = null;
let settingsQueue = Promise.resolve(),
  settingsPending = 0,
  processingBusy = false,
  whiteBalanceSource = "manual",
  whiteBalance = [1, 1, 1];
let inspection = null,
  calibration = null;
const markers = new Markers((changed) => {
  if (inspection) {
    if (changed) inspection.changed();
    else inspection.render();
  }
});
const viewer = new Viewer(markers);
const resolution = () =>
  inspection?.record?.metadata.resolution ||
  frameMetadata?.resolution ||
  (!live && viewer.hasImage
    ? `${viewer.source.width}x${viewer.source.height}`
    : "") ||
  report?.acquisition.resolution ||
  "";
calibration = new CalibrationUI(
  () => inspection?.record,
  resolution,
  () => markers.items.find((m) => m.id === markers.selected),
  () => inspection?.changed(),
);
inspection = new Inspection(
  markers,
  viewer,
  calibration,
  async () => {
    if (inspection.dirty) await inspection.save();
    await stopOnly();
  },
  () => frameMetadata,
);
const replayMode = () => report?.acquisition.source_type === "replay";

function controls() {
  $("live-view").disabled = !report?.capture_available || busy;
  $("live-view").textContent = live
    ? "■ Stop and capture"
    : replayMode()
      ? "▶ Play recording"
      : "▶ Start live view";
  $("capture-frame").disabled = !frameId || busy || !!inspection.record;
  $("acquisition-controls").disabled =
    replayMode() || !report?.capture_available || busy;
  $("recording").disabled = !report?.capture_available || busy;
  $("color-controls").disabled = !report?.capture_available || processingBusy;
  $("white-balance").disabled = !report?.acquisition.running;
  inspection.render();
}

async function refreshStatus() {
  if (checking) return;
  checking = true;
  $("refresh").disabled = true;
  try {
    report = await request("/api/status");
    const state = report.acquisition,
      replay = replayMode(),
      connected = report.usb_state === "connected";
    $("connection-text").textContent = replay
      ? "Offline replay · camera not used"
      : connected
        ? "USB connected · native SDK"
        : "Camera disconnected";
    $("status-dot").className =
      `dot ${replay || connected ? "connected" : "error"}`;
    $("device-state").textContent = replay
      ? "Recorded data"
      : report.capture_available
        ? "Ready for capture"
        : "Camera unavailable";
    $("device-message").textContent = report.message;
    $("recording-field").hidden = !replay;
    $("empty-message").textContent = replay
      ? "Play a recording, then Capture & freeze to save an inspection. No camera connection is needed."
      : "Start live view, then Capture & freeze to save an inspection. You can also open an image locally.";
    $("refresh").title = replay
      ? "Refresh replay status"
      : "Refresh USB status";
    $("refresh").setAttribute("aria-label", $("refresh").title);
    $("acquisition-note").textContent = replay
      ? "Exposure and gain are fixed in each recording. Playback loops saved raw frames."
      : "Exposure is in sensor lines; duration changes with resolution.";
    if (replay && !busy) {
      const key = JSON.stringify(state.recordings);
      if ($("recording").dataset.key !== key) {
        $("recording").replaceChildren(
          ...state.recordings.map(
            (g) =>
              new Option(
                `${g.resolution.replace("x", " × ")} · ${g.settings.exposure_lines} lines · gain ${g.settings.gain}`,
                g.id,
              ),
          ),
        );
        $("recording").dataset.key = key;
      }
      $("recording").value = state.recording_id;
    }
    if (
      !settingsPending &&
      !busy &&
      !["exposure", "gain", "resolution"].includes(document.activeElement?.id)
    ) {
      $("exposure").value = state.settings.exposure_lines;
      $("gain").value = state.settings.gain;
      $("resolution").value = state.resolution;
      settingsLabels();
    }
    if (!processingBusy) {
      whiteBalance = state.white_balance_gains;
      whiteBalanceSource = state.white_balance_source || "manual";
      $("display-mode").value = state.display_mode;
      processingLabels();
    }
    $("recorded-wb").hidden = !replay;
    $("recorded-wb").disabled =
      processingBusy || whiteBalanceSource === "recorded";
    const details = replay
      ? {
          Source: "Recorded RAW8 RGGB; USB disabled",
          Dataset: state.dataset,
          Scene: state.description,
        }
      : {
          "USB ID": "0547:c004",
          Name: report.devices[0]?.name || "—",
          Host: `${report.platform} / ${report.architecture}`,
        };
    $("device-details").replaceChildren();
    for (const [key, value] of Object.entries(details)) {
      const dt = document.createElement("dt"),
        dd = document.createElement("dd");
      dt.textContent = key;
      dd.textContent = value;
      $("device-details").append(dt, dd);
    }
    if (live && !busy && !state.running) {
      live = false;
      generation++;
      $("source-tag").textContent = "PREVIEW STOPPED";
      feedback(
        "Preview stopped. Capture the retained frame now, or resume preview.",
      );
    }
    calibration.render();
    controls();
  } catch (error) {
    report = null;
    $("connection-text").textContent = "Local server unavailable";
    $("status-dot").className = "dot error";
    controls();
  } finally {
    checking = false;
    $("refresh").disabled = false;
    $("diagnostics").disabled = !report;
  }
}

function displayMetadata(meta, saved = false) {
  frameMetadata = meta;
  if (!saved && !processingBusy) {
    whiteBalance = meta.white_balance_gains;
    whiteBalanceSource = meta.white_balance_source || "manual";
    processingLabels();
  }
  $("image-title").textContent = saved
    ? "Saved inspection"
    : meta.source_type === "replay"
      ? "Recorded sensor playback"
      : "Live sensor preview";
  $("source-tag").textContent =
    `${saved ? "SAVED" : meta.source_type === "replay" ? "REPLAY" : "LIVE"} · ${meta.display_mode === "color" ? "RGB" : "RAW"}`;
  $("dimensions").textContent =
    `${meta.width} × ${meta.height} · ${meta.source_type === "replay" ? meta.recorded_file || meta.provenance?.file : "USB"} · frame ${meta.frame_id.slice(0, 8)}`;
  const stats = meta.raw_statistics;
  $("clipping-badge").textContent =
    `Raw: ${stats.saturated_percent.toFixed(4)}% at 255 · ${stats.zero_percent.toFixed(4)}% at 0`;
  $("clipping-badge").classList.toggle("warning", stats.saturated_pixels > 0);
  $("focus-value").textContent = `${stats.focus?.toFixed(2) ?? "—"} DN²`;
  viewer.histogram(meta);
  calibration.render();
  viewer.scale = calibration.active?.um_per_pixel ?? null;
  viewer.render();
}

async function nextFrame(token) {
  if (!live || token !== generation) return;
  try {
    const response = await fetch("/api/camera/frame.png", {
      signal: AbortSignal.timeout(20000),
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Frame request failed");
    }
    const id = response.headers.get("X-Frame-ID");
    if (!id) throw new Error("Restart the server to enable capture IDs.");
    const [bitmap, meta] = await Promise.all([
      response.blob().then(createImageBitmap),
      request(`/api/frames/${id}`),
    ]);
    if (!live || token !== generation) {
      bitmap.close();
      return;
    }
    const first = !frameId;
    viewer.show(bitmap, first);
    bitmap.close();
    frameId = id;
    displayMetadata(meta);
    controls();
    if (first)
      feedback(
        "Preview ready. Capture & freeze saves these exact raw pixels and settings.",
      );
    setTimeout(() => nextFrame(token), 150);
  } catch (error) {
    if (token !== generation) return;
    live = false;
    generation++;
    try {
      await cameraCommand("stop");
    } catch {}
    feedback(error.message, true);
    controls();
  }
}

async function stopOnly() {
  live = false;
  generation++;
  try {
    await cameraCommand("stop");
  } finally {
    controls();
  }
}
async function freeze() {
  if (!frameId) throw new Error("Wait for a preview frame before capturing.");
  live = false;
  generation++; // The displayed frame ID is now fixed, including any request already in flight.
  let record;
  try {
    record = await inspection.capture(frameId);
  } finally {
    await cameraCommand("stop");
  }
  displayMetadata(record.metadata, true);
  controls();
  return record;
}
async function action(work) {
  if (busy) return;
  busy = true;
  controls();
  try {
    await work();
  } catch (error) {
    feedback(error.message, true);
  } finally {
    busy = false;
    await refreshStatus();
    controls();
  }
}
$("capture-frame").onclick = () => action(freeze);
$("live-view").onclick = () =>
  action(async () => {
    if (live) {
      await freeze();
      return;
    }
    if (inspection.dirty) await inspection.save();
    await settingsQueue;
    await cameraCommand("start");
    inspection.clear();
    frameId = frameMetadata = null;
    live = true;
    const token = ++generation;
    calibration.render();
    $("source-tag").textContent = "WAITING FOR FRAME";
    feedback("Starting preview…");
    nextFrame(token);
  });
function settingsLabels() {
  $("exposure-value").textContent = `${$("exposure").value} lines`;
  $("gain-value").textContent = $("gain").value;
}
for (const id of ["exposure", "gain"]) {
  $(id).oninput = settingsLabels;
  $(id).onchange = () => {
    // Send only the control that changed; the other keeps its current server value, so a slider that has
    // not yet refreshed (e.g. after a scripted capture changed the gain) cannot write back a stale setting.
    const data =
      id === "exposure"
        ? { exposure_lines: Number($("exposure").value) }
        : { gain: Number($("gain").value) };
    settingsPending++;
    settingsQueue = settingsQueue
      .then(() => cameraCommand("settings", data))
      .catch((e) => feedback(e.message, true))
      .finally(() => settingsPending--);
  };
}
async function changeSampling(actionName, data) {
  await action(async () => {
    const wasLive = live;
    generation++;
    await settingsQueue;
    await cameraCommand(actionName, data);
    if (wasLive) {
      inspection.clear();
      frameId = frameMetadata = null;
      nextFrame(generation);
    }
    feedback(
      "Acquisition mode changed. Calibration profiles are matched to exact image resolution.",
    );
  });
}
$("resolution").onchange = () =>
  changeSampling("resolution", { resolution: $("resolution").value });
$("recording").onchange = () =>
  changeSampling("recording", { recording_id: $("recording").value });
function processingLabels() {
  $("wb-values").textContent =
    `RGB gains · ${whiteBalance.map((g) => g.toFixed(2)).join(" / ")}${replayMode() ? ` · ${whiteBalanceSource === "recorded" ? "recorded per frame" : "manual override"}` : ""}`;
}
async function processing(actionName, data) {
  if (processingBusy) return;
  processingBusy = true;
  controls();
  try {
    const state = await cameraCommand(actionName, data);
    whiteBalance = state.white_balance_gains;
    whiteBalanceSource = state.white_balance_source || "manual";
    processingLabels();
    feedback(
      "Processing updated for subsequent preview frames. Saved captures retain their original display settings.",
    );
  } catch (error) {
    feedback(error.message, true);
  } finally {
    processingBusy = false;
    await refreshStatus();
  }
}
$("display-mode").onchange = () =>
  processing("processing", {
    display_mode: $("display-mode").value,
    white_balance_gains: whiteBalance,
    ...(replayMode() ? { white_balance_source: whiteBalanceSource } : {}),
  });
$("recorded-wb").onclick = () =>
  processing("processing", {
    display_mode: $("display-mode").value,
    white_balance_source: "recorded",
  });
$("white-balance").onclick = () => processing("white-balance", {});
$("reset-wb").onclick = () =>
  processing("processing", {
    display_mode: $("display-mode").value,
    white_balance_gains: [1, 1, 1],
  });
$("fit").onclick = () => viewer.fit();
$("actual").onclick = () => viewer.zoom(1 / viewer.view.scale);
$("zoom-in").onclick = () => viewer.zoom(1.25);
$("zoom-out").onclick = () => viewer.zoom(0.8);
$("crosshair").onclick = () => {
  viewer.crosshair = !viewer.crosshair;
  $("crosshair").setAttribute("aria-pressed", String(viewer.crosshair));
  viewer.render();
};
$("refresh").onclick = refreshStatus;
$("diagnostics").onclick = () =>
  download(
    new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    "microscope-status.json",
  );
window.addEventListener("captureopened", (event) => {
  frameId = null;
  displayMetadata(event.detail.metadata, true);
  controls();
  feedback(
    "Saved capture opened with its original pixels, settings and annotations.",
  );
});

async function openImage(file) {
  if (!file) return;
  await action(async () => {
    if (file.size > 50 * 1024 * 1024)
      throw new Error("Choose an image smaller than 50 MB.");
    if (inspection.dirty) await inspection.save();
    await stopOnly();
    const bitmap = await createImageBitmap(file);
    if (bitmap.width * bitmap.height > 40_000_000) {
      bitmap.close();
      throw new Error("Choose an image no larger than 40 MP.");
    }
    inspection.clear();
    frameId = frameMetadata = null;
    calibration.restore(null);
    viewer.show(bitmap, true);
    bitmap.close();
    viewer.editable = true;
    calibration.render();
    $("image-title").textContent = file.name;
    $("source-tag").textContent = "IMPORTED IMAGE";
    $("dimensions").textContent =
      `${viewer.source.width} × ${viewer.source.height} · no raw sensor data`;
    $("clipping-badge").textContent = "Raw clipping unavailable";
    $("focus-value").textContent = "—";
    viewer.histogram(null);
    inspection.render();
    feedback(
      "Imported image opened locally. Raw capture and session exports require camera or replay frames.",
    );
  });
}
$("image-file").onchange = (e) => {
  openImage(e.target.files[0]);
  e.target.value = "";
};
for (const id of ["open-image", "empty-open"])
  $(id).onclick = () => $("image-file").click();
$("stage").addEventListener("dragover", (e) => e.preventDefault());
$("stage").addEventListener("drop", (e) => {
  e.preventDefault();
  openImage(e.dataTransfer.files[0]);
});
window.addEventListener("pagehide", () => {
  if (live)
    fetch("/api/camera/stop", {
      method: "POST",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        "X-Microscope-Client": "local-ui",
      },
      body: "{}",
    }).catch(() => {});
});
calibration.load().catch((e) => feedback(e.message, true));
inspection.gallery().catch((e) => feedback(e.message, true));
refreshStatus();
setInterval(() => {
  if (!document.hidden) refreshStatus();
}, 15000);
