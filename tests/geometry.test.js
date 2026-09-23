import test from 'node:test';
import assert from 'node:assert/strict';
import { imagePoint, distance, calibratedScale, zoomAt } from '../web/geometry.js';

test('physical measurements stay independent of viewport zoom and pan', () => {
  const view = { scale: 2, x: 10, y: 20 };
  const line = { a: imagePoint({ x: 10, y: 20 }, view), b: imagePoint({ x: 610, y: 820 }, view) };
  assert.equal(distance(line), 500);
  assert.equal(calibratedScale(line, 100), 0.2);
  const feature = { a: { x: 7, y: 12 }, b: { x: 37, y: 52 } };
  assert.equal(distance(feature) * calibratedScale(line, 100), 10);
});

test('zoom preserves the image coordinate below the cursor, even at limits', () => {
  const view = { scale: 0.7, x: -120, y: 38 };
  const anchor = { x: 450, y: 200 };
  const before = imagePoint(anchor, view);
  for (const factor of [1.25, 0.00001, 1000]) {
    const after = imagePoint(anchor, zoomAt(view, anchor, factor));
    assert.ok(Math.abs(before.x - after.x) < 1e-8);
    assert.ok(Math.abs(before.y - after.y) < 1e-8);
  }
});

test('invalid calibration cannot create a false physical scale', () => {
  const line = { a: { x: 0, y: 0 }, b: { x: 10, y: 0 } };
  for (const value of [0, -1, Infinity, NaN]) assert.throws(() => calibratedScale(line, value));
  assert.throws(() => calibratedScale({ a: line.a, b: line.a }, 100));
});

