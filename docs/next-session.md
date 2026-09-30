# Next microscope session: proposed measurements

Status: **proposal, 30 September 2026**. Nothing here has been measured. The items come from the open points of the
phone display-lattice calibration (draft r2), the M4 mirror comparison (draft r4), the M4 footprint follow-up and
the [validation plan](calibration-validation-plan.md). Follow the [session procedure](session-procedure.md) for
setup, capture, analysis, lab notes and the archive copy; this page only says *what* to measure next and why.
Blocks A–D need the phone and the USAF target, E needs the backlight and the mirrors; they can be separate sessions.

## Before the session

- Start `python3 server.py`; the dashboard must show **USB connected · native SDK**. Choose one gain per series and
  pass `--gain` on every capture.
- Room lights off (or unchanged) for backlit work; plan capped dark frames at every exposure used.
- Check that the colour page can **hold** red, green and blue individually, not only cycle (needed for block C).
- Have a flat gauge of known thickness ready (feeler gauge or gauge block, about 0.3–1 mm) for block D.
- Workspace in iCloud: if analyses of older data are planned, `brctl download sessions artifacts/captures` first.

## A. Zoom 0.58 and zoom 1: USAF and phone in one session (priority 1)

Why: at 0.58 the phone lattice differs from the USAF profile by **+1.46%**, beyond every USAF diagnostic; zoom 1 has a
phone scale (4.4158 µm/px, full resolution) but no USAF profile.
- At 0.58 (mechanical end stop) and at 1 (from lower zoom): alternate USAF → phone → USAF → phone, refocusing on each,
  two full-resolution frames plus one preview each. Note the focus turns needed between the two objects.
- Result: USAF vs phone at the same ring setting and session; a USAF profile for zoom 1 that the operator can decide
  to install. Decide the acceptance criterion before looking at the numbers.

## B. Ring return at 2, 4 and 7 with the phone lattice (priority 1)

Why: ring return is untested ([validation plan §1](calibration-validation-plan.md#1-pilot-first-ring-return-at-2-4-and-7));
the phone lattice repeats to about 0.005% between frames, far better than the USAF bars.
- White page held, focus on green. At each of 2, 4, 7: five returns from lower zoom (leave the mark each time), two
  full frames per return; refocus only if needed and record it.
- Result: the spread of the scale across returns against the within-return frame spread.

## C. Single-colour through-focus (priority 2)

Why: axial colour is only indicative; the white-page series mix colours in every Bayer plane, and the blue-plane
maximum was at the end of the range (−3 turns, not bracketed). This also limits the M4 blue/green interpretation.
- Zoom 4 first, then 2 and 7 if time allows. Hold red, then green, then blue; at each colour, full fine-focus turns
  from −6 to +3 around green best focus, always approached from the same side, exposure chosen per colour (≤200 DN at
  the 99.9th percentile).
- Result: best focus per isolated colour (lattice modulation and spot width), and scale against focus per colour.

## D. Fine-focus travel per turn and the phone's focus plane (priority 2)

Why: focus steps are in turns, so neither the axial-colour offsets nor the scale change per turn (about −0.1% per
turn at zoom 4 and 7, +0.03% at 2) can be stated in micrometres, and the cover-glass offset between the phone pixels
and a USAF target surface is unknown.
- Focus on a mark on the base plate and on the top of the gauge (both in air), counting turns; three times each way,
  at zoom 4 and 7.
- On the phone: focus on a small mark on the cover-glass surface and on the pixels; count turns. With the turn
  calibration this gives the apparent depth of the pixel plane.

## E. M4 mirrors (priority 2, separate backlit session)

Why: the used mirror's diagonal band shows B/G 1.7% below its flanks; blur has not been excluded. Cross-session
ratios carry an unquantified spectral-transfer term. See M4 r4 and the footprint correction in the M4 thread.
- Used mirror, zoom 4, the band field: through-focus in full turns covering green **and** blue best focus (use the
  result of C for the range), matched empty references at the same exposures, capped darks. Test whether the band's
  core-to-flank B/G contrast changes when blue is in focus.
- Room lights off, capped darks, empty reference before and after, at least three placements per mirror.
- Measure two bridge mirrors (the used M4 and one with a different spectrum) if results are to be compared with
  earlier sessions.
- For any mirror taken out of a cavity from now on: mark the cavity-plane orientation and the beam position, and
  image it as removed, **before cleaning**.

## After the session

- `specimen_session verify` and `overview` for every series; then `archive_copy run --skip-evicted` until nothing is
  left over (session procedure, step 6).
- Analysis and draft report with a raw-data atlas and scale bars; an independent review before posting; lab note to
  the M4 thread or `logbook-microscope`; logbook and status updated.
- Due anyway: the monthly `archive_copy audit` (next about 30 October 2026).

## Open decisions (operator)

- Install the zoom-1 scale as a provisional profile (after block A, preferably from USAF).
- Acceptance criteria for ring return (B) and for the 0.58 discrepancy (A), set before the measurement.
- Whether to move the workspace out of the iCloud-synced `~/Documents` (kept there for now, 30 September).
