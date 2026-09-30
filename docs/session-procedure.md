# Measurement session procedure

The procedure used for the September 2026 mirror sessions, from preparation to the Mattermost lab note and the
archive copy on the group share. Reuse
it for new measurements with the instrument. Capture details are on the [acquisition sheet](acquisition-sheet.md);
scale limits are in the [USAF calibration](calibration-usaf.md) and [validation plan](calibration-validation-plan.md).
Proposed measurements for the next session: [next session](next-session.md).
The worked example is the backlit used-vs-new mirror comparison of 24 September 2026 (logbook entries of
24–26 September). Its analysis and report builders are in the local packet `artifacts/captures/m4-comparison-20260924/`,
which is not in Git; use them as templates.

## 1. Before the session

- **Software state.** Commit or stash code changes, then start `python3 server.py`. Captures record the commit and any
  modified paths. Check that the dashboard shows **USB connected · native SDK**.
- **Plan the comparison before touching the specimen.** Name the objects, the zoom marks, one fixed gain and an
  exposure series. Also plan the references:
  - an **empty-holder or bare-backlight frame** for each object configuration, at the same zoom, gain and exposures;
  - **dark frames** with the light path blocked, at every exposure used, before and after the series (measures the
    black offset directly);
  - **repeats**: alternate the objects (A → reference → B → reference → A …) with at least three placements each.
  - **dark frames with the objective capped** (not only the light source off): room light enters through the
    specimen plane and raises uncapped "dark" frames with exposure. The capped sensor black is flat at about 9.9 DN.
  - **a bridge sample** measured in an earlier session, whenever results are to be compared across days: the
    source brightness and spectrum can differ between sessions.
- **Room lights off** during backlit or transmission runs; if they must stay on, keep them unchanged for the run.
- **Record the setup** that later analysis depends on: illumination source, geometry and settings; the mount or holder,
  which is the same for all objects if their transmission is to be compared; orientation and the side facing the camera;
  packaging, cleaning and handling. Transcribe labels verbatim.
- Choose a series name per object, for example `<object>-<yyyymmdd>`, and keep reference frames in their own series.

## 2. Capture

For each field:

1. Set the zoom ring **on a mark** and note the approach direction. Only marked settings have a scale; zoom 1 has none.
2. **Probe exposures** on unsaved frames at the fixed gain. Judge clipping by the **share of pixels ≥240 DN**, not the
   count at 255: this sensor saturates at about 246–254 DN. Choose a doubling series that includes an unclipped frame
   and gives the weakest signal of interest **at least about 50 DN above black**.
3. Capture with the fixed gain and the series:
   `python3 -m tools.specimen_session capture SERIES --sample "LABEL" --zoom Z --field NAME --note "..." --illumination "..." --gain G --exposures 129,258,515,1031`
4. **Do not move the dashboard sliders during a capture.** The tool checks each saved frame against the requested gain
   and exposure, and stops the field if they differ. Afterwards the live view stays at the series gain.
5. If the operator corrects or adds information later, record it as an **annotation revision**, never by editing raw
   data. Re-export the FITS files; earlier revisions stay.

After the session: `python3 -m tools.specimen_session verify SERIES` and `overview SERIES` for every series. Then write a
logbook entry that covers collection only, with no interpretation yet.

## 3. Analysis

- Work in a local packet folder `artifacts/captures/<topic>-<yyyymmdd>/`. Scripts there read only checksum-verified raw
  frames.
- Use raw Bayer planes (R, G1, G2, B) with no demosaicing or white balance, and exclude the always-zero rightmost column.
- **Black offset:** from the dark frames, or failing that from opaque areas; it rises with exposure. Compare frames only
  at equal zoom, gain and exposure. Set validity windows for the reference (for example 30–235 DN) and the specimen
  (<235 DN). Use an exposure only if most of the region of interest is valid.
- Statistic: the median, cross-checked against an area-weighted sum.
- **Uncertainty:** observed variations (between zooms and exposures, between placements) plus sensitivity tests. For
  the offset, test both a shared error and independent offsets per frame. Add the terms linearly and call the result
  an envelope **for the tested assumptions**, not a confidence interval. Say when a channel is not constrained.
- **Spatial claims:** support "lower everywhere sampled" with percentiles of both objects. Area detected by a
  segmentation rule is not the total affected area.

## 4. Report

- Build Markdown, HTML and PDF from the results file with a script; the PDF comes from headless Chrome. Check every page
  visually.
