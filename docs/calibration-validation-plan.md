# Physical calibration validation plan

Status: **planned, not performed**. Use the current 14 profiles only at their
recorded zoom markings and exact resolution, with the same objective/adapter.
They remain provisional at those markings: neither returning to a mark nor
transferring the reference scale to another focus height has been validated.
Intermediate zoom values are rough planning estimates, without an assigned
total accuracy. The previous rounded ±2% statement is not a specimen-accuracy
claim at either measured or intermediate settings.

## Record the setup before acquiring anything

Use an unsaturated, well-focused reference. Record target identity/certificate,
objective/adapter markings, illumination, stage and focus positions, surface
height relative to a reproducible datum, date, operator, and direction of zoom
approach. Keep exposure and gain fixed within a comparison where practicable;
record every change. Preserve exact RAW8, original timestamps, frame IDs,
histograms and checksums. Assign a run/cycle identifier and separate mechanical
returns from consecutive frames taken without touching the controls.

The ring marking is an operator observation; the USB camera does not measure it.
Record whether focus was adjusted after each zoom change. Establish a safe
reference height without contacting or loading the specimen's optical surface.

## 1. Ring return and direction dependence

Start with full resolution. At each of 0.58, 2, 3, 4, 5, 6 and 7:

1. Move clearly away from the mark, then approach it from lower zoom without
   overshoot. Record the excursion and approach direction.
2. Capture two consecutive raw frames without touching any control.
3. Repeat five independent returns from that direction, then five from higher
   zoom. Extend to ten returns per direction if practicable.
4. If a setting is a mechanical endpoint, do not force travel past it. Use only
   the accessible direction and record that direction dependence cannot be
   tested there. Approach direction is not inferred from capture order.
5. Keep focus fixed for the first run if the reference remains measurable.
   Separately repeat the normal refocusing workflow at representative marks;
   record it as a different condition rather than mixing the two populations.

Five returns per direction with two frames gives 20 full-resolution frames per
interior mark, up to 140 across seven marks before endpoint exceptions. These
are ten independent returns, not twenty independent mechanical trials. Add
paired preview frames at a few returns to check the mode ratio economically;
expand to both modes throughout if they disagree. Do not move the ring between
paired preview/full captures.

Fit each capture from the same nominal reference intervals, then calculate
within-return variation, between-return spread, direction-specific means and
their difference, and deviation from the original profile. Plot every return
with direction and sequence. Do not divide between-return spread by sqrt(n)
when describing uncertainty of a future single setting; uncertainty of the
estimated mean is a different quantity. Retain outliers and document causes.

## 2. Reference plane and specimen focus height

Use the mirror's working surface height as the reference-plane target, not the
holder/base height. If the historical height cannot be recovered, mark that
limitation: a new check will not certify the earlier captures retrospectively.

At the marks used for the mirror (0.58, 2, 4, 5, 7), place the length reference
at the reproducible specimen surface plane and refocus using the normal lab
workflow. Compare with the original reference plane, and bracket the expected
surface-height range using recorded offsets. Capture at least three independent
placements/refocus operations per condition, with two consecutive full frames
each. Keep zoom at the same mark during a height comparison. Record which
mechanical component moves to focus; do not assume telecentricity or assign a
universal scale change per millimetre from this dataset.

Estimate scale versus measured height and repeatability of the actual focus
workflow. Separate this from ring-return variation wherever the design permits.
Store a new profile/configuration when the optical geometry differs, rather than
silently overwriting the original one.

## 3. Missing low-zoom nodes and intermediate setting precision

Acquire marks/readings 1 and 1.5, at both resolutions, preserving the same target
plane and recording how each reading is set. Use the ring-return protocol above
(five returns per accessible approach direction, two consecutive frames).
These measurements address the 0.58–2 gap and ring-setting repeatability.

Also test at least one unmarked middle setting such as 3.5 using the same
protocol; low-zoom references alone do not validate reading intermediate values
throughout 2–7. Compare directly measured scales with predictions that excluded
the tested node. Retain the readout/return uncertainty in a future-use allowance.

## 4. Group-dependent bias and field distortion

Use a stage micrometer or other independently certified length reference,
including its tolerance/certificate. At overlapping zooms 2 and 3, compare both
usable USAF groups and the independent reference in the same setup; confirm that
the finer group is sufficiently resolved. This helps distinguish group-dependent
target/edge bias from a change with zoom. A common target error can cancel in the
preview/full ratio and remain invisible to that check.

Translate the same known interval to the centre, four edge regions and four
corners, measuring both orientations with at least three independent placements
per location. Keep the target plane normal to the viewing direction and record
any refocus. Start at one representative zoom, then repeat at the intended
measurement settings. Use translated known intervals, not an uncalibrated stage
movement as a length standard. Fit position-dependent scale and axis differences;
report the validated field region and consider a distortion correction only if
supported by repeatable data.

## Acceptance and record keeping

Choose the required specimen measurement tolerance before judging the results.
Combine reference tolerance, image analysis, ring setting/direction, height/focus
and field-position terms with their correlations stated. Report the uncertainty
of a future specimen measurement, not just fit SE or the mean calibration.
Recalibrate or restrict the usable field/configuration where the requirement is
not met. Do not publish a total percentage while material terms remain unknown.

Keep new raw sessions and calibration revisions alongside the original evidence.
Update the [calibration method](calibration-usaf.md) and [logbook](logbook.md)
with observed results; this checklist is not evidence that any check has passed.
For the existing mirror frames, matching marked-setting profiles can be assigned
provisionally, with ring return and reference-plane transfer explicitly pending.


## Background references

Object-distance sensitivity depends on optical design; conventional and
telecentric imaging behave differently. The current zoom objective has not been
characterized for this property. See [Edmund Optics, advantages of telecentricity](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity).
For distinctions among repeatability, precision and measurement uncertainty,
see [NIST TN 1297, terminology](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-d1-terminology).
The acquisition counts above are a proposed local experiment, not a quoted
manufacturer specification or prescribed standard.
