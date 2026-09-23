# USAF target calibration — measured zoom series

The [completed series](#completed-zoom-series-offline-analysis-2026-09-23) covers
seven zoom markings at both resolutions. Fourteen provisional measured profiles
are available; intermediate settings are estimates with the limitations below.

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

### Interpolating between measured zoom marks

The offline helper [tools/zoom_interpolation.py](../tools/zoom_interpolation.py)
linearly interpolates **pixels/µm** against ring marking, then inverts:

```
t = (z - z_i) / (z_(i+1) - z_i)
s(z) = 1 / ((1-t)/s_i + t/s_(i+1))
```

It refuses extrapolation, unordered/duplicate nodes and nonpositive scales.
It does not create dashboard profiles or relax exact-configuration matching.
For quantitative work prefer measured profiles over intermediate estimates.

Withholding each interior node 3, 4, 5 and 6 from the 2–7 series in turn gives
RMS/max prediction errors of **0.332%/0.431% preview** and **0.321%/0.496% full**.
Each check spans a two-unit bracket; the four checks share endpoints and are
not an independent statistical sample. Direct linear interpolation of µm/pixel
has about 12% maximum error on the same check. Inverse-zoom and log-log models
have similar small errors to the reciprocal-scale model; this agreement is not
an accuracy bound.

For a provisional engineering allowance, define a node envelope as the maximum
of absolute held-out error, repeat change, x/y difference, threshold/green-phase
sensitivity, and twice relative fit SE. Take the larger envelope of the two
bracketing nodes and add the maximum withheld-node error for that resolution.
Addition avoids treating correlated diagnostics as independent random errors.

| Interpolated ring interval | Preview working allowance | Full working allowance |
| --- | ---: | ---: |
| 2–3 | ±1.53% | ±1.34% |
| 3–4 | ±1.53% | ±1.34% |
| 4–5 | ±1.22% | ±1.29% |
| 5–6 | ±0.85% | ±1.09% |
| 6–7 | ±1.05% | ±1.09% |

These are **empirical allowances, not standard uncertainties, 95% intervals,
guaranteed bounds or a complete uncertainty budget**. A rounded ±2% allowance
inside 2–7 excludes target tolerance, field/focus effects and mechanical zoom
reading/return. At 3.5, estimates are 2.4974 ± 0.0383 µm/px preview and
1.2479 ± 0.0168 µm/px full under this convention. A hypothetical ±0.05 ring-unit
reading error would add roughly ±1.4% at 3.5 (relative scale error ≈ |δz|/z);
no such ring-reading precision has been measured.

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
