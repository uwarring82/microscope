# Development logbook

Record consequential implementation decisions, evidence, limitations and follow-up here. Entries describe completed work or explicitly mark validation pending; Git commits provide the exact source history. Do not put specimen images, secrets, private server paths or vendor binaries in this log.

## 2026-09-23 — Hardware discovery and initial SDK (retrospective)

- Identified the Di-Li-labelled 5MP-B CMOS camera as USB `0547:c004`, revision `a000`, vendor-specific interface and bulk endpoint `0x82`. The manufacturer string is not a serial number; the device is not UVC.
- Inspected a user-supplied legacy driver archive and a publicly available ISListen x86_64 executable statically. No legacy executable or installer was run. Vendor binaries remain outside the source repository. Detailed evidence: [driver discovery](driver-discovery.md).
- Recovered initialization, exposure-line, gain, acknowledgement and raw-frame framing behavior. Implemented a native C/libusb driver and Python binding for Apple Silicon.
- Verified repeated capture/start/stop and illuminated aluminium surface imaging. Full resolution needed a corrected rounded-up transfer length of 5,039,616 bytes; the image contains exactly 5,038,848 pixel bytes, with no padding or upscaling. Both resolution modes and transitions were tested.
- Implemented RGGB bilinear color reconstruction and fixed neutral-reference white balance. Resolved smartphone display subpixels provide a useful visual check; quantitative color, timing, orientation and optical fidelity remain uncalibrated. Evidence: [SDK notes](native-sdk.md).

## 2026-09-23 — Offline UI development dataset (retrospective)

- Saved 18 original raw frames (67,838,976 bytes): 12 at full resolution and six at preview resolution, with exposure brackets and gain 40. Verified all lengths and SHA-256 hashes, then closed USB so the camera could be disconnected.
- Added explicit offline replay, grouped by acquisition settings. It uses the normal color pipeline and never discovers or opens the camera. Preserved timestamps and source files. Added tests for replay loops, corruption, path containment and unavailable hardware controls.
- Baseline checks passed: native USB/color tests, 17 Python tests and three JavaScript geometry tests.

## 2026-09-23 — Inspection release, capture foundation

- Initialized Git and recorded the working baseline. Removed private laboratory host/mount paths from the unpublished baseline before public distribution; preserved relative binary inventory and checksums.
- Accepted the design review's central correction: browser freeze alone is not a raw capture. Added an eight-frame cache, immutable frame IDs, metadata lookup and exact-frame capture. Expired IDs are refused instead of being replaced with a fresh frame.
- Sessions reuse `dili-raw-dataset-v1`. Raw bytes, processing metadata, original preview PNG and annotation/calibration JSON are saved on the server. Atomic manifest updates define committed captures; annotation revisions prevent silent stale writes.
- Raw histograms/clipping are calculated before white balance. Added a relative focus measure on a central same-phase green region; this is not an autofocus or calibrated resolution measurement.
- Added persistent, resolution-specific calibration profiles with a multi-interval fit, standard error, reference capture links and raw checksums. No calibration is inferred from objective magnification or transferred between resolution modes.
- Split the UI into API, viewing, marker, calibration, inspection and export modules. Added editable lines, rectangles, circles and points, labels, undo/redo, saved sessions and capture reopening.
- Added raw FITS export preserving acquisition row order and Bayer phase, with explicit non-astronomical exposure/gain units and a JSON metadata extension. Inspection PNGs use the saved capture and annotation revision rather than current controls.
- Expanded automated tests to cover exact capture identity, eviction, raw-vs-RGB clipping, calibration matching, annotation revisions, replay round trips, FITS row order/provenance and marker editing. Validation results and browser checks are recorded below when complete.

## 2026-09-23 — Public repository and FAIR preparation

- User requested public GitHub publication, a dedicated logbook and FAIR practice; explicitly selected the MIT code license.
- Added the license, citation metadata, CodeMeta, versioned dataset schema, units/coordinate documentation and a FAIR stewardship guide. New captures retain software version, Git commit and working-tree state; sessions receive UUID URNs.
- Raw datasets, saved sessions, installed dependencies, generated reports and vendor binaries are excluded from Git. Data licensing remains an explicit dataset-owner decision. No DOI, archive deposit or full FAIR certification is claimed.
- Added a macOS GitHub Actions workflow running the same hardware-free test suite with Python 3.12 and Node.js 24. Its initial hosted result is recorded with publication below.

## 2026-09-23 — Inspection release validation

- Passed `make test`: native fake-USB and color checks, 25 Python tests, and seven JavaScript geometry/marker tests. The camera stayed disconnected throughout this release's development.
- API replay check saved a retained full-resolution frame after stopping playback and changing display processing. The saved raw checksum, original color gains/exposure and PNG bytes still matched the displayed frame. Annotation requests larger than the old 1 KB request limit were accepted; stale revisions were rejected by tests.
- Independently read the full-resolution FITS with Astropy: strict verification returned no warnings, the primary image was unsigned 8-bit 1944 × 2592, and every raw byte and SHA-256 matched the capture. Verified RGGB phase, top-down row order, sensor-line exposure and JSON provenance. JSON Schema validation passed for both the original 18-frame recording and a saved inspection session.
- Browser replay checks covered capture/freeze, drawing multiple markers, notes, reopening from the gallery and changing a marker label. Fixed label edits to persist on input. Verified a 3552 × 1944 inspection sheet with the full native image, markers, saved settings, raw histogram, notes and visible UNCALIBRATED status. Fixed report-height trimming and rejected overlong reports instead of silently clipping them.
- Imported-image profile matching now uses the image's own dimensions. Calibration fits and profile mismatch handling were tested with synthetic references; no physical calibration was assigned to the smartphone image.
- FITS header strings replace control/non-ASCII characters, while the JSON extension preserves complete original metadata. Added a regression case for a multiline Unicode objective label.
- Public-source review found no private host/mount paths, credentials, specimen data or vendor binaries among publication files. Raw recordings, generated reports and sessions remain local and ignored.
