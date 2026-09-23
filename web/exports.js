import { drawMarkers, drawScaleBar, drawHistogram } from "./overlays.js";
import { measurement } from "./markers.js";

function wrap(ctx, text, x, y, width, lineHeight) {
  for (const paragraph of String(text).split("\n")) {
    let line = "";
    for (const word of paragraph.split(/\s+/)) {
      if (ctx.measureText(line + word).width > width && line) {
        ctx.fillText(line, x, y);
        y += lineHeight;
        line = "";
      }
      line += word + " ";
    }
    ctx.fillText(line, x, y);
    y += lineHeight;
  }
  return y;
}

export async function inspectionPNG(record, kind) {
  const response = await fetch(record.image_url);
  if (!response.ok) throw new Error("Cannot load saved capture image.");
  const bitmap = await createImageBitmap(await response.blob()),
    m = record.metadata,
    a = record.inspection;
  const sheet = kind === "inspection.png",
    panel = 960;
  const textScale = Math.max(1, m.width / 1280),
    canvas = document.createElement("canvas");
  canvas.width = m.width + (sheet ? panel : 0);
  canvas.height = sheet
    ? Math.max(
        m.height,
        2300 +
          a.markers.length * 100 +
          (Math.ceil(a.notes.length / 45) + a.notes.split("\n").length) * 34,
      )
    : m.height;
  if (canvas.height > 12000) {
    bitmap.close();
    throw new Error(
      "This report is too long for one PNG. Shorten notes or export annotations separately.",
    );
  }
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#f7f8f3";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  if (kind !== "image-only.png") {
    drawMarkers(
      ctx,
      a.markers,
      { x: 0, y: 0, scale: 1 },
      a.calibration?.um_per_pixel ?? null,
      null,
      textScale,
      m.width,
    );
    drawScaleBar(
      ctx,
      m.width,
      m.height,
      a.calibration?.um_per_pixel,
      textScale,
    );
    // Every annotated image states the applied profile, including uncalibrated captures.
    ctx.font = `${15 * textScale}px sans-serif`;
    ctx.fillStyle = "#101b15e8";
    ctx.fillRect(0, 0, m.width, 32 * textScale);
    ctx.fillStyle = "#e5f7d6";
    ctx.fillText(
      a.calibration
        ? `Calibration: ${a.calibration.name} · ${a.calibration.um_per_pixel.toPrecision(5)} µm/px`
        : "UNCALIBRATED · measurements in pixels",
      14 * textScale,
      22 * textScale,
    );
  }
  if (sheet) {
    const x = m.width + 36,
      width = panel - 72;
    let y = 55;
    ctx.fillStyle = "#17251d";
    ctx.font = "bold 32px sans-serif";
    y = wrap(ctx, "Microscope inspection", x, y, width, 42);
    ctx.font = "24px sans-serif";
    const rows = [
      ["Sample", a.sample_id || "Not specified"],
      ["Acquired", m.captured_at],
      [
        "Source",
        m.source_type === "replay"
          ? `REPLAY · ${m.provenance?.dataset}/${m.provenance?.file}`
          : "USB camera",
      ],
      ["Resolution", `${m.width} × ${m.height} · ${m.pixel_format}`],
      ["Exposure", `${m.exposure_lines} sensor lines (timing uncalibrated)`],
      ["Gain", `${m.gain} sensor register units`],
      [
        "Display",
        `${m.display_mode} · WB ${m.white_balance_gains.map((v) => v.toFixed(4)).join(" / ")}`,
      ],
      ["Objective", a.objective || "Not specified"],
      ["Optical configuration", a.optical_configuration || "Not specified"],
      [
        "Calibration",
        a.calibration
          ? `${a.calibration.name} · ${a.calibration.um_per_pixel.toPrecision(5)} ± ${a.calibration.fit_standard_error.toPrecision(2)} µm/px (fit SE only)`
          : "UNCALIBRATED",
      ],
      [
        "Raw clipping",
        `${m.raw_statistics.saturated_percent.toFixed(5)}% at 255; ${m.raw_statistics.zero_percent.toFixed(5)}% at 0`,
      ],
      [
        "Focus",
        `${m.raw_statistics.focus?.toFixed(2) ?? "n/a"} DN² · central raw green; exposure dependent`,
      ],
      ["Capture ID", m.capture_id],
      ["Annotation revision", a.revision],
      ["Raw SHA-256", m.sha256],
    ];
    for (const [key, value] of rows) {
      ctx.font = "bold 22px sans-serif";
      y = wrap(ctx, key, x, y + 16, width, 29);
      ctx.font = "24px sans-serif";
      y = wrap(ctx, value, x, y, width, 31);
    }
    ctx.font = "bold 25px sans-serif";
    y = wrap(ctx, "Raw sensor histogram (DN)", x, y + 30, width, 34);
    drawHistogram(ctx, m.raw_statistics.histogram, x, y, width, 150, "#4c7158");
    y += 182;
    ctx.font = "20px monospace";
    ctx.fillText("0", x, y);
    ctx.fillText("255", x + width - 40, y);
    y += 40;
    ctx.font = "bold 25px sans-serif";
    y = wrap(ctx, "Markers and measurements", x, y, width, 34);
    ctx.font = "24px sans-serif";
    for (const marker of a.markers)
      y = wrap(
        ctx,
        `${marker.label || marker.id}: ${measurement(marker, a.calibration?.um_per_pixel ?? null)}`,
        x,
        y,
        width,
        31,
      );
    if (!a.markers.length) y = wrap(ctx, "No markers", x, y, width, 31);
    ctx.font = "bold 25px sans-serif";
    y = wrap(ctx, "Notes", x, y + 26, width, 34);
    ctx.font = "24px sans-serif";
    y = wrap(ctx, a.notes || "—", x, y, width, 31);
    if (y + 40 > canvas.height)
      throw new Error(
        "This report is too long for one PNG. Shorten notes or export annotations separately.",
      );
    // Keep original image pixels; trim only the unused report canvas below both columns.
    const trimmed = document.createElement("canvas");
    trimmed.width = canvas.width;
    trimmed.height = Math.ceil(Math.max(m.height, y + 40));
    trimmed.getContext("2d").drawImage(canvas, 0, 0);
    return trimmed.toDataURL("image/png").split(",")[1];
  }
  return canvas.toDataURL("image/png").split(",")[1];
}
