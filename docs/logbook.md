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

## 2026-09-23 — Public publication

- Published the source history to [uwarring82/microscope](https://github.com/uwarring82/microscope), with `main` as the default branch and the MIT license recognized by GitHub.
- Baseline commit: `90265b9`; inspection implementation and FAIR metadata: `fc97547`. The [first hosted macOS test run](https://github.com/uwarring82/microscope/actions/runs/35854273996) passed for `fc97547`.
- Release metadata is version `0.2.0`. The `v0.2.0` tag pins this release and its dataset schema; subsequent logbook entries and fixes remain part of normal Git history.
- The source repository has no tracked recordings, sessions or vendor executables. Dataset licensing and a long-term archive/DOI remain separate stewardship steps described in [FAIR practice](fair.md).

## 2026-09-23 — v0.2.1 review fixes (offline)

- Review found replay applying the first capture's white balance to every frame. Recorded gains are now validated and selected per row, with manifest/unity fallback for legacy datasets. Manual override is explicit; switching display mode preserves the choice, and Use recorded balance restores the originals. Regression tests compare encoded PNGs and retained metadata across changing gains and replay loops.
- Versioned calibration storage as `dili-calibrations-v1`, with a published schema. Legacy bare lists remain readable and migrate atomically on the next write without losing profiles. Unknown formats are refused. Documented that reference sessions/raw data must be retained with calibration history; reference images are not duplicated.
- Session summaries expose source types and resolutions. The UI warns when the current/next capture mixes camera and replay data or resolutions; each frame's original metadata remains intact.
- Added preview-resolution focus guidance. The review reported about 0.14 s for statistics and 0.37 s for PNG encoding per full-resolution frame on the development Mac (roughly 2 fps); this is an observation, not a frame-rate guarantee.
- Replaced the FITS `TIMETYPE` keyword with custom `TSOURCE='HOSTREAD'`. Clarified that the METADATA extension is ASCII JSON stored in a byte IMAGE extension, not a second specimen image.
- Added a reproducible validation-only Astropy dependency and `tools.verify_fits`, plus CI for Astropy and NASA's distinct `fitsverify` executable. The original temporary/off-machine validation is no longer the only independent check. Synthetic exports exercise both resolutions, byte order, checksums, Unicode/quotes and JSON round trips.
- Local native tests, 29 Python tests and seven JavaScript tests passed. Astropy 8.0.1 passed both synthetic export checks in the optional local validation environment. Browser/hosted results are appended after completion.
- Browser checks passed for manual/recorded white-balance selection and color/raw switches. An isolated synthetic session showed both source/resolution notices before capture and after saving, without accessing hardware. The new calibration schema validated against a generated profile. Synthetic fixtures were kept outside the normal session root.
- User explicitly requested continued offline work. Stage-micrometer calibration at both resolutions and deliberate overexposure/saturation characterization remain **pending**. UI wording distinguishes the 255-DN endpoint count from validated sensor saturation. No physical profile, black offset or binning/crop/scaling interpretation is claimed. Release wording describes a calibration workflow.
- Hosted [macOS and independent FITS CI](https://github.com/uwarring82/microscope/actions/runs/35862324570) passed for implementation commit `15d8c69`, including Astropy and NASA fitsverify. Corrected the v0.2.0 release-note wording without moving its tag. Version `v0.2.1` records the review fixes and this validation entry.

### Next physical validation session

1. Capture a stage micrometer at both resolutions without changing the objective, adapter or field. Measure several intervals, compare field coverage and fitted scales, and record uncertainty and reference identity. Do not infer the sampling mechanism from nominal magnification or a presumed factor of two; field/feature comparisons are required.
2. At fixed illumination and gain, acquire an unsaturated baseline and progressively longer exposures, including clearly overexposed frames, at both resolutions. Save exact raw frames, maximum DN, upper-tail histograms and 255-DN fractions. Check for a stable signal plateau below 255 and repeat at another gain before treating the endpoint counter as a sensor-saturation measurement. Record black-offset characterization separately.
3. Keep these reference sessions with the calibration file and log the actual results before enabling quantitative specimen measurements. Reference comparison and flat-field correction remain later work.

## 2026-09-23 — Camera reconnection and mirror setup

- User reconnected the camera and requested imaging a half-inch mirror and its coating. Confirmed USB `0547:c004` at 480 Mb/s and switched the local server explicitly from replay to hardware mode.
- Fresh raw captures succeeded at 1280 × 960 and 2592 × 1944, with exact byte counts and SHA-256 metadata retained in a local inspection session. This verifies reopening after a stopped/disconnected interval, not unplugging during an active USB transfer.
- The initial preview at 500 exposure lines/gain 40 was nearly dark (mean 12.057 DN, maximum 32). The later full-resolution frame at 1703 lines/gain 59 showed the mirror outline/rim and a dim surface with bright specks (mean 29.078 DN; six of 5,038,848 pixels at 255). Settings and specimen setup changed between captures; these are not a controlled exposure comparison or saturation calibration.
- Saved the full-resolution raw FITS and setup notes locally. Illumination/focus optimization and any distinction between dust, reflections and coating defects remain pending. No physical scale or quantitative color interpretation was applied. Preview resolution was restored after the framing check, retaining the operator's exposure/gain settings; live viewing is running for further adjustment.


## 2026-09-23 — Physical USAF calibration at zoom 0.58

- Operator identified a Thorlabs R1DS1N, 1-inch negative USAF 1951 target and confirmed zoom-ring marking 0.58. Default objective and adapter stayed in place; their markings, target certificate/serial and illumination geometry were not recorded. The marking is not a measured total optical magnification.
- Saved primary and independent-repeat RAW8 captures at both resolutions, at 20 exposure lines/gain register 13 with unity display white balance. All four retained references had zero pixels at 255. Exact raw/PNG/FITS files, settings, frame/capture/session IDs and checksums remain local.
- Measured 12 group-2 first-to-third bar-center intervals per primary frame, covering E1–E6 and both axes. Separate provisional profiles yielded 14.67167 µm/px (1280 × 960) and 7.31291 µm/px (2592 × 1944). Repeat fit changes were −0.0824% and +0.0366%. Held-out group-3 E1 errors reached 2.04% and 0.72%, respectively; fit standard error is not total accuracy. [Method and limitations](calibration-usaf.md).
- Retained explicit raw-green measurement strips, intensity profiles, interpolated endpoints, residuals, sensitivity checks, profile snapshots, diagnostic figures and local lab notes. Verified raw hashes/lengths and histograms, reconstructed original PNGs byte-for-byte, and checked FITS primary arrays and embedded latest metadata against the source records. This was a payload check, not a new independent Astropy/fitsverify standards validation.
- The rightmost zero column persists in all four references, was preserved and lies outside every measurement strip. Target tolerance, target-plane tilt, full-field distortion, focus dependence, repeated mechanical return to 0.58 and a stage-micrometer comparison remain pending. No binning/crop/scaling mechanism or optical resolution limit is inferred.
- Numerical sanity check: synthetic trapezoid bars recovered an exact 80-pixel first-to-third interval on both axes. Repository checks passed (native tests, 29 Python tests, seven JavaScript tests). Browser reopening restored the measured profile and reference markers. Documentation changed; SDK/UI runtime behavior did not.

## 2026-09-23 — Zoom series: collection before analysis

- Operator requested collecting further settings before analysis. The first additional set was initially reported as zoom 1, then explicitly corrected to zoom 2. Updated annotation revisions and FITS exports preserve that correction history without changing raw bytes, checksums or acquisition timestamps. A subsequent set was collected at zoom 4. Each setting has two independent frames at each resolution, at 20 exposure lines/gain 13, with exact raw data, original PNGs, raw FITS, metadata and lab notes. Raw sizes/checksums were verified and all eight frames had zero pixels at 255.
- Zoom-2 and zoom-4 captures explicitly remain uncalibrated; the 0.58 profiles were not applied and no scale fit was performed. Acquisition was stopped after collection and the operator was told the next zoom setting could be selected. Subsequent zooms require their own recorded markings and reference data.


## 2026-09-23 — Zoom-7 reference collection

- Operator confirmed zoom 7. Saved two raw captures per resolution at 20 exposure lines/gain 13; those initial references were dim (primary raw maxima 31 DN in preview and 43 DN at full resolution).
- Retained the initial frames and added two brighter captures per resolution at 120 lines/gain 13, giving primary maxima 128 DN and 191 DN. All eight zoom-7 frames had zero pixels at 255. Saved exact RAW8, original PNG, raw FITS, acquisition settings, identities/checksums and lab notes. Target bars were visually checked for collection quality; no new spatial fit or resolution measurement was performed.
- The current series comprises zoom markings 0.58, 2, 4 and 7. The first has provisional profiles; later settings remain explicitly uncalibrated pending the operator-requested analysis phase. The local evidence packet preserves the zoom-1-to-2 correction history, all raw frames and reference sessions, latest annotations/FITS, analysis records and a checksum inventory. No raw images or private paths are published to Git.
