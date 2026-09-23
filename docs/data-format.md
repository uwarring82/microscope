# Inspection sessions, metadata and exports

## Exact-frame capture

Each served preview has an `X-Frame-ID`. The server retains eight raw frames and their immutable acquisition/display metadata (at most about 40 MB of raw pixel payload at full resolution). `GET /api/frames/{id}` returns its metadata. `POST /api/capture` with `frame_id` saves that exact frame; it never calls the camera to obtain a replacement. An evicted ID returns HTTP 409. Stopping acquisition or the idle USB lease does not discard retained frames; restarting the server does. Capture & freeze commits the selected frame to disk before it can be lost to later previews.

## Session layout

The default root is `sessions/`, overridable with `--sessions PATH`. Each `session-…/` is a `dili-raw-dataset-v1` dataset:

- `manifest.json`: session UUID URN, name, creation time, data-license status, frame inventory, software provenance and checksums.
- `capture-….raw`: immutable row-major sensor bytes, one unsigned 8-bit DN per pixel. No USB framing or processing.
- `capture-….json`: the acquisition and display metadata of the exact served frame.
- `capture-….annotations.json`: sample ID, notes, manually selected objective/configuration, complete calibration snapshot, editable marker coordinates and revision.
- `capture-….png`: the captured preview reconstructed from the same raw frame and the saved processing settings.
- `capture-…-rN-raw.fits` and `…-rN-{inspection,annotated,image-only}.png`: exports of annotation revision N. PNG exports have companion metadata JSON.

The manifest is atomically replaced after all capture files are saved. Each annotation update is atomic and checks the prior revision to prevent silent overwrites from another tab. Failed writes may leave unreferenced files; committed captures are defined by the manifest. Do not delete raw files to clean up exports. Back up the session root separately from the source repository.

Replay with `python3 server.py --replay sessions/session-…`. The [JSON Schema](../schemas/dili-raw-dataset-v1.schema.json) permits extension fields for compatibility. The loader additionally enforces matching dimensions, exact file byte counts, in-directory filenames and SHA-256 hashes.

## Units and coordinates

Images use x increasing right and y increasing down, with `(0, 0)` at the acquired top-left pixel. RGGB means red at even x/even y and blue at odd x/odd y. Marker coordinates are image pixels, independent of viewport zoom/pan. Types are `line`, `rectangle`, `circle` and `point`; each has an ID, label and `a`/`b` points. A circle uses `a` as its center and `b` on its radius; a point uses coincident endpoints. Rectangle dimensions and areas are derived from opposite corners.

Exposure is **sensor lines**, gain is **sensor register units**, intensities are **8-bit digital numbers**, and spatial scale is **µm/image pixel**. Host timestamps record read completion in UTC, not hardware exposure start. Replay preserves the original acquisition timestamp and records its dataset/file/SHA-256 provenance. White balance applies only to the derived display. Raw clipping counts sensor values exactly 255; the zero fraction is shown separately and is not interpreted as optical black. The focus score is the mean squared difference between same-phase raw green samples in a central region up to 256 × 256 pixels. It depends on exposure, specimen and sampling; it is not a calibrated optical-resolution measurement.

## Spatial calibration

Profiles are stored in `sessions/calibrations.json` and keyed by the exact objective, optical configuration and acquisition resolution. The objective is manually confirmed; it cannot be detected from this camera. No profile is scaled between 1280 × 960 and 2592 × 1944. A profile uses at least three measured stage-micrometer intervals. A least-squares fit through the origin estimates µm/px. The stored standard error describes fit precision only, excluding reference accuracy, field distortion and positioning systematics. Reference endpoints, raw checksums, capture IDs and residuals are retained. The active profile or UNCALIBRATED state is always visible; every export's metadata records the calibration state.

## FITS

Exports follow [FITS 4.0](https://fits.gsfc.nasa.gov/standard40/fits_standard40aa-le.pdf): 80-byte cards and 2880-byte padded header/data blocks; an unsigned 8-bit (`BITPIX=8`) primary image. Sensor rows are preserved byte for byte. `ROWORDER='TOP-DOWN'` and `BAYERPAT='RGGB'` describe the stored array. A viewer drawing axis 2 upward may display it inverted; we deliberately do not flip rows or alter the Bayer phase. The raw SHA-256 is computed on sensor bytes without FITS padding.

Use custom `EXPLINES` and `SENSGAIN`; `EXPTIME` and `GAIN` are not emitted because the corresponding seconds and electrons/ADU are unknown. `DATE-OBS`, `TIMESYS`, and `TIMETYPE` describe the original UTC host-read timestamp. `RAWSHA`, `FRAMEID`, `CAPTID`, `SRCFILE`, `SRCSHA`, `SRCDATA`, `CALPROF`, `SCALEUM` and `SCALERR` retain provenance and calibration. Long strings and full metadata, including annotations, Unicode text and nested provenance, are stored as ASCII-escaped JSON in a one-dimensional unsigned-byte IMAGE extension named `METADATA`.

## Local API

All mutations require JSON, loopback Host validation, same-origin Origin when supplied, and `X-Microscope-Client: local-ui`. Acquisition requests are limited to 1 KB, annotation/profile/capture requests to 256 KB, and PNG export requests to 32 MB (decoded PNG maximum 24 MB). Paths are generated IDs, not client-supplied filesystem paths.

| Route | Purpose |
|---|---|
| `GET /api/sessions` | Session/capture inventory |
| `GET /api/sessions/{session}/{capture}` | Saved metadata, annotation snapshot and image URL |
| `POST /api/capture` | Exact retained frame into a new or existing session |
| `POST /api/annotations` | Revision-checked marker/note/calibration update |
| `GET, POST /api/profiles` | Read or fit and save persistent calibration profiles |
| `POST /api/export/fits` | Save raw FITS derived from the saved capture |
| `POST /api/export/png` | Save a browser-rendered PNG with the matching annotation revision |

PNG settings and histograms are rendered from the saved capture metadata, never current acquisition controls. Browser-generated PNGs are inspection derivatives; their source and annotation snapshot are retained in companion JSON. Original PNG/FITS files remain distinguishable by capture ID and annotation revision.
