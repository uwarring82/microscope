# Physical calibration validation plan

Status: **physical checks planned, not performed**. The saved-frame relative-scale
check is complete; it does not replace these physical checks. Use the current 14 profiles only at their
recorded zoom markings and exact resolution, with the same objective/adapter.
They remain provisional at those markings: neither returning to a mark nor
transferring the reference scale to another focus height has been validated.
Intermediate zoom values are rough planning estimates, without an assigned
total accuracy. The previous rounded ±2% statement is not a specimen-accuracy
claim at either measured or intermediate settings.

## Record the setup before acquiring anything

Use an unsaturated, well-focused reference. Record target identity/certificate,
objective/adapter markings, illumination source identity/type and spectrum or
filter, source setting, azimuth and incidence angle (relative to the surface
normal), source distance, coaxial/off-axis geometry and ambient light, stage and
focus positions, surface
height relative to a reproducible datum, date, operator, and direction of zoom
approach. Keep exposure and gain fixed within a comparison where practicable;
record every change. Preserve exact RAW8, original timestamps, frame IDs,
histograms and checksums. Assign a run/cycle identifier and separate mechanical
returns from consecutive frames taken without touching the controls.

The ring marking is an operator observation; the USB camera does not measure it.
Record whether focus was adjusted after each zoom change. Establish a safe
reference height without contacting or loading the specimen's optical surface.

## 1. Pilot first: ring return at 2, 4 and 7

Start with **five returns from lower zoom at each of 2, 4 and 7**, using full
resolution and two consecutive frames per return: **15 mechanical returns / 30
raw frames**. Approach without overshoot, keep the reference plane and focus
fixed if measurable, and record every control adjustment. This common approach
direction is accessible even if 7 is an upper endpoint; never force travel past
an endpoint. These settings cover the existing overlapping specimen fields.

Set the required tolerance and its allocated ring-return contribution before
testing. Compare the spread across returns with that contribution and with the
within-return image variation. If it is clearly small, reduce subsequent work
to the configurations needed for the intended measurements; if it is substantial,
prioritize direction dependence and focus-height tests. Five returns are a pilot,
not a confidence bound on rare positioning errors. One approach direction does
not test hysteresis. Do not lower the acceptance criterion after seeing the data.

### Expanded run if the pilot or application requires it

At each required marking among 0.58, 2, 3, 4, 5, 6 and 7:

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

First compare several matched particle separations in the existing specimen
raw frames at zooms 2, 4 and 7. Fit their image geometry without a calibration
scale prior; compare with the measured profile ratios afterward. Check alternate
exposures, centroid definitions and spatial residuals, not the fuzzy ends of an
elongated streak. This is a relative consistency check at the specimen's actual
imaging condition, not an absolute calibration or an isolated height test.

A discrepancy around 1% can be a useful investigation trigger **if it exceeds
the image-localization checks**, not a universal tolerance or a diagnosis of ring
return/height error. Correspondence, blur, illumination, distortion and profile
bias can also contribute. Agreement cannot exclude a shared target or
specimen-plane scale offset and does not replace the physical height check.

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

## 5. Registered feature: focus and illumination

The saved mirror overview has a dark face against a bright diffuse background.
This suggests **scatter-dominated, dark-field-like** imaging, consistent with
specular light largely missing the objective; the actual source and geometry
remain unconfirmed. In that interpretation, bright features send more scattered
light into the collection cone, while dark patches send less than nearby regions.
This is not a measurement of total scatter, reflectance or a coating diagnosis.

Use the **zoom-4 streak field**, registered with the streak and several nearby
compact points, keeping ring and stage position fixed. Start with gain register
**13** (as in the target series) and choose **one fixed exposure** with usable
signal and no raw values at 255 in the defined ROI at any tested focus/lighting
condition; retain headroom and the ROI maximum/counts. Zero endpoint counts alone
do not establish absence of saturation below 255. Set the exposure rule before
collection, not by adjusting each frame. If no single usable exposure spans the
conditions, design separate documented runs first; do not compare their feature
counts or raw brightness directly.

Record a central focus and **-5 to +5 focus steps**, returning through the same
recorded approach direction. Record the mechanical increment and which component
moves; call these steps, not micrometres, unless focus travel is calibrated.
For each of **2-3 recorded illumination directions**, acquire the full eleven-frame
series. Add a **coaxial bright-field series of the same registered feature** if
the setup supports it, and confirm that specular return enters the objective.
Keep gain, exposure, camera mode and display processing fixed for the comparison.
Track displacement/scale with nearby points because focusing may change both.

For the secondary arc, one equivalent **zoom-0.58 focus series** is sufficient
for an initial motion test. Track the arc relative to candidate surface points;
independent motion/focus would support an edge/holder reflection or transmission
hypothesis, not identify its exact surface. Surface-side assignments remain open.

Use matching dark/flat references for quantitative intensity comparison, and
characterize stability with illumination geometry. A flat cannot remove sample
specularity or make different illumination directions directly equivalent.

## 6. Repeat inspection and comparison conditions

The current captures are a **first appearance record, not a controlled repeat-
inspection baseline**. Mark/record the optic orientation in its holder without
marking the optical surface. Record stage coordinates or register each field to
the streak plus multiple nearby features, retaining the registration residuals.
Record the objective/adapter, ring marking and approach, resolution, focus rule,
illumination source/angles/settings and specimen height. Lock gain and a defined
exposure rule before starting; retain the actual values and all raw frames.

A repeat comparison needs the same registered field and matched acquisition and
illumination conditions. If a control changes, document it as a separate condition
and establish a new matched reference. Keep processing fixed too; independent
contrast stretches and the current 103-3000-line/gain-60 exposure range change
feature detectability and do not support comparisons of feature counts or density.

## 7. Optical performance: separate measurement and decision

Microscope appearance does not determine fitness for the optical application.
Agree acceptance criteria with the setup's users **before measuring**. Record
operating wavelength/bandwidth, angle of incidence relative to the surface normal,
polarization and beam footprint, and obtain the applicable coating specification.

Measure reflected/incident power with a suitably calibrated power meter at those
conditions; account for source drift, detector response, alignment and collection
aperture in the uncertainty. Compare with the coating specification. If practical,
measure scattered or otherwise lost power against a reference mirror under the
same conditions, documenting collection geometry and detection limits. A missing
specular fraction alone does not distinguish absorption, scatter and transmission.
No such performance measurement or acceptance decision has been made here.

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

For illumination-dependent contrast and nonuniformity, see [Edmund Optics, common illumination types](https://www.edmundoptics.com/knowledge-center/application-notes/illumination/choose-the-correct-illumination). The proposed flat/dark and registered-angle checks must be validated for this reflective specimen; they are not an assumed correction already applied.

The scatter-dominated interpretation is an inference from the saved images, not a
recorded illumination setup. See [Edmund Optics, in-line illumination](https://www.edmundoptics.eu/knowledge-center/application-notes/illumination/in-line-illumination-considerations)
for the contrast change when specular return enters the objective, and
[darkfield ring illumination](https://www.edmundoptics.com/knowledge-center/application-notes/illumination/darkfield-illumination-with-ring-lights-for-machine-vision/)
for collection of scattered light from reflective objects. These sources do not
identify the light or coating used in this dataset.
