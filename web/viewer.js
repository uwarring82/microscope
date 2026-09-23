import { $, feedback } from "./api.js";
import { imagePoint, zoomAt, distance } from "./geometry.js";
import { hitTest, translate } from "./markers.js";
import { drawMarkers, drawScaleBar, drawHistogram } from "./overlays.js";

export class Viewer {
  constructor(markers) {
    this.markers = markers;
    this.canvas = $("viewer");
    this.ctx = this.canvas.getContext("2d");
    this.source = document.createElement("canvas");
    this.pixels = this.source.getContext("2d", { willReadFrequently: true });
    this.hasImage = false;
    this.editable = false;
    this.tool = "pan";
    this.scale = null;
    this.crosshair = false;
    this.view = { x: 0, y: 0, scale: 1 };
    this.drag = null;
    this.draft = null;
    this.canvas.addEventListener("pointerdown", (e) => this.down(e));
    this.canvas.addEventListener("pointermove", (e) => this.move(e));
    this.canvas.addEventListener("pointerup", () => this.up());
    this.canvas.addEventListener("pointercancel", () => {
      this.drag = this.draft = null;
      this.render();
    });
    this.canvas.addEventListener(
      "wheel",
      (e) => {
        if (this.hasImage) {
          e.preventDefault();
          this.zoom(Math.exp(-e.deltaY * 0.001), this.point(e));
        }
      },
      { passive: false },
    );
    new ResizeObserver(() => this.resize()).observe($("stage"));
  }
  dimensions() {
    return { width: $("stage").clientWidth, height: $("stage").clientHeight };
  }
  point(e) {
    const r = this.canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }
  clamp(p) {
    return {
      x: Math.max(0, Math.min(this.source.width - 1, p.x)),
      y: Math.max(0, Math.min(this.source.height - 1, p.y)),
    };
  }
  resize() {
    const { width, height } = this.dimensions(),
      dpr = window.devicePixelRatio || 1;
    this.canvas.width = width * dpr;
    this.canvas.height = height * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.render();
  }
  fit() {
    if (!this.hasImage) return;
    const { width, height } = this.dimensions();
    const scale = Math.min(
      (width - 24) / this.source.width,
      (height - 24) / this.source.height,
    );
    this.view = {
      scale,
      x: (width - this.source.width * scale) / 2,
      y: (height - this.source.height * scale) / 2,
    };
    this.render();
  }
  zoom(factor, anchor) {
    if (!this.hasImage) return;
    const { width, height } = this.dimensions();
    this.view = zoomAt(
      this.view,
      anchor || { x: width / 2, y: height / 2 },
      factor,
    );
    this.render();
  }
  show(bitmap, reset = false) {
    const changed =
      this.source.width !== bitmap.width ||
      this.source.height !== bitmap.height;
    this.source.width = bitmap.width;
    this.source.height = bitmap.height;
    this.pixels.drawImage(bitmap, 0, 0);
    this.hasImage = true;
    $("empty").hidden = true;
    this.canvas.hidden = false;
    $("image-hint").hidden = false;
    $("cursor-value").textContent = "";
    $("image-size").textContent =
      `${((bitmap.width * bitmap.height) / 1e6).toFixed(2)} MP`;
    for (const id of ["fit", "actual", "zoom-in", "zoom-out", "crosshair"])
      $(id).disabled = false;
    if (changed || reset) {
      this.resize();
      this.fit();
    } else this.render();
  }
  render() {
    const { width, height } = this.dimensions(),
      ctx = this.ctx;
    ctx.clearRect(0, 0, width, height);
    if (!this.hasImage) return;
    ctx.imageSmoothingEnabled = this.view.scale < 2;
    ctx.drawImage(
      this.source,
      this.view.x,
      this.view.y,
      this.source.width * this.view.scale,
      this.source.height * this.view.scale,
    );
    if (this.crosshair) {
      ctx.strokeStyle = "#d5fba980";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(width / 2, 0);
      ctx.lineTo(width / 2, height);
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
    }
    let items = this.markers.items;
    if (this.draft)
      items = [...items.filter((m) => m.id !== this.draft.id), this.draft];
    drawMarkers(ctx, items, this.view, this.scale, this.markers.selected);
    // A scale bar is drawn in screen pixels but converted using the image zoom.
    if (this.scale)
      drawScaleBar(ctx, width, height, this.scale / this.view.scale);
    $("zoom-value").textContent = `${Math.round(this.view.scale * 100)}%`;
  }
  histogram(metadata) {
    let bins = metadata?.raw_statistics?.histogram,
      mean = metadata?.raw_statistics?.mean;
    if (!bins) {
      bins = new Array(256).fill(0);
      const rgba = this.pixels.getImageData(
        0,
        0,
        this.source.width,
        this.source.height,
      ).data;
      let sum = 0;
      for (let i = 0; i < rgba.length; i += 4) {
        const n = Math.round(
          0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2],
        );
        bins[n]++;
        sum += n;
      }
      mean = sum / (rgba.length / 4);
    }
    const ctx = $("histogram").getContext("2d");
    ctx.clearRect(0, 0, 480, 76);
    drawHistogram(ctx, bins, 0, 0, 480, 74);
    $("histogram-label").textContent = metadata
      ? "Raw sensor DN"
      : "Displayed luminance";
    $("mean").textContent = `${mean.toFixed(1)} / 255`;
  }
  down(e) {
    if (!this.hasImage || e.button !== 0) return;
    const p = this.point(e),
      ip = this.clamp(imagePoint(p, this.view));
    this.canvas.setPointerCapture(e.pointerId);
    this.drag = { start: p, ip, view: { ...this.view }, mode: "pan" };
    if (!this.editable || this.tool === "pan") return;
    if (this.tool === "select") {
      const hit = hitTest(this.markers.items, ip, 10 / this.view.scale);
      this.markers.select(hit?.marker.id || null);
      if (hit) {
        this.drag = { ...this.drag, ...hit, mode: "edit" };
        this.draft = structuredClone(hit.marker);
      }
    } else {
      this.drag.mode = "new";
      this.draft = {
        id: crypto.randomUUID(),
        type: this.tool,
        label: `M${this.markers.items.length + 1}`,
        a: ip,
        b: ip,
      };
    }
    this.render();
  }
  move(e) {
    if (!this.hasImage) return;
    const p = this.point(e),
      ip = this.clamp(imagePoint(p, this.view));
    if (this.drag) {
      if (this.drag.mode === "new")
        this.draft = {
          ...this.draft,
          b: this.draft.type === "point" ? this.draft.a : ip,
        };
      else if (this.drag.mode === "edit") {
        if (this.drag.handle) {
          this.draft = { ...this.drag.marker, [this.drag.handle]: ip };
          if (this.draft.type === "point") this.draft.b = ip;
        } else
          this.draft = translate(
            this.drag.marker,
            ip.x - this.drag.ip.x,
            ip.y - this.drag.ip.y,
            this.source.width,
            this.source.height,
          );
      } else
        this.view = {
          ...this.drag.view,
          x: this.drag.view.x + p.x - this.drag.start.x,
          y: this.drag.view.y + p.y - this.drag.start.y,
        };
      this.render();
    }
    const [r, g, b] = this.pixels.getImageData(
      Math.floor(ip.x),
      Math.floor(ip.y),
      1,
      1,
    ).data;
    $("cursor-value").textContent =
      `x ${Math.floor(ip.x)} · y ${Math.floor(ip.y)} · RGB ${r}, ${g}, ${b}`;
  }
  up() {
    if (this.draft) {
      try {
        if (this.drag.mode === "edit")
          this.markers.update(this.draft.id, this.draft);
        else if (this.draft.type === "point" || distance(this.draft) >= 1)
          this.markers.add(this.draft);
      } catch (error) {
        feedback(error.message, true);
      }
    }
    this.drag = this.draft = null;
    this.render();
  }
}
