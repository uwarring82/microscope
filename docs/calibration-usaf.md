# USAF target calibration — zoom setting 0.58

Physical measurements on 2026-09-23 established **provisional, resolution-specific
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
