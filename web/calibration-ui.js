import { $, request, feedback } from "./api.js";
import { distance } from "./geometry.js";

export class CalibrationUI {
  constructor(getRecord, getResolution, getMarker, onchange) {
    Object.assign(this, { getRecord, getResolution, getMarker, onchange });
    this.profiles = [];
    this.active = null;
    this.references = [];
    $("profile").onchange = () => {
      this.active =
        this.profiles.find((p) => p.id === $("profile").value) || null;
      if (this.active) {
        $("objective").value = this.active.objective;
        $("optical-configuration").value = this.active.optical_configuration;
      }
      this.render();
      onchange();
    };
    for (const id of ["objective", "optical-configuration"])
      $(id).oninput = () => {
        if (
          this.active &&
          (this.active.objective !== $("objective").value.trim() ||
            this.active.optical_configuration !==
              $("optical-configuration").value.trim())
        )
          this.active = null;
        this.render();
        onchange();
      };
    $("add-reference").onclick = () => this.addReference();
    $("clear-references").onclick = () => {
      this.references = [];
      this.render();
    };
    $("save-profile").onclick = () =>
      this.save().catch((e) => feedback(e.message, true));
  }
  async load() {
    this.profiles = await request("/api/profiles");
    this.render();
  }
  fields() {
    return {
      objective: $("objective").value.trim(),
      optical_configuration: $("optical-configuration").value.trim(),
      calibration_id: this.active?.id || null,
    };
  }
  restore(inspection) {
    this.active = inspection?.calibration || null;
    $("objective").value = inspection?.objective || "";
    $("optical-configuration").value = inspection?.optical_configuration || "";
    this.render();
  }
  render() {
    const resolution = this.getResolution();
    if (this.active?.resolution !== resolution) this.active = null;
    const selected = this.active?.id || "";
    $("profile").replaceChildren(
      new Option("Uncalibrated · pixels", ""),
      ...this.profiles
        .filter((p) => p.resolution === resolution)
        .map(
          (p) =>
            new Option(
              `${p.name} · ${p.objective} · ${p.optical_configuration}`,
              p.id,
            ),
        ),
    );
    $("profile").value = selected;
    const p = this.active;
    $("calibration-banner").textContent = p
      ? `${p.name} · ${p.objective} · ${p.optical_configuration} · ${p.resolution} · ${p.um_per_pixel.toPrecision(5)} ± ${p.fit_standard_error.toPrecision(2)} µm/px (fit SE)`
      : `UNCALIBRATED · ${$("objective").value || "objective not specified"} · ${resolution || "no image"}`;
    $("scale-value").textContent = p
      ? `${p.um_per_pixel.toPrecision(5)} µm/px`
      : "Not set";
    $("profile-detail").textContent = p
      ? `${p.references.length} intervals · ${p.created_at.slice(0, 10)}. ${p.uncertainty_note}. Objective selection is manual.`
      : "Select a matching profile only after confirming the objective and optical configuration. Profiles never scale between resolution modes.";
    $("reference-count").textContent =
      this.references
        .map(
          (r, i) => `${i + 1}: ${distance(r).toFixed(2)} px = ${r.known_um} µm`,
        )
        .join(" · ") || "No reference intervals yet.";
    $("save-profile").disabled = this.references.length < 3;
  }
  addReference() {
    const record = this.getRecord(),
      marker = this.getMarker(),
      known = Number($("known-distance").value);
    if (
      !record ||
      !marker ||
      marker.type !== "line" ||
      distance(marker) < 1 ||
      !Number.isFinite(known) ||
      known <= 0
    )
      return feedback(
        "Capture a stage-micrometer image, select a line, and enter its known length in µm.",
        true,
      );
    this.references.push({
      session_id: record.metadata.session_id,
      capture_id: record.metadata.capture_id,
      a: { ...marker.a },
      b: { ...marker.b },
      known_um: known,
    });
    this.render();
    feedback(
      "Reference interval added. Measure at least three intervals, preferably spanning different lengths.",
    );
  }
  async save() {
    const profile = await request("/api/profiles", {
      name: $("profile-name").value,
      ...this.fields(),
      references: this.references,
    });
    this.profiles.push(profile);
    this.active = profile;
    this.references = [];
    this.render();
    this.onchange();
    feedback(
      "Calibration profile saved. Its fit uncertainty is shown with the scale.",
    );
  }
}
