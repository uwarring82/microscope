import { measurement } from "./markers.js";
import { distance } from "./geometry.js";
export function drawMarkers(
  ctx,
  items,
  view,
  scale = null,
  selected = null,
  textScale = 1,
  boundsWidth = ctx.canvas.width / ctx.getTransform().a,
) {
  ctx.save();
  ctx.font = `${12 * textScale}px -apple-system, sans-serif`;
  ctx.lineWidth = 2 * textScale;
  for (const marker of items) {
    const a = {
      x: view.x + marker.a.x * view.scale,
      y: view.y + marker.a.y * view.scale,
    };
    const b = {
      x: view.x + marker.b.x * view.scale,
      y: view.y + marker.b.y * view.scale,
    };
    ctx.strokeStyle = ctx.fillStyle =
      marker.id === selected ? "#ffcf77" : "#d5fba9";
    ctx.beginPath();
    if (marker.type === "rectangle") ctx.rect(a.x, a.y, b.x - a.x, b.y - a.y);
    else if (marker.type === "circle")
      ctx.arc(a.x, a.y, distance(marker) * view.scale, 0, 2 * Math.PI);
    else if (marker.type === "point") {
      ctx.moveTo(a.x - 6 * textScale, a.y);
      ctx.lineTo(a.x + 6 * textScale, a.y);
      ctx.moveTo(a.x, a.y - 6 * textScale);
      ctx.lineTo(a.x, a.y + 6 * textScale);
    } else {
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();
    if (marker.id === selected)
      for (const point of [a, b])
        ctx.fillRect(
          point.x - 3 * textScale,
          point.y - 3 * textScale,
          6 * textScale,
          6 * textScale,
        );
    const text = `${marker.label || "Marker"} · ${measurement(marker, scale)}`;
    const width = ctx.measureText(text).width + 12 * textScale;
    const x = Math.max(0, Math.min(boundsWidth - width, a.x));
    const y = Math.max(20 * textScale, a.y - 10 * textScale);
    ctx.fillStyle = "#152219e8";
    ctx.fillRect(x, y - 16 * textScale, width, 22 * textScale);
    ctx.fillStyle = "#e5f7d6";
    ctx.fillText(text, x + 6 * textScale, y);
  }
  ctx.restore();
}
export function drawScaleBar(ctx, width, height, umPerPixel, textScale = 1) {
  if (!umPerPixel) return;
  const maximum = width * 0.2 * umPerPixel;
  const decade = 10 ** Math.floor(Math.log10(maximum));
  const length =
    [5, 2, 1].map((n) => n * decade).find((n) => n <= maximum) || decade / 2;
  const px = length / umPerPixel,
    x = 30 * textScale,
    y = height - 35 * textScale;
  ctx.save();
  ctx.fillStyle = "#101b15dd";
  ctx.fillRect(
    x - 12 * textScale,
    y - 40 * textScale,
    px + 24 * textScale,
    60 * textScale,
  );
  ctx.strokeStyle = ctx.fillStyle = "#e5f7d6";
  ctx.lineWidth = 4 * textScale;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + px, y);
  ctx.stroke();
  ctx.font = `${15 * textScale}px sans-serif`;
  ctx.fillText(`${Number(length.toPrecision(4))} µm`, x, y - 13 * textScale);
  ctx.restore();
}
export function drawHistogram(
  ctx,
  bins,
  x,
  y,
  width,
  height,
  color = "#a8c28e",
) {
  const maximum = Math.max(...bins, 1);
  ctx.fillStyle = color;
  bins.forEach((value, i) => {
    const h = (value / maximum) * height;
    ctx.fillRect(
      x + (i * width) / 256,
      y + height - h,
      Math.max(1, width / 256),
      h,
    );
  });
}
