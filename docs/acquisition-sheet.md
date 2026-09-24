# Specimen acquisition sheet

A one-page checklist for inspection sessions that reuse the provisional USAF
profiles. It records the setup details that were missing from the first mirror
series. Captures, verification and overviews use
[`tools/specimen_session.py`](../tools/specimen_session.py).

## Before the first field

- [ ] Server running (`python3 server.py`); camera shows **USB connected · native SDK**.
- [ ] Objective and camera adapter are the unchanged default (otherwise the profiles do not apply).
- [ ] Specimen label, transcribed verbatim. Choose a series name, e.g. `m4-bbo-20260924`.
- [ ] Optic orientation in its holder: mark the holder or record a visible reference, never the optical surface.
- [ ] Illumination: source and type, setting, direction/angle of incidence, coaxial or off-axis, room lights.
- [ ] Gain: pick one value for the session and keep it (13 as in the target series if the signal allows).
- [ ] Display white balance: unity, or record the gains.

## For each field

Tell the assistant, or pass as options:

| Item | Option | Example |
| --- | --- | --- |
| Zoom ring marking, set **on a mark** | `--zoom` | `4` |
| Short field name | `--field` | `streak` |
| Position / registration | `--note` | `same streak as field 02, stage X 12.3 mm` |
| Illumination, if changed | `--illumination` | `LED ring, 45° from left` |
| Approach to the mark | in `--note` | `from lower zoom` |

1. Set the zoom ring on a marking; record the approach direction. Intermediate settings have no validated scale.
2. Focus, then set exposure in the live view: a usable signal, ideally no raw values ≥240 in the region of interest (this sensor can saturate below 255).
3. Stop live view, then capture:

   ```sh
   python3 -m tools.specimen_session capture SERIES --sample "LABEL" --zoom 4 --field streak \
       --note "..." --illumination "..." --gain 50 --exposures 129,258,515,1031
   ```

   `--gain` fixes the gain even if the live setting changes; `--exposures` takes a full-resolution series at fixed gain
   (the preview uses the live exposure). Without them, one preview and one full frame use the live settings. With `--bracket`, each clipped
   full-resolution frame is followed by one at half the exposure until none reaches 240; every frame is kept. The
   matching marked-setting profile is attached automatically; without one the capture is marked UNCALIBRATED.
4. Check the printed raw max and % ≥240. Repeat for the next field. Fields are numbered in order
   and never overwritten.

## After the session

```sh
python3 -m tools.specimen_session verify SERIES     # checksum, histogram, PNG, FITS, profile match
python3 -m tools.specimen_session overview SERIES   # contact sheet, ledger, display provenance
```

Outputs go to `artifacts/captures/SERIES/` (ignored by Git). The raw data stay in `sessions/`.

## What the scales support

Scales are **provisional**: ring return, transfer from the target plane to the specimen height, and field dependence
are unvalidated. They give spatial context and relative comparisons at the same zoom mark. They do not support
defect dimensions with a stated accuracy. See the [validation plan](calibration-validation-plan.md). Compare feature
visibility only between frames with matched exposure, gain and illumination.
