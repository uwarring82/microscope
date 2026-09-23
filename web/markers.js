import { distance } from "./geometry.js";
const copy = (value) => structuredClone(value);
export class Markers {
  constructor(onchange = () => {}) {
    this.items = [];
    this.selected = null;
    this.past = [];
    this.future = [];
    this.onchange = onchange;
  }
  replace(items = []) {
    this.items = copy(items);
    this.selected = null;
    this.past = [];
    this.future = [];
    this.onchange(false);
  }
  edit(action) {
    const before = copy(this.items);
    action();
    if (JSON.stringify(before) === JSON.stringify(this.items)) return;
    this.past.push(before);
    if (this.past.length > 100) this.past.shift();
    this.future = [];
    this.onchange(true);
  }
  add(marker) {
    if (this.items.length >= 200)
      throw new Error("Maximum 200 markers per image.");
    this.edit(() => {
      this.items.push(copy(marker));
      this.selected = marker.id;
    });
  }
  update(id, values) {
    this.edit(() => {
      this.items = this.items.map((m) =>
        m.id === id ? { ...m, ...copy(values) } : m,
      );
    });
  }
  remove() {
    this.edit(() => {
      this.items = this.items.filter((m) => m.id !== this.selected);
      this.selected = null;
    });
  }
  select(id) {
    this.selected = id;
    this.onchange(false);
  }
  undo() {
    if (!this.past.length) return;
    this.future.push(copy(this.items));
    this.items = this.past.pop();
    this.selected = null;
    this.onchange(true);
  }
  redo() {
    if (!this.future.length) return;
    this.past.push(copy(this.items));
    this.items = this.future.pop();
    this.selected = null;
    this.onchange(true);
  }
}

export function measurement(marker, scale = null) {
  const s = scale ?? 1,
    unit = scale === null ? "px" : "µm";
  const dx = Math.abs(marker.b.x - marker.a.x),
    dy = Math.abs(marker.b.y - marker.a.y);
  if (marker.type === "point")
    return `x ${marker.a.x.toFixed(1)}, y ${marker.a.y.toFixed(1)} px`;
  if (marker.type === "circle")
    return `Ø ${(2 * distance(marker) * s).toFixed(2)} ${unit}`;
  if (marker.type === "rectangle")
    return `${(dx * s).toFixed(2)} × ${(dy * s).toFixed(2)} ${unit}; ${(dx * dy * s * s).toFixed(2)} ${unit}²`;
  return `${(distance(marker) * s).toFixed(2)} ${unit}`;
}

export function translate(marker, dx, dy, width, height) {
  dx = Math.max(
    -Math.min(marker.a.x, marker.b.x),
    Math.min(width - 1 - Math.max(marker.a.x, marker.b.x), dx),
  );
  dy = Math.max(
    -Math.min(marker.a.y, marker.b.y),
    Math.min(height - 1 - Math.max(marker.a.y, marker.b.y), dy),
  );
  return {
    ...marker,
    a: { x: marker.a.x + dx, y: marker.a.y + dy },
    b: { x: marker.b.x + dx, y: marker.b.y + dy },
  };
}

export function hitTest(markers, p, tolerance) {
  for (const marker of [...markers].reverse()) {
    for (const handle of marker.type === "point" ? ["a"] : ["a", "b"]) {
      if (
        Math.hypot(p.x - marker[handle].x, p.y - marker[handle].y) <= tolerance
      )
        return { marker, handle };
    }
    let near = false;
    if (marker.type === "line") {
      const dx = marker.b.x - marker.a.x,
        dy = marker.b.y - marker.a.y;
      const t = Math.max(
        0,
        Math.min(
          1,
          ((p.x - marker.a.x) * dx + (p.y - marker.a.y) * dy) /
            (dx * dx + dy * dy || 1),
        ),
      );
      near =
        Math.hypot(p.x - marker.a.x - t * dx, p.y - marker.a.y - t * dy) <=
        tolerance;
    } else if (marker.type === "rectangle") {
      near =
        p.x >= Math.min(marker.a.x, marker.b.x) - tolerance &&
        p.x <= Math.max(marker.a.x, marker.b.x) + tolerance &&
        p.y >= Math.min(marker.a.y, marker.b.y) - tolerance &&
        p.y <= Math.max(marker.a.y, marker.b.y) + tolerance;
    } else if (marker.type === "circle")
      near =
        Math.hypot(p.x - marker.a.x, p.y - marker.a.y) <=
        distance(marker) + tolerance;
    if (near) return { marker, handle: null };
  }
  return null;
}
