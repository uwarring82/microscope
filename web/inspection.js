import { $, request, feedback, download } from "./api.js";
import { measurement } from "./markers.js";
import { inspectionPNG } from "./exports.js";
import { drawMarkers, drawScaleBar } from "./overlays.js";

export class Inspection {
  constructor(markers, viewer, calibration, onOpen, getPreview) {
    Object.assign(this, { markers, viewer, calibration, onOpen, getPreview });
    this.sessions = [];
    this.record = null;
    this.dirty = false;
    this.sessionId = null;
    this.busy = false;
    for (const id of ["sample-id", "notes"])
      $(id).oninput = () => this.changed();
    $("save-inspection").onclick = () => this.run(() => this.save());
    $("new-session").onclick = () => {
      this.sessionId = null;
      $("session-name").value = "Lab inspection";
      this.render();
      feedback("The next capture will start a new session.");
    };
    $("fits-export").onclick = () =>
      this.run(async () => {
        await this.save();
        const result = await request("/api/export/fits", this.ids());
        feedback(`Raw FITS saved: ${result.path}`);
        this.showLink(result);
      });
    $("png-export").onclick = () =>
      this.run(async () => {
        if (!this.record) {
          const canvas = document.createElement("canvas");
          canvas.width = viewer.source.width;
          canvas.height = viewer.source.height;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(viewer.source, 0, 0);
          drawMarkers(
            ctx,
            markers.items,
            { x: 0, y: 0, scale: 1 },
            calibration.active?.um_per_pixel ?? null,
            null,
            Math.max(1, canvas.width / 1280),
          );
          drawScaleBar(
            ctx,
            canvas.width,
            canvas.height,
            calibration.active?.um_per_pixel,
            Math.max(1, canvas.width / 1280),
          );
          const blob = await new Promise((resolve) =>
            canvas.toBlob(resolve, "image/png"),
          );
          if (!blob) throw new Error("PNG export failed");
          download(blob, "imported-image-annotated.png");
          feedback(
            "Imported image exported locally; no sensor settings or raw data are available.",
          );
          return;
        }
        await this.save();
        const kind = $("export-kind").value,
          record = structuredClone(this.record);
        const png = await inspectionPNG(record, kind);
        const result = await request("/api/export/png", {
          ...this.ids(),
          revision: record.inspection.revision,
          kind,
          png,
        });
        feedback(`PNG saved: ${result.path}`);
        this.showLink(result);
      });
    $("marker-label").oninput = () => {
      if (markers.selected)
        markers.update(markers.selected, { label: $("marker-label").value });
    };
    $("delete-marker").onclick = () => markers.remove();
    $("undo-marker").onclick = () => markers.undo();
    $("redo-marker").onclick = () => markers.redo();
    $("marker-tool").onchange = () => {
      viewer.tool = $("marker-tool").value;
    };
    $("refresh-sessions").onclick = () =>
      this.gallery().catch((e) => feedback(e.message, true));
  }
  ids() {
    return {
      session_id: this.record.metadata.session_id,
      capture_id: this.record.metadata.capture_id,
    };
  }
  fields() {
    return {
      ...this.calibration.fields(),
      sample_id: $("sample-id").value,
      notes: $("notes").value,
      markers: this.markers.items,
    };
  }
  async run(action) {
    if (this.busy) return;
    this.busy = true;
    this.render();
    try {
      await action();
    } catch (e) {
      feedback(e.message, true);
    } finally {
      this.busy = false;
      this.render();
    }
  }
  showLink(result) {
    $("last-export").href = result.url;
    $("last-export").textContent = "Open saved export ↗";
    $("last-export").hidden = false;
  }
  changed() {
    if (this.record) this.dirty = true;
    this.render();
  }
  render() {
    const summary = this.sessions.find((s) => s.id === this.sessionId);
    const candidate = this.getPreview();
    const sources = new Set(summary?.source_types || []);
    const resolutions = new Set(summary?.resolutions || []);
    if (this.sessionId && candidate && !this.record) {
      sources.add(candidate.source_type);
      resolutions.add(candidate.resolution);
    }
    const notices = [];
    if (sources.size > 1)
      notices.push(
        "This session mixes camera and replay captures. Each capture keeps its source provenance.",
      );
    if (resolutions.size > 1)
      notices.push(
        "This session contains multiple resolutions. Replay groups frames by acquisition settings; calibration stays resolution-specific.",
      );
    $("session-warning").textContent = notices.join(" ");
    $("session-warning").hidden = !notices.length;
    const enabled = !!this.record && !this.busy;
    for (const id of ["save-inspection", "fits-export", "png-export"])
      $(id).disabled = !enabled;
    $("png-export").disabled = !(
      enabled ||
      (this.viewer.hasImage && this.viewer.editable && !this.busy)
    );
    $("png-export").textContent = this.record ? "Save PNG" : "Download PNG";
    $("marker-controls").disabled = !this.viewer.editable || this.busy;
    $("save-state").textContent = this.record
      ? `${this.dirty ? "Unsaved edits" : "Saved"} · ${this.record.metadata.capture_id.slice(-8)} · ${this.record.metadata.source_type.toUpperCase()}`
      : "Capture and freeze to save raw data and annotations.";
    $("marker-list").replaceChildren();
    const scale = this.calibration.active?.um_per_pixel ?? null;
    for (const marker of this.markers.items) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "marker-row";
      row.setAttribute(
        "aria-pressed",
        String(marker.id === this.markers.selected),
      );
      row.textContent = `${marker.label || "Marker"} · ${marker.type} · ${measurement(marker, scale)}`;
      row.onclick = () => this.markers.select(marker.id);
      $("marker-list").append(row);
    }
    const selected = this.markers.items.find(
      (m) => m.id === this.markers.selected,
    );
    if (document.activeElement !== $("marker-label"))
      $("marker-label").value = selected?.label || "";
    $("marker-label").disabled = !selected;
    $("delete-marker").disabled = !selected;
    $("undo-marker").disabled = !this.markers.past.length;
    $("redo-marker").disabled = !this.markers.future.length;
    this.viewer.scale = scale;
    this.viewer.render();
  }
  async capture(frameId) {
    this.record = await request("/api/capture", {
      frame_id: frameId,
      session_id: this.sessionId,
      session_name: $("session-name").value,
      ...this.fields(),
    });
    this.sessionId = this.record.metadata.session_id;
    this.dirty = false;
    this.viewer.editable = true;
    this.render();
    await this.gallery();
    feedback(
      `Exact raw frame saved in ${this.record.directory}. Add markers or export FITS / PNG.`,
    );
    return this.record;
  }
  async save() {
    if (!this.record) throw new Error("Capture and freeze a frame first.");
    if (this.dirty) {
      this.record = await request("/api/annotations", {
        ...this.ids(),
        revision: this.record.inspection.revision,
        ...this.fields(),
      });
      this.dirty = false;
    }
    this.render();
    return this.record;
  }
  clear() {
    this.record = null;
    this.dirty = false;
    this.viewer.editable = false;
    this.markers.replace();
    $("last-export").hidden = true;
    this.render();
  }
  async load(session, capture) {
    await this.onOpen();
    const record = await request(`/api/sessions/${session}/${capture}`);
    const response = await fetch(record.image_url);
    if (!response.ok) throw new Error("Saved PNG unavailable");
    const bitmap = await createImageBitmap(await response.blob());
    this.viewer.show(bitmap, true);
    bitmap.close();
    this.record = record;
    this.sessionId = session;
    this.viewer.editable = true;
    this.dirty = false;
    $("sample-id").value = record.inspection.sample_id;
    $("notes").value = record.inspection.notes;
    $("session-name").value = record.session_name;
    this.calibration.restore(record.inspection);
    this.markers.replace(record.inspection.markers);
    this.viewer.histogram(record.metadata);
    this.render();
    return record;
  }
  async gallery() {
    const sessions = await request("/api/sessions");
    this.sessions = sessions;
    this.render();
    $("session-gallery").replaceChildren();
    if (!sessions.length) {
      $("session-gallery").textContent = "No saved captures yet.";
      return;
    }
    for (const session of sessions) {
      const title = document.createElement("h3");
      title.textContent = session.name;
      $("session-gallery").append(title);
      for (const capture of session.captures) {
        const button = document.createElement("button");
        button.className = "capture-row";
        button.textContent = `${capture.sample_id || capture.id.slice(-8)} · ${capture.resolution} · ${capture.captured_at} · ${capture.source_type}`;
        button.onclick = () =>
          this.run(async () => {
            const record = await this.load(session.id, capture.id);
            window.dispatchEvent(
              new CustomEvent("captureopened", { detail: record }),
            );
          });
        $("session-gallery").append(button);
      }
    }
  }
}
