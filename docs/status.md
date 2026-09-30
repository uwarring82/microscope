# Project status

Snapshot: **30 September 2026** (software v0.2.1).
Use this page for the current state; the [logbook](logbook.md) holds the evidence
and history. For a new measurement session, follow the [session procedure](session-procedure.md). Update this page whenever a status below changes.

## Software

| Area | Status |
| --- | --- |
| Native USB capture, both modes | Working on Apple Silicon; hardware-free tests pass (native, 62 Python, 7 JavaScript) and run in macOS CI. |
| Exact-frame capture, sessions, FITS/PNG exports | Working; replay, checksum and FITS payload checks recorded in the logbook. |
| Capture provenance | Captures made **from now on** record `modified_paths`, `snapshot_at` and `snapshot_scope`. Captures made before the restart after `a44e352` record only a `modified` boolean. |
| Specimen sessions | `tools/specimen_session.py` captures fields with the matching profile attached, verifies files and draws contact sheets/ledgers; use with the [acquisition sheet](acquisition-sheet.md). Bracketing is tested against a simulated camera only. |
| Lab notes to Mattermost | `tools/labnotes.py` posts dedicated notes to `logbook-microscope` (team `oneworld`) through a local outbox. Pilot in use since 2026-09-26: the operator's personal token, from the operator's computer and in the operator's name; six notes posted (including reviewed M4 r4, phone r2 and the illustrated footprint follow-up in the M4 r4 thread on 30 Sep). A bot token is needed before other people run it. |
| Display-lattice analysis | `tools/display_lattice.py` (numpy/scipy/matplotlib, analysis only): lattice scale per colour (centroid and Fourier fits), radial term, lattice modulation for through-focus series, and colour-cycle classification by lattice frequency. Synthetic tests only; validated on the 29 September phone frames. |
| Open software issues | The rightmost raw column is always zero; its cause is not known. The sensor can saturate at about 246–254 DN without reaching 255 (seen 2026-09-24), so the server's count at 255 underestimates clipping; the session tool also reports % ≥240. Sensor black measured with the objective capped (29 Sep): 9.9–10.0 DN at gain 50, nearly flat from 515 to 3000 lines. Saturation level and exposure time in seconds are not characterized. |

## Spatial calibration

| Item | Status |
| --- | --- |
| USAF profiles, zoom marks 0.58, 2, 3, 4, 5, 6, 7 × both resolutions | **14 provisional profiles**, stored locally in `sessions/calibrations.json` (not in Git). [Method and results](calibration-usaf.md). |
| Use | Only at a recorded ring mark, with the matching resolution and the unchanged default objective/adapter. |
| Intermediate zoom settings | Rough estimates only; no accuracy assigned. The 0.58–2 range has no USAF reference; the phone lattice gives zoom 1 (see below). |
| Total measurement uncertainty | **Unknown.** Fit precision and image-analysis checks are small (mostly well below 1%), but ring return, specimen/focus height, target tolerance and field distortion are unmeasured. |
| Relative scale on a specimen | Seven landmarks seen at zooms 2, 4 and 7 on the M4 mirror agree to within 0.23%. This checks zoom-to-zoom ratios only, not absolute scale. |
| Independent display-lattice scale | iPhone 17 Pro OLED lattice, nominal pitch from 460 ppi (tolerance not stated; absolute accuracy not established), at recorded marks on 29 Sep (reviewed draft report r2, posted to the lab-book channel on 30 Sep): green centre scale −0.11% to +0.37% (centroid) or −0.18% to +0.29% (Fourier) from the USAF profiles at marks 2–7, comparable to the USAF diagnostics; **+1.46% at 0.58, unexplained**. Zoom 1: 4.4158 µm/px (full), not installed as a profile. Mode ratio 1.9991–2.0002. Local scale varies across the field by up to about 0.5% (block Fourier fits), so a centre scale is not a full-field scale. Scale changes by about −0.1% per fine-focus turn at marks 4 and 7 (+0.03% at 2). Lateral colour ≤0.22% at the centre, sign method-dependent at 6–7; axial colour indicative only (colour crosstalk). |
| Physical validation | **Planned, not started.** See the [validation plan](calibration-validation-plan.md); first step is the ring-return pilot at zooms 2/4/7. |

## M4 mirror inspection

| Item | Status |
| --- | --- |
| Data | 17 raw captures (zooms 7, 4, 0.58, 2, 5), checksum-verified, stored locally with matching provisional profiles. |
| Report | Local illustrated report, revision 2 (7 pages). Documents appearance only. |
| Interpretation | Imaging appears scatter-dominated (dark-field-like); this is inferred, since the illumination was not recorded. No cause, coating damage, dimensions or grade is assigned. |
| Software record of these captures | v0.2.1, commit `a99db05`, `modified: true`; which files were modified cannot be reconstructed. |
| Backlit comparison (24 Sep) | Used and new M4 in one mirror mount against the empty mount: used ÷ new relative transmittance 0.571 green (0.52–0.62) and 0.906 blue (0.85–0.96) under the tested assumptions; red not constrained. Consistent at three zooms; lower across all sampled fields, including background regions. Superseded by r4 below. |
| Three-mirror comparison (r4, 24 and 29 Sep) | Sensor black from capped darks (29 Sep, applied to both days); M4 removed from the cavity on 29 Sep added, with the used M4 as a bridge. Green: removed ÷ used 1.464 (±3.9%, same session, strongest result); used ÷ new 0.579 (±4.4%); removed ÷ new 0.854 (+8.5/−8.1%, through the bridge, excluding an unquantified spectral-transfer term). The bridge reproduces the used M4 within 1.1%, which does not bound spectral effects on other mirrors. Reviewed draft report r4, posted to the lab-book channel on 30 Sep. Band-integrated and setup-specific; degradation and its cause are not established. |
| Next evidence | Focus series with 2–3 illumination directions at the zoom-4 streak field; a registered repeat inspection with fixed settings; performance measured separately at the operating wavelength. Acceptance criteria not yet agreed with the setup's users. |

## Data stewardship

Raw data, sessions, calibration profiles and reports are ignored by Git. Since
30 September they are copied one way to the group's file share (run by the
university computing centre, with its own snapshots and replication), in the lab's
filing structure by data stream (`instruments/microscope/`), with `tools/archive_copy.py`:
frames write-once, other files versioned, every copy read back and verified. Local
checksum-verified ZIP packets remain. No data license or DOI has been assigned.

The workspace lies in `~/Documents`, which iCloud syncs with storage optimisation
on: `sessions/` and `artifacts/` are also stored in the operator's iCloud, and macOS
evicts local copies when the disk is short. **Decision (30 September): the workspace
stays in iCloud for now**; the verified archive copy on the group share is the
long-term copy. The copy and audit skip evicted files instead of waiting
([session procedure](session-procedure.md#6-archive-to-the-group-share)).
