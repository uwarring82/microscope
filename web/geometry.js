export function imagePoint(point, view) {
  return {
    x: (point.x - view.x) / view.scale,
    y: (point.y - view.y) / view.scale,
  };
}

export function distance(line) {
  return Math.hypot(line.b.x - line.a.x, line.b.y - line.a.y);
}

export function calibratedScale(line, micrometers) {
  const pixels = distance(line);
  if (
    !Number.isFinite(micrometers) ||
    micrometers <= 0 ||
    !Number.isFinite(pixels) ||
    pixels < 1
  ) {
    throw new Error(
      "Draw a line at least one image pixel long and enter a positive known length.",
    );
  }
  return micrometers / pixels;
}

export function zoomAt(view, anchor, factor) {
  const point = imagePoint(anchor, view);
  const scale = Math.max(0.01, Math.min(32, view.scale * factor));
  return {
    scale,
    x: anchor.x - point.x * scale,
    y: anchor.y - point.y * scale,
  };
}