- Required contents:
  - specimens and setup, with unrecorded items stated;
  - methods: acquisition timeline, a **raw-data atlas** of every frame with ID (#01…), date and UTC time, settings and
    capture ID, and analysis;
  - results with **provisional scale bars** on every image, limitations, interpretation and next steps;
  - a **frame ledger** giving each frame's role and checksum.
- Name what is not established: cause, reflectance at the operating wavelength, spectra, history. Describe features,
  never diagnose.
- Number revisions (Draft r1, r2 …) with the build time, and keep earlier revisions under `revisions/`. An independent
  review round (for example another agent recomputing medians from the raw data) caught overstated claims last time.

## 5. Lab note to Mattermost

- Write one dedicated note per result, not per capture, in `artifacts/labnotes/notes/`:
  - a short header (id, label `[RUN]`, `[NOTE]`, `[SETTING]` or `[SERVICE]`, title, UTC event time, author, attachments);
  - a Markdown body understandable without repository access;
  - 2–3 low-resolution previews made with `python3 -m tools.labnotes preview FIG.png --out DIR`, plus the report PDF if
    useful.
- `python3 -m tools.labnotes check NOTE.md` prints the exact post. The operator approves it, then `enqueue` and
  `deliver`. Check the result with `status`, and read the post back in `oneworld/logbook-microscope`.
- Posted notes are not edited: send a new note with `corrects: <old id>`.
- **Credentials:** the pilot posts from the operator's computer with the operator's personal token, in the operator's
  name. The local
  configuration points to it, so it isn't copied. Any app used by other lab members needs a bot token instead. Never
  paste tokens into chats or files in Git.

## 6. Archive to the group share

The group's file share holds the archive copy of all microscope data (decision of 30 September 2026). The lab files
lab-wide data there by data stream; the microscope is the stream `instruments/microscope/`, whose rules are in the
share's `0_README` files and in the lab-infrastructure notes (`fileserver.md`).

- **After every session** (and after rebuilding a report), with the share mounted:
  `python3 -m tools.archive_copy run --skip-evicted`. The summary must show no `conflict` and no `failed`.
  - `conflict`: an archived raw frame differs from the local one. Nothing was overwritten; find out which copy is
    damaged before doing anything else.
  - `failed`: a local frame no longer matches the SHA-256 in its metadata, or a read-back check failed. The file was
    not put in place.
  - `evicted`: files still in iCloud (see below) were left out. Run again later until none remain.
- **Monthly:** `python3 -m tools.archive_copy audit` reads every archived file back. Results and each run's log are in
  the stream's `_copylog/` on the share.
- **Restore:** `python3 -m tools.archive_copy restore <path relative to the repository> --to DIR`, with
  `--version <run>` for an earlier version from `_versions/`. The share's own snapshots are not visible over the
  Mac's SMB mount; restores from them go through a Linux mount (PAULA), Windows "Previous Versions" or the computing
  centre.
- The destination is set only in `~/.config/microscope-archive/config.json` (not in Git). The tool refuses to run if
  the folder has no `0_README`, which is also what an unmounted share looks like.
- **The workspace stays in the iCloud-synced `~/Documents` for now** (operator's decision, 30 September 2026). macOS
  may evict local file contents to iCloud when the disk is short. Reading such a file downloads it first, which slows
  analyses; `brctl download <folder>` fetches a folder in advance. The archive copy and the audit skip evicted files
  instead of waiting, so a run may need repeating.

## 7. Records

- **Git** holds code, tests, public methods, the logbook and the status page. **Not in Git:** raw sessions, specimen
  labels, images, reports, notes, the outbox and credentials. All of these except the outbox and credentials are
  archived on the group share (step 6); credentials never go there.
- For each consequential step: add a logbook entry (hardware observation, synthetic test or pending validation), update
  `docs/status.md`, run `make test`, then commit and push.
- Stop the server when finished (Ctrl-C, or ask the assistant). The camera itself is released after 30 s without frame requests.

## Lessons from September 2026

- A live setting changed between probe and capture once gave a gain-70 series instead of gain 50. Always pass `--gain`.
- The count at 255 missed saturation in frames where 76% of pixels were saturated. Use the share ≥240 DN.
- Low red signal (2–8 DN above black) left the red channel unconstrained. Plan exposures for the weakest channel.
- A single reinsertion measures placement and elapsed time only once. Repeat placements and take dark frames.
- Overstated first-draft claims ("uniform", "features <1%") were corrected after review. Keep claims to what the
  statistic shows.
- 29 September: the backlight was 2–4× dimmer than five days earlier and not reproducible. Empty references in the
  same session and a bridge sample (last week's mirror) made the comparison work. The opaque-area black offset
  used on 24 September included light; capped dark frames showed the true sensor black.
- Display-lattice (phone) calibration: focus on green; a colour-cycling page gives single-colour frames without
  touching the phone (40 frames at ~1.2 s span a 48 s cycle); a through-focus series in full fine-focus turns showed
  scale changing with focus by −0.11 to −0.14% per turn at zoom 4 and 7, but +0.03% per turn at zoom 2.
- 30 September: iCloud had evicted about 1000 local files, so analyses and a first archive copy waited on downloads.
  Copy what is local first (`--skip-evicted`) and repeat; keep the verified copy on the group share.
