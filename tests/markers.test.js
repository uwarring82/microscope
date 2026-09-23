import test from "node:test";
import assert from "node:assert/strict";
import { Markers, measurement, translate, hitTest } from "../web/markers.js";

const line = {
  id: "one",
  type: "line",
  label: "gap",
  a: { x: 10, y: 20 },
  b: { x: 110, y: 20 },
};
test("multiple markers retain image coordinates with independent edits and undo/redo", () => {
  const model = new Markers();
  model.add(line);
  model.add({ ...line, id: "two", label: "other" });
  model.update("one", { label: "changed" });
  assert.equal(model.items[1].label, "other");
  model.undo();
  assert.equal(model.items[0].label, "gap");
  model.redo();
  assert.equal(model.items[0].label, "changed");
  assert.deepEqual(model.items[0].a, { x: 10, y: 20 });
  model.select("two");
  model.remove();
  assert.equal(model.items.length, 1);
  model.undo();
  assert.equal(model.items.length, 2);
});
test("measurements use the supplied physical scale without modifying coordinates", () => {
  assert.equal(measurement(line), "100.00 px");
  assert.equal(measurement(line, 0.2), "20.00 µm");
  assert.equal(measurement({ ...line, type: "circle" }, 0.2), "Ø 40.00 µm");
  assert.equal(
    measurement({ ...line, type: "rectangle", b: { x: 30, y: 30 } }, 0.2),
    "4.00 × 2.00 µm; 8.00 µm²",
  );
});
test("whole-shape movement clamps the shape without changing its length", () => {
  const moved = translate(line, -1000, 1000, 1280, 960);
  assert.deepEqual(moved.a, { x: 0, y: 959 });
  assert.deepEqual(moved.b, { x: 100, y: 959 });
  assert.equal(measurement(moved), "100.00 px");
});
test("selection chooses visible endpoints and topmost overlapping markers", () => {
  assert.equal(hitTest([line], { x: 11, y: 20 }, 3).handle, "a");
  assert.equal(
    hitTest([line, { ...line, id: "top" }], { x: 50, y: 20 }, 3).marker.id,
    "top",
  );
  assert.equal(hitTest([line], { x: 500, y: 500 }, 3), null);
});
