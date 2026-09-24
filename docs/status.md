# Project status

Snapshot: **24 September 2026** (software v0.2.1).
Use this page for the current state; the [logbook](logbook.md) holds the evidence
and history. Update this page whenever a status below changes.

## Software

| Area | Status |
| --- | --- |
| Native USB capture, both modes | Working on Apple Silicon; hardware-free tests pass (native, 41 Python, 7 JavaScript) and run in macOS CI. |
| Exact-frame capture, sessions, FITS/PNG exports | Working; replay, checksum and FITS payload checks recorded in the logbook. |
| Capture provenance | Captures made **from now on** record `modified_paths`, `snapshot_at` and `snapshot_scope`. Captures made before the restart after `a44e352` record only a `modified` boolean. |
| Specimen sessions | `tools/specimen_session.py` captures fields with the matching profile attached, verifies files and draws contact sheets/ledgers; use with the [acquisition sheet](acquisition-sheet.md). Bracketing is tested against a simulated camera only. |
| Open software issues | The rightmost raw column is always zero; its cause is not known. The sensor can saturate at about 246–254 DN without reaching 255 (seen 2026-09-24), so the server's count at 255 underestimates clipping; the session tool also reports % ≥240. Saturation level, black offset (about 10 DN observed) and exposure time in seconds are not characterized. |

## Spatial calibration

| Item | Status |
| --- | --- |
| USAF profiles, zoom marks 0.58, 2, 3, 4, 5, 6, 7 × both resolutions | **14 provisional profiles**, stored locally in `sessions/calibrations.json` (not in Git). [Method and results](calibration-usaf.md). |
| Use | Only at a recorded ring mark, with the matching resolution and the unchanged default objective/adapter. |
| Intermediate zoom settings | Rough estimates only; no accuracy assigned. The 0.58–2 range has no interior reference. |
| Total measurement uncertainty | **Unknown.** Fit precision and image-analysis checks are small (mostly well below 1%), but ring return, specimen/focus height, target tolerance and field distortion are unmeasured. |
| Relative scale on a specimen | Seven landmarks seen at zooms 2, 4 and 7 on the M4 mirror agree to within 0.23%. This checks zoom-to-zoom ratios only, not absolute scale. |
| Physical validation | **Planned, not started.** See the [validation plan](calibration-validation-plan.md); first step is the ring-return pilot at zooms 2/4/7. |

## M4 mirror inspection

| Item | Status |
| --- | --- |
| Data | 17 raw captures (zooms 7, 4, 0.58, 2, 5), checksum-verified, stored locally with matching provisional profiles. |
| Report | Local illustrated report, revision 2 (7 pages). Documents appearance only. |
| Interpretation | Imaging appears scatter-dominated (dark-field-like); this is inferred, since the illumination was not recorded. No cause, coating damage, dimensions or grade is assigned. |
| Software record of these captures | v0.2.1, commit `a99db05`, `modified: true`; which files were modified cannot be reconstructed. |
| Backlit comparison (24 Sep) | Used and new M4 in one mirror mount against the empty mount: used ÷ new relative transmittance 0.571 green (0.52–0.62) and 0.906 blue (0.85–0.96) under the tested assumptions; red not constrained. Consistent at three zooms; lower across all sampled fields, including background regions. Local draft report r2. Band-integrated and setup-specific; not a reflectance, spectrum or diagnosis; black offset from opaque areas (dark frames pending). |
| Next evidence | Focus series with 2–3 illumination directions at the zoom-4 streak field; a registered repeat inspection with fixed settings; performance measured separately at the operating wavelength. Acceptance criteria not yet agreed with the setup's users. |

## Data stewardship

Raw data, sessions, calibration profiles and reports stay local and are ignored
by Git. They are backed up only as local checksum-verified ZIP packets, with no
external backup. No data license or DOI has been assigned.
