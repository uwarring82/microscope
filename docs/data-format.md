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

Replay uses each frame row's `white_balance_gains`, falling back to the manifest's gains (or unity) for older recordings. A manual white-balance/reset operation overrides those gains until **Use recorded balance** is selected. Switching color/raw display preserves that choice. Served frame metadata records the actual gains and `white_balance_source` (`recorded` or `manual`). Acquisition-setting groups stay independent of display gains, so a loop can faithfully contain different balances.

Sessions may contain multiple resolutions and both camera/replay captures. The API returns `source_types` and `resolutions` in the session inventory and `session_summary` with a saved capture. The UI shows a persistent notice for mixed sessions, including when the next preview capture would create a mixture. Every frame retains its own settings and provenance; replay still groups by resolution, exposure and sensor gain.

## Software snapshot provenance

New `software` records retain version/repository/license, `commit` and `modified`,
and add `modified_paths`, `snapshot_at` and `snapshot_scope`.
`modified_paths` is a sorted list of repository-relative staged, unstaged and
untracked paths, including both source/destination names for renames or copies.
Paths with spaces, tabs, newlines or Unicode are preserved. Git-ignored files
(including local sessions, artifacts and generated binaries) are excluded;
submodule changes identify the submodule path, not every nested file.
An empty list with `modified: false` means a successful clean status check;
`null` means unknown. If status fails after a successful commit lookup, the
known commit is retained with unknown modified state/paths. Paths identify
which files were involved, not their contents; no diff or file-content hash is
claimed.

`build_info()` remains cached at first use per process to avoid running Git on
every preview. `snapshot_scope: "process_first_use"` makes this explicit, and
`snapshot_at` records the UTC start of that observation. It is not the acquisition
timestamp or proof of exactly which modules/binary bytes were loaded; the Git
commands are not an atomic filesystem snapshot. Restart the server after source
changes. This patch does not refresh an already-running server's cached record.

Older captures with only a commit and boolean remain valid and unchanged.
Their modified paths cannot be reconstructed reliably from the current tree or
later Git history. Optional fields extend the v1 schema without a format bump.
For the status/path convention, see [Git's porcelain v1 documentation](https://git-scm.com/docs/git-status#_porcelain_format_version_1).

## Units and coordinates

Images use x increasing right and y increasing down, with `(0, 0)` at the acquired top-left pixel. RGGB means red at even x/even y and blue at odd x/odd y. Marker coordinates are image pixels, independent of viewport zoom/pan. Types are `line`, `rectangle`, `circle` and `point`; each has an ID, label and `a`/`b` points. A circle uses `a` as its center and `b` on its radius; a point uses coincident endpoints. Rectangle dimensions and areas are derived from opposite corners.

Exposure is **sensor lines**, gain is **sensor register units**, intensities are **8-bit digital numbers**, and spatial scale is **µm/image pixel**. Host timestamps record read completion in UTC, not hardware exposure start. Replay preserves the original acquisition timestamp and records its dataset/file/SHA-256 provenance. White balance applies only to the derived display. Raw clipping counts sensor values exactly 255; the zero fraction is shown separately and is not interpreted as optical black. The focus score is the mean squared difference between same-phase raw green samples in a central region up to 256 × 256 pixels. It depends on exposure, specimen and sampling; it is not a calibrated optical-resolution measurement.

The sensor's actual saturation level and black offset have not been characterized. The 255-DN fraction can miss saturation below that endpoint; zero percent is not proof of an unsaturated image. A deliberately overexposed hardware sequence is still pending. Prefer 1280 × 960 for responsive focus adjustment: the review measured roughly 0.14 s for raw statistics and 0.37 s for full-resolution PNG encoding on the development Mac, giving about 2 fps, not a guaranteed rate.

## Spatial calibration

Profiles are stored in `sessions/calibrations.json` and keyed by the exact objective, optical configuration and acquisition resolution. The objective is manually confirmed; it cannot be detected from this camera. No profile is scaled between 1280 × 960 and 2592 × 1944. A profile uses at least three measured intervals with known lengths, normally from a stage micrometer. Known USAF bar-center spacings can also be supplied through the same API; see the [physical USAF calibration and limitations](calibration-usaf.md). The current UI still labels the workflow as stage-micrometer calibration. A least-squares fit through the origin estimates µm/px. The stored standard error describes fit precision only, excluding reference accuracy, field distortion and positioning systematics. Reference endpoints, raw checksums, capture IDs and residuals are retained. A matched profile identifies a reference scale; it does not validate mechanical zoom return or transfer to a different specimen/focus plane. Use the current USAF profiles only at their recorded ring markings; specimen applications remain provisional pending those checks. The active profile or UNCALIBRATED state is always visible; every export's metadata records the calibration state.

The file envelope is `{"format":"dili-calibrations-v1","profiles":[...]}`; see its [schema](../schemas/dili-calibrations-v1.schema.json). The API continues to return a profile list. Legacy v0.2.0 bare lists are readable and are migrated atomically on the next profile save, preserving existing profiles. Unknown format versions are refused. **Keep and back up every referenced session**, including its raw files and metadata, with the calibration file. IDs/checksums and annotation snapshots cannot reconstruct a deleted reference image. References are not copied to a separate archive by this version. No stage-micrometer profile has yet been physically validated.

## FITS

Exports follow [FITS 4.0](https://fits.gsfc.nasa.gov/standard40/fits_standard40aa-le.pdf): 80-byte cards and 2880-byte padded header/data blocks; an unsigned 8-bit (`BITPIX=8`) primary image. Sensor rows are preserved byte for byte. `ROWORDER='TOP-DOWN'` and `BAYERPAT='RGGB'` describe the stored array. A viewer drawing axis 2 upward may display it inverted; we deliberately do not flip rows or alter the Bayer phase. The raw SHA-256 is computed on sensor bytes without FITS padding.

Use custom `EXPLINES` and `SENSGAIN`; `EXPTIME` and `GAIN` are not emitted because the corresponding seconds and electrons/ADU are unknown. `DATE-OBS` and `TIMESYS='UTC'` describe the original UTC timestamp; the custom `TSOURCE='HOSTREAD'` explicitly identifies host-read completion, not exposure start. This replaces v0.2.0's `TIMETYPE` keyword in new exports. `RAWSHA`, `FRAMEID`, `CAPTID`, `SRCFILE`, `SRCSHA`, `SRCDATA`, `CALPROF`, `SCALEUM` and `SCALERR` retain provenance and calibration. Long strings and full metadata, including annotations, Unicode text and nested provenance, are stored as ASCII-escaped JSON in a one-dimensional unsigned-byte IMAGE extension named `METADATA`.

That extension is a project convention, **not another specimen image**. Generic FITS viewers may display its bytes as pixels. `CONTENT='JSON-ASCII'` identifies the encoding; with Astropy, decode it using `json.loads(hdus['METADATA'].data.tobytes().decode('ascii'))`. The primary HDU alone is the raw sensor image.

`python -m tools.verify_fits` generates synthetic exports at both resolutions and checks them independently with Astropy, including exact raw bytes and JSON round trips. Install `requirements-validation.txt` in an optional Python 3.12+ environment. Add `--fitsverify` when NASA's separate `fitsverify` executable is installed; CI runs both verifiers. These tools are validation dependencies only, not SDK/server requirements.

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
