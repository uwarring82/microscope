# USAF target calibration — measured zoom series

The [completed series](#completed-zoom-series-offline-analysis-2026-09-23) covers
seven zoom markings at both resolutions. Fourteen provisional measured profiles
are available for use only at the corresponding ring markings; they remain
provisional pending ring-return and reference-plane validation. Intermediate
settings are rough estimates with no established total accuracy. See the
[physical validation plan](calibration-validation-plan.md).

## Recorded microscope and camera details

| Component | Recorded information |
| --- | --- |
| Microscope stand / zoom head | Manufacturer and model unrecorded; operator reports no additional known markings. |
| Camera | Di-Li Mikroskope-Kamera label; USB product `5MP-B CMOS Camera`. |
| USB identity | `0547:c004`, revision `a000`, vendor-specific non-UVC interface; observed 480 Mb/s link. Manufacturer string `123456789` is not a serial number. |
| Objective / camera adapter | “Default objective” is an operator label; objective and adapter remained unchanged. Their manufacturer, model and magnification markings are unrecorded. |
| Zoom markings | 0.58, 2, 3, 4, 5, 6, 7; ring readings are not a measurement of total magnification. |
| Capture modes | 1280×960 and 2592×1944 RAW8 RGGB. Sensor model/pitch and the mode sampling mechanism remain unconfirmed. |
| Host and acquisition | macOS on Apple Silicon, native libusb SDK, software v0.2.1 during this collection. |
| Other unrecorded parameters | Numerical aperture, working distance, illumination geometry, stage/focus/surface-height datum and target certificate/serial. |

Identification comes from recorded device observations and operator labels;
the camera branding does not establish the microscope/zoom-head manufacturer.

## Initial reference at zoom 0.58

The initial physical measurements on 2026-09-23 established **provisional, resolution-specific
scales** for the current default objective and camera adapter, with the zoom ring
set to **0.58**, as confirmed by the operator. This is the ring marking, not a
measurement of total optical magnification. The target was operator-identified
as a Thorlabs R1DS1N, a 1-inch negative USAF 1951 target. Objective markings,
adapter magnification, target serial/certificate and illumination geometry were
not recorded. Do not transfer these profiles to another optical configuration.

| Acquisition resolution | Scale (µm/image pixel) | Fit standard error only (µm/pixel) | Independent repeat change |
| --- | ---: | ---: | ---: |
| 1280 × 960 | 14.67167 | 0.02066 | −0.0824% |
| 2592 × 1944 | 7.31291 | 0.00343 | +0.0366% |

The figures above do **not** establish total measurement accuracy. A finer
pattern excluded from the fit differed by up to 2.04% in preview and 0.72% at
full resolution. Use full resolution for measurements and treat these as local
working scales pending reference and field validation.

## Reference and method

The USAF spatial frequency is `2^(group + (element − 1)/6)` line pairs/mm.
The distance from the first to the third corresponding bar center is therefore
`2000 / 2^(group + (element − 1)/6)` µm. Group 2 element 1 supplies a 500 µm
interval. The formula and group/element interpretation are documented in
[Thorlabs' optical imaging lab notes](https://www.thorlabs.com/images/tabimages/MTN015225_B-LN02.pdf);
the [Thorlabs frequency table](https://www.thorlabs.com/catalogpages/V21/1786.pdf)
provides a cross-check.

- Acquired a primary reference and an independent repeat at each resolution,
  with 20 exposure lines, gain register setting 13 and unity display white
  balance. No raw pixels in these four frames equalled 255. The exposure unit
  remains sensor lines; exposure time in seconds is uncalibrated.
- Identified group 2 elements 1–6 visually. Measured first-to-third bar centers
  in both orientations: 12 intervals per primary frame, spanning approximately
  281–500 µm. Group 3 element 1, both orientations, was reserved as a check.
- Averaged only raw RGGB green samples in explicitly recorded strips through
  the interiors of the bars. Baseline and peak were the 10th and 95th
  percentiles of each strip profile. Linearly interpolated half-contrast edge
  crossings defined each bar center. No demosaicing or white balance entered
  the measurements; original raw arrays were preserved.
- Fitted known distance against pixel distance through the origin, separately
  for each acquisition resolution. The existing profile API stores endpoints,
  reference capture IDs, checksums and fit residuals. Repeated captures were
  validation data, not additional independent target dimensions in the fit.

## Checks and limitations

Horizontal and vertical fits differed by 0.019% in preview and 0.072% at full
resolution. Changing edge thresholds from 50% to 40%/60% and processing the two
green phases separately shifted the combined scale by less than 0.17% in
preview and 0.06% at full resolution. The independent repeats changed it by
less than 0.1%. These checks assess this analysis and acquisition repeatability;
they do not measure target accuracy or repeated mechanical zoom positioning.

Group 3 element 1 check errors (measured minus nominal, relative to nominal)
were −2.040% / −1.751% for x/y in preview, and −0.722% / −0.051% at full
resolution. The smaller pattern is more sensitive to sampling, blur and edge
definition. Its disagreement is retained rather than folded into the fit.

Bar-angle spot checks were within approximately 1°; distances were measured
along image axes without a rotation correction. No out-of-plane target tilt,
field distortion, focus dependence or optical resolving-power limit was
measured. The target occupied the upper-middle part of the field; a single
scalar profile is an approximation outside that region. No stage micrometer,
certified target tolerance or total uncertainty budget has been validated.

The rightmost raw column was zero in all four frames, as in earlier recordings.
It was retained unchanged and lies outside all measurement strips. Its cause
remains unresolved. Similar field coverage and approximately twofold sampling
between modes do not establish the sensor's binning/cropping/scaling mechanism.

## Retention and reproduction

The local calibration packet contains the four exact RAW8 captures, original
PNGs, metadata and annotation revisions, raw FITS exports, profile snapshot,
explicit strips/endpoints, one-dimensional intensity profiles, fit/check JSON,
analysis scripts, annotated diagnostic figures and lab notes. A checksum
inventory and a portable ZIP accompany it. Data and local paths are excluded
from public Git; their reuse license remains unspecified. No DOI or external
archival deposit is claimed.

Keep both reference sessions with `sessions/calibrations.json`. Reopening a
saved reference restores its profile and measurement markers. Select the
matching 0.58 profile only with the unchanged objective/adapter and the same
acquisition resolution. Every new zoom setting requires its own reference
captures and profile; the camera cannot detect the physical zoom setting.

Next validation: independently certified length reference, target repositioning
across the field, repeated return to zoom 0.58, and focus/target-plane checks.


## Completed zoom series (offline analysis, 2026-09-23)

The operator subsequently acquired ring markings **2, 4, 7, 6, 3 and 5**, with
primary and repeat frames at both exact resolutions. The first set called 1 was
explicitly corrected by the operator to **2**; no zoom-1 reference exists.
Thirty-two target RAW8 frames are retained: 28 primary/repeat references plus
four initially dim zoom-7 trials. The brighter third/fourth captures at zoom 7
were used. All 32 frames have no values at 255 and a zero rightmost column,
which remains untouched and outside the measurement strips. Absence of values
at 255 is not a sensor-saturation calibration.

Offline analysis and visual review of every primary strip/endpoint overlay are
complete. Fourteen provisional measured profiles are installed locally, with
matching configuration/resolution checks. The 28 primary/repeat references have
profile snapshots and markers in revised annotations and FITS exports; earlier
FITS revisions are retained. The four dim trials remain uncalibrated. No new
acquisition occurred during analysis. Specimen recordings were not modified.

| Ring marking | 1280 × 960 scale (µm/px) | Fit SE only | 2592 × 1944 scale (µm/px) | Fit SE only |
| ---: | ---: | ---: | ---: | ---: |
| 0.58 | 14.671667 | 0.020663 | 7.312908 | 0.003434 |
| 2 | 4.369702 | 0.004278 | 2.183356 | 0.000995 |
| 3 | 2.921903 | 0.002963 | 1.460694 | 0.001051 |
| 4 | 2.180564 | 0.002112 | 1.089292 | 0.000647 |
| 5 | 1.751047 | 0.001813 | 0.873806 | 0.000774 |
| 6 | 1.456621 | 0.000685 | 0.728140 | 0.000661 |
| 7 | 1.244701 | 0.000746 | 0.623343 | 0.000330 |

The scales are object-space sampling, not optical resolving power or total
magnification. Fit SE is one standard error of the origin fit, not total
measurement uncertainty. Each mode was measured independently; neither a
nominal zoom ratio nor an assumed resolution ratio supplied a reference length.
Approximate coordinate transformations only located the measurement strips.

Zoom 2 uses G2 E1–6 with G3 E1 held out, as at 0.58. Zooms 3–7 use G4 E1–6,
spanning 70.15–125 µm first-to-third bar centers, with G5 E1 (62.5 µm) held out.
Each primary contributes 12 fitted intervals, six in each axis, using the raw
green/half-contrast method above. Repeats are validation acquisitions, not
independent target dimensions added to the fit. Exposure varied to improve
contrast: preview/full lines were 20/20 at 0.58 and 2, 40/20 at 3, 20/20 at 4,
80/80 at 5, 120/60 at 6, and 120/120 for accepted zoom-7 references; gain was 13.

Across the complete series, maximum absolute checks are:

| Diagnostic | Preview | Full resolution |
| --- | ---: | ---: |
| Repeat scale change | 0.102% | 0.196% |
| x/y scale disagreement | 0.421% | 0.340% |
| Threshold or green-phase sensitivity | 0.253% | 0.179% |
| Finer held-out interval error | 2.040% | 0.849% |

Bar-angle spot checks reached 1.63°; axis projection alone would be about 0.04%
at that angle. No rotation correction or out-of-plane tilt correction was made.
These checks are local to the sampled region and target dimensions. They do not
measure field distortion, mechanical return to a zoom mark, target accuracy or
focus/target-height effects. An image footprint computed as array size × local
scale extrapolates that scale outside the sampled region.

### Cross-mode consistency and reference coverage

For ring markings 0.58, 2, 3, 4, 5, 6 and 7, preview/full scale ratios are
**2.0063, 2.0014, 2.0004, 2.0018, 2.0039, 2.0005 and 1.9968**. Their relative
departures from 2 are at most 0.313% overall and 0.196% inside 2–7. This is a
useful relative consistency check: the same ring setting enters both captures.
It does not establish 0.1–0.2% absolute accuracy, because shared target, optical
and analysis biases can cancel. It also does not establish the sensor's sampling
mechanism or guarantee that an ideal scale ratio is exactly 2.

The two modes follow a similar departure from inverse zoom over 2–7 (Pearson
correlation 0.855 for six nodes). After separately normalizing zoom × scale by
its median over 2–7, their curves differ by at most 0.205 percentage points.
This is consistent with a shared zoom-dependent component, but a single visit
per mark cannot separate ring placement from optical nonlinearity or shared
biases. It is not a measurement of mechanical error.

G2 supplies 281–500 µm intervals at 0.58/2; G4 supplies 70–125 µm at 3–7.
Group-dependent target fabrication or edge-measurement bias could therefore
contribute across the 2–3 boundary; target tolerances have not been checked.
At zoom 7 full resolution each fitted interval is 112–201 pixels long. The
strips are distributed across x=656–1949 and y=288–1845 in the 2592×1944 array
(upper ROI bounds exclusive), rather than confined to one tiny central patch.
This samples several positions but is **not a full-field distortion map**:
different target elements and positions are confounded and the horizontal
edges/corners lack translated-reference validation.

Specimen height and refocusing can change scale; this optical setup's dependence
has not been characterized. The mirror's surface plane differs from the target's
according to the operator, so reference-plane transfer remains unvalidated for
**every mirror measurement**, even with an exact marked-setting profile. The
new [validation plan](calibration-validation-plan.md) addresses that transfer,
ring return/direction, low-zoom nodes and a translated certified reference.

### Interpolating between measured zoom marks

The offline helper [tools/zoom_interpolation.py](../tools/zoom_interpolation.py)
linearly interpolates **pixels/µm** against ring marking, then inverts:

```
t = (z - z_i) / (z_(i+1) - z_i)
s(z) = 1 / ((1-t)/s_i + t/s_(i+1))
```

It refuses extrapolation, unordered/duplicate nodes and nonpositive scales.
It does not create dashboard profiles or relax exact-configuration matching.
Use the 14 profiles only at their recorded markings and exact resolution.
Interpolation is a rough planning estimate until intermediate ring setting and
return precision are measured; do not assign it a total accuracy.

Withholding each interior node 3, 4, 5 and 6 from the 2–7 series in turn gives
RMS/max prediction errors of **0.332%/0.431% preview** and **0.321%/0.496% full**.
Each check spans a two-unit bracket; the four checks share endpoints and are
not an independent statistical sample. Direct linear interpolation of µm/pixel
has about 12% maximum error on the same check. Inverse-zoom and log-log models
have similar small errors to the reciprocal-scale model; this agreement is not
an accuracy bound.

For an image-analysis/model diagnostic envelope only, define a node envelope as the maximum
of absolute held-out error, repeat change, x/y difference, threshold/green-phase
sensitivity, and twice relative fit SE. Take the larger envelope of the two
bracketing nodes and add the maximum withheld-node error for that resolution.
Addition avoids treating correlated diagnostics as independent random errors.

| Interpolated ring interval | Preview diagnostic envelope | Full diagnostic envelope |
| --- | ---: | ---: |
| 2–3 | ±1.53% | ±1.34% |
| 3–4 | ±1.53% | ±1.34% |
| 4–5 | ±1.22% | ±1.29% |
| 5–6 | ±0.85% | ±1.09% |
| 6–7 | ±1.05% | ±1.09% |

These are **partial diagnostic envelopes, not a future-setting accuracy,
standard uncertainty, 95% interval or guaranteed bound**. The earlier rounded
±2% recommendation is withdrawn as an operational accuracy statement: it does
not include ring reading/return, target tolerance, specimen height/focus or field
position. No total ±2% bound is established even at the marked settings.
At 3.5 the model gives 2.4974 µm/px preview and 1.2479 µm/px full; the tabulated
diagnostic components alone correspond to 0.0383 and 0.0168 µm/px. A hypothetical
±0.05 ring-unit error contributes roughly ±1.4% at 3.5 and ±2.5% at 2
(relative scale error ≈ |δz|/z), before the other terms. Such reading precision
has not been measured, and marked-setting return uncertainty is also unknown.

**The 0.58–2 gap has no interior validation.** At ring 1 and 1.5, estimated full
scales are 4.3147 and 2.8995 µm/px. Alternative inverse-zoom/log-log estimates
depart by up to 0.84% and 0.61%, but that spread does not bound the unknown error.
The product zoom × scale at 0.58 is about 3% below the 2–7 trend; it is retained
as observed. Acquire intermediate references before quantitative interpolation
in this gap. Do not extrapolate below 0.58 or above 7.

### Completed evidence and remaining physical validation

The local packet now contains all 32 raw references and their PNG/FITS/metadata,
14 profile snapshots, annotation history, strips/endpoints and raw intensity
profiles, repeat/sensitivity checks, a three-page illustrated report, an editable
narrative, numerical results, scientific figures and analysis scripts. Raw hashes,
lengths, histograms, PNG reconstruction and current FITS raw/metadata payloads
are checked again when packaging. This is an identity check, not a new independent
FITS standards validation. The packet has a SHA-256 inventory and ZIP sidecar;
it is a local retention copy, not an external backup or DOI archive. Reference
images/data and private paths remain outside public Git, with reuse license
unspecified. The public numerical helper and synthetic tests require no camera
or private dataset.

Remaining physical checks: an independently certified length reference, zooms
inside 0.58–2, repeated approach to marks from both directions, target translation
across the field and focus/target-plane changes. The independent immediate frame
repeats above do not replace these mechanical or metrological checks.


## Relative scale check on overlapping specimen fields

An offline check uses seven visually reviewed compact particle landmarks common
to full-resolution images at marked zooms 2, 4 and 7. The operator recorded a
position change at zoom 2; image correspondence now supports **partial overlap**
with 4 and 7, without reconstructing stage coordinates or claiming that every
field is registered. The diffuse endpoints of the elongated feature were not
used as length references.

Raw RGGB cell-green means are background-subtracted using a local annular plane.
A connected half-peak support mask is located from lightly smoothed signal;
centroid weights are positive, unsmoothed green intensities. The selected raw
ROIs have maxima of 212 / 104 / 90 DN at zooms 2 / 4 / 7. Profiles and nominal zoom
ratios are not inputs to the free similarity fit (translation, rotation, scale).
Profile-predicted ratios are compared only after fitting pixel coordinates.
The [relative-scale helper](../tools/relative_scale.py) and synthetic tests are
camera independent; source hashes, raw coordinates, ROI bounds, candidate
correspondences and complete analysis scripts remain in the local data packet.

| Comparison | Fitted target/source pixel ratio | Profile-predicted ratio | Relative calibrated-length disagreement |
| --- | ---: | ---: | ---: |
| 2 → 4 | 2.003003 | 2.004381 | −0.069% |
| 4 → 7 | 1.751430 | 1.747499 | +0.225% |
| 2 → 7 | 3.508118 | 3.502653 | +0.156% |

Nineteen pairs with baselines of at least 150 raw pixels at zoom 2 differ by
at most 0.423% after application of the profiles. These pairs share endpoints
and are not independent observations. Threshold (30/70%), green-phase, crop-radius
and alternate-exposure checks shift fitted ratios by less than 0.098%; leaving
one landmark out changes them by less than 0.056%. This measures the sensitivity
of this analysis, not the uncertainty of a future microscope setting.

The recorded specimen fields support relative scale consistency below a 1%
investigation threshold. They cannot reveal a common absolute error, establish
correct reference-to-specimen height transfer, or measure mechanical ring return.
A discrepancy would not uniquely identify ring or height error; localization,
correspondence, distortion, illumination and profile bias are alternatives.
The [validation plan](calibration-validation-plan.md) now begins with a 30-frame
pilot (2/4/7, five returns from one direction, two frames per return). Larger
runs depend on the tolerance and pilot result; height and field checks remain
pending. No new camera acquisition was performed for this comparison.

## Independent display-lattice scale: iPhone 17 Pro (analysis 2026-09-26)

The operator identified the smartphone in the dataset `phone-screen-20260923` as an **iPhone 17 Pro**. That dataset holds
18 raw frames taken on 2026-09-23 at 10:22 UTC, about 8 h before the USAF series. Apple specifies its display as
2622 × 1206 pixels at **460 ppi** ([Apple tech specs](https://support.apple.com/en-us/125090)). That gives a pixel pitch of
p = 25.4 mm / 460 = **55.22 µm**, with about ±0.11% from rounding the ppi; the stated 6.27 in diagonal gives 460.3 ppi.
The resolved OLED layout has one green subpixel per logical pixel on a square lattice of pitch p. Red and blue lie on a
square lattice of pitch p√2, with twice as many greens as reds. The layout is therefore a physical length standard
independent of the USAF target.

**Method.** Intensity-weighted centroids of every green subpixel (raw Bayer planes, ~2200 per full frame), then a
least-squares Bravais-lattice fit. The scale is p divided by the square root of the lattice cell area, cross-checked with
the red lattice (factor √2). Local fits in 4 × 3 blocks, and a joint radial term, test field dependence. Frames 006–011
(full resolution) and 012–017 (preview) cover the whole field; frames 000–005 cover it only partly and are not used.

| Quantity | Result |
| --- | --- |
| Scale, 2592 × 1944 (whole field / image centre) | **1.1806 / 1.1812 µm/px**, total uncertainty ±0.15% (specification-dominated) |
| Scale, 1280 × 960 | **2.3612 µm/px** |
| Preview ÷ full ratio | **1.99992** (six frames each; spread 0.005%) |
| Pixel aspect (lattice axis-length ratio; angle) | equal within 0.02%; 90° within 0.03° |
| Red vs green lattice scale | agree within 0.02% |
| Field dependence at this setting | local scale within 0.12% over the full field; radial term +0.10% at the corner (slight pincushion) in both modes |

**Comparison with the USAF profiles.**
- **The zoom ring was not recorded for the phone frames, so the absolute scales cannot be compared.** 1.1806 µm/px lies
  between the full-resolution profiles for marks 3 (1.4607) and 4 (1.0893), 7.7% from mark 4. The ring was therefore not
  on a mark, or the optical configuration differed. Reciprocal interpolation places it near ring reading 3.7, which is a
  rough estimate, not a result.
- **Comparisons that do not depend on zoom agree with the USAF analysis and tighten it:**
  - The mode ratio is 2.000 to 0.01%. The USAF per-mark ratios of 1.997–2.006 therefore show USAF measurement scatter,
    not an optical effect.
  - Pixel squareness is better than 0.02%. The USAF x/y differences of 0.3–0.4% are therefore analysis-side as well.
  - The first field measurement, valid at this ring setting only, shows scale variations ≤0.13% across the full field.

**To validate the profiles directly:** image the phone at recorded marks (1, 2, 3, 4, 5, 6, 7; at 0.58 the green pitch is
only ~7.6 px), in the same session as a USAF reference, alternating the two. Zoom 1 would also fill the 0.58–2 gap. The
display pixels lie under the cover glass at a different height from the target surface. Refocusing therefore brings in
the unvalidated height/focus term, so a phone-vs-USAF difference at one mark measures that term together with ring
return.
