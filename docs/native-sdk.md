# Experimental native macOS SDK

The repository now contains an ARM64 C library and a dependency-free Python binding for the attached Di-Li / IS500-family camera. It directly uses the installed libusb library; the Windows DLL and obsolete Mac application are not executed or redistributed.

**Verified on 2026-09-23:** USB `0547:c004`, device revision `a000`, Apple Silicon. Ten sequential dark frames and three acquisition restart cycles succeeded. Full 2592 × 1944 mode subsequently passed twelve sequential illuminated captures and repeated switching between preview and full resolution. Exposure/gain changes produced repeatable changes in dark-frame mean intensity. Illuminated captures showed coherent scratches on the user-identified aluminium optical breadboard. RGGB color reconstruction subsequently showed distinct red, green, and blue smartphone display subpixels at full resolution. Absolute orientation, quantitative color accuracy, and optical fidelity are **not yet calibrated**.

## Build and use

Requires macOS, Clang, Python 3.10+, and libusb. On this Mac libusb is already installed under `/opt/homebrew`. To install the dependency on another Homebrew Mac, use `brew install libusb`.

```sh
make
python3 dili.py --resolution 2592x1944 --frames 10 --output artifacts/captures/sample.png
python3 dili.py --resolution 2592x1944 --color --white-balance 1.32 1 1.22 --output artifacts/captures/color.png
python3 server.py
```

On an Intel Homebrew installation, use `make USB_PREFIX=/usr/local`. Intel compilation/runtime is not yet tested. The dylib is built for the host architecture, not as a universal binary. Build tools, bindings, and libusb must use compatible architectures. Run in a terminal permitted to access USB; a sandbox may hide the device. No root account or kernel extension is used.

Open http://127.0.0.1:8765 and click **Start live view**. Choose **2592 × 1944 · full 5 MP** in the resolution selector for full acquisition. **Capture & freeze** (or **Stop and capture**) saves the exact displayed raw frame and settings into a replayable session. Calibration profiles must match the objective, optical configuration and exact resolution; known reference lengths are required to establish each scale, normally from a stage micrometer. The [USAF target calibration](calibration-usaf.md) covers seven measured zoom markings at both resolutions; its provisional scales and interpolation limits are documented separately. Exposure is still in sensor lines, whose duration differs between modes. Acquisition is closed after 30 seconds without frame requests and when the server exits normally. Close other camera software first. The SDK deliberately refuses ambiguous selection when multiple matching cameras are attached. See [session format and capture API](data-format.md) for durable captures, FITS, annotation revisions and provenance.

```python
from pathlib import Path
from dili import Camera

with Camera() as camera:
    camera.start(exposure_lines=500, gain=40, resolution='2592x1944')
    frame = camera.read(timeout_ms=5000)
    Path('sample.raw').write_bytes(frame.pixels)
    Path('sample.png').write_bytes(frame.png())
    Path('sample-color.png').write_bytes(frame.png('color'))
    camera.set_exposure_lines(1000)
    camera.set_gain(30)
    next_frame = camera.read()
    camera.stop()
```

The native C interface is in `sdk/dili.h`; build output is `artifacts/libdili.dylib`. Python uses `ctypes`, so no pip packages are required. Always close the handle; calls on a handle must be serialized. `Camera` is a context manager. Error codes are negative; C callers can use `dili_error(code)`.

## Supported prototype functions

| Function | Behavior |
|---|---|
| Open/close | Exact VID/PID/revision and endpoint validation; exclusive interface claim |
| Start/stop | Recovered sensor resume/suspend sequence |
| Read | 1280 × 960 (1,228,800 bytes) or 2592 × 1944 (5,038,848 bytes), 8-bit raw sensor data |
| Exposure | Integer 1–3000 **sensor lines**, not milliseconds |
| Gain | Integer 1–70 in the legacy driver's register scale, not dB |
| Color | Bilinear RGGB demosaicing at the acquired dimensions; fixed RGB gains |
| White balance | One-shot estimate from a neutral reference; rejects dark/saturated references |
| Export | Raw bytes, metadata JSON, lossless raw grayscale PNG/PGM or processed RGB PNG |
| UI | Exact-frame sessions, raw clipping/focus, calibration profiles, editable markers, FITS/PNG export and gallery |

`frame.png()` remains an unprocessed grayscale view of the sensor mosaic for compatibility; `frame.png('color', gains)` produces RGB. The UI defaults to color. There is no continuous automatic white balance/exposure, ROI control, video recording, or hardware readback of settings. Settings in the UI/metadata are successfully submitted values, not values read back from the sensor. The fixed pixel clock and selected resolution make exposure durations approximately inferable from the old code, but physical timing has not been calibrated; the API therefore exposes line counts.

## Color processing and white balance

`Frame.pixels` remains immutable RAW8 RGGB data. `frame.rgb(gains=(1, 1, 1))` returns interleaved RGB8 bytes; `frame.png('color', gains)` exports them. No raw values are overwritten. Bilinear interpolation uses reflected boundaries that preserve Bayer parity. Gains are finite values in 0.125–8, applied after interpolation with rounding and clipping to 8 bits. There is no black-level subtraction, gamma curve, contrast stretch, or calibrated color correction matrix. PNG compression is lossless, but the RGB reconstruction is processed data.

To estimate gains, capture an unsaturated neutral reference filling the view and call `gains = reference_frame.white_balance()`. Apply those same gains to later specimen frames. The estimator averages RGGB samples across the view, normalizes green to 1, and excludes dark cells and cells with values above 240. It rejects fewer than 64 usable 2 × 2 cells, more than 5% clipped cells, insufficient red/blue signal, or gains outside the supported range. A rejected reference retains the previous gains and does not stop acquisition. This is a practical balance operation, not a color calibration. When using a resolved white display, include many complete display pixels so the estimate averages over their colored subpixels.

The UI's **Set white balance** captures a fresh reference; **Reset** restores `(1, 1, 1)`. Gains remain fixed across subsequent frames, resolution changes, and page reloads, but reset when the server restarts. **Raw sensor · grayscale** ignores gains. The CLI's `--color` enables RGB PNG output and `--white-balance R G B` supplies fixed gains; the saved `.raw` companion remains unchanged. The gains in the command example above are illustrative and must be measured for the illumination being used.

C callers use `dili_rgb8(raw, raw_size, width, height, gains, rgb, rgb_size)` with separate input/output buffers and at least `3*width*height` output bytes. `dili_white_balance(raw, raw_size, width, height, gains)` writes three gains on success; `DILI_WB_REFERENCE` indicates an unsuitable reference without modifying the gains. Both functions are software-only and require no camera handle.

**RGGB evidence:** `VA500C` sets Bayer mode 3 at `0x10000ba91`. In `__decode_rawdata` (`0x10000d506`), this mode assigns the odd-row/odd-column sample to the third output channel and its diagonal neighbors to the first. The output is consumed as RGB through `NSBitmapImageRep` / `NSDeviceRGBColorSpace` at `0x10000525e`–`0x1000052af`, with no intervening red/blue swap. This supports the RGGB phase used here. The resolved smartphone image is visually consistent with RGB subpixels; an independent known-color target is still needed to validate channel identity and color accuracy optically.

## Protocol recovered from ISListen V2.5

Source inspected: the x86_64 `NVision` executable in ISListen V2.5, downloaded from the [IS300/500/1000 software archive](https://sios.net.au/software/is-300-500-1000-iscapture-islisten-software). The retained local Objective-C symbols identify `DevManager`, `CamBase`, and `VA500C` routines. The attach dispatch maps `0547:c004` to `VA500C`. Static inspection was sufficient; the old app was never launched.

All following requests are device-recipient vendor OUT control transfers, `bmRequestType=0x40`, zero data length:

| Purpose | bRequest | wValue | wIndex |
|---|---|---|---|
| Resume | `ba` | `0000` | `0000` |
| Resolution 2592 × 1944 | `b4` | `00c0` | `0000` |
| Resolution 1280 × 960 | `b4` | `00c6` | `0000` |
| Pixel clock selection 0 | `b5` | `00a0` | `0000` |
| Gain | `b7` | encoded gain | `0035` |
| Exposure | `b7` | line count | `0009` |
| Acknowledge/rearm after complete bulk read | `b3` | `0000` | `0000` |
| Suspend | `bb` | `0000` | `0000` |

Initialization: claim interface 0, alternate setting 0; resume; wait 300 ms; resolution; clock; gain; exposure. The camera's actual active USB descriptor confirms configuration 1 and one bulk IN endpoint `0x82`, maximum packet size 512. Each 1280 × 960 read requests **1,229,312 bytes**, with a 512-byte leading region discarded according to the legacy decoder. Full-resolution reads request **5,039,616 bytes**: a 512-byte leading region, exactly 5,038,848 returned pixel bytes, and 256 trailing transport bytes excluded from the image. No firmware upload, persistent setting command, or device reset is used.

For gain below 64, wValue equals the setting. At 64–70 it is `((gain - 63) << 8) + 0x3f`. Exposure is passed directly to register index 9. The first two buffers after startup/settings changes are discarded. Interior USB packets starting with ten `88` bytes signal the observed startup/invalid-frame condition and are rejected; a marker in the first header packet is normal. Short reads or USB errors are never returned as complete images. Faults stop streaming before a subsequent restart. Marker detection is a conservative legacy-derived heuristic; a specimen producing that exact pixel sequence could be rejected.

Key static locations in this executable (virtual addresses):

- `DevManager` attach dispatch: `0x100007b6c` onward.
- `CamBase _sensor_resume`: `0x100008654`; `_sensor_suspend`: `0x100008599`.
- `CamBase _data:length:`: `0x10000928a`; `_raw2image:img:c:`: `0x100009b4a`.
- `VA500C _init_device:`: `0x10000b859`; `_set_resolution:`: `0x10000babd`.
- `VA500C _set_pixsclock:`: `0x10000bde0`; `_set_analog_gain:`: `0x10000c000`; `_set_exposure:`: `0x10000c072`.
- Resolution table: `0x10006f490`, modes 0, 6, 8, 9, 11. Clock table: `0x10006f4e0`, selections 0, 1.

**Full-resolution framing resolved:** the old routine rounded pixel bytes down before adding one block, apparently leaving the final 256 pixel bytes unread. Direct hardware tests show that rounding **up after adding the header** works: `ceil((width*height + 512)/512)*512`. Eight diagnostic reads returned 5,039,616 bytes each. After discarding startup data, the last rows were spatially coherent and the final 256 pixels contained varying scene data. The SDK copies exactly `width*height` pixels and ignores the 256 extra transport bytes; it does not pad, repeat, or upscale image pixels. The full-mode PNG is 2592 × 1944. Live UI switching from full resolution to preview and back was verified on hardware; the subsequent UI PNG was also verified as 2592 × 1944. Existing exposure/gain values are preserved across mode changes; the calibration is cleared. The diagnostic probe is `tools/probe_full_resolution.c`; untouched USB buffers and SDK captures are in `artifacts/captures/full-resolution/`.

C callers use `dili_start_mode(camera, DILI_MODE_FULL, exposure_lines, gain)` and `dili_get_frame_size()` before allocating their output buffer. Legacy `dili_start()` and `DILI_FRAME_BYTES` retain the 1280 × 960 default. The Python `Camera.start(resolution='2592x1944')` handles allocation and frame dimensions. Stop acquisition before changing mode in the C/Python SDK; the UI service performs that transition automatically.

## Verification

`make test` compiles with warnings as errors, runs fake-USB and color native tests, 39 Python tests, and seven viewer geometry/marker tests. The USB test exercises device identity/revision rejection, endpoint validation, both initialization modes, gain encoding, bounds, marker rejection, partial reads, timeout handling, failed initialization, restart, and resource cleanup. A dedicated full-mode case checks every final-fragment pixel, excludes trailing transport bytes, protects output-buffer boundaries, and rejects the legacy undersized transfer. Color tests cover known constant and varying RGB planes, Bayer phase, interpolation, boundaries, clipping, invalid inputs, immutable raw data, and reference rejection. Python tests verify exact grayscale/RGB PNG payloads, processing metadata, invalid settings, and service cleanup; a rejected white-balance reference preserves the working stream. Inspection tests also check immutable frame identity, replay round trips, raw clipping, calibration matching, stale annotation/export rejection and FITS row order. Tests never access hardware. GitHub Actions runs the same suite on macOS; detailed release checks are in the [logbook](logbook.md).

Real hardware checks are recorded in `artifacts/captures/sdk-hardware-check.json` (local, ignored by source control). At exposure/gain pairs `(100,10)`, `(1500,40)`, `(3000,65)`, `(500,40)`, three cycles produced means approximately `10.04`, `10.84`, `13.09`, `10.31` respectively out of 255. These demonstrate a repeatable sensor response, not a calibrated gain or exposure measurement. The first ten-frame CLI run took about 1.55 seconds including warmup and Python statistics; this is not a sustained frame-rate specification.

Browser integration was also exercised through the live UI: over 400 frames, exposure/gain changes, stop/freeze, and restored defaults. API checks rejected out-of-range settings, unauthorized Origin/Host headers, and requests outside the static asset allowlist.

### Illuminated sample check

The user illuminated a scratched aluminium optical breadboard surface. Three initial 1280 × 960 captures showed coherent diagonal scratches and larger dark features without the earlier startup packet artifacts. The visible fine checkerboard is the raw Bayer mosaic, not a demosaiced image. This validates useful spatial image acquisition, but does not establish absolute orientation, optical resolution, or quantitative color accuracy.

At fixed gain 50, a three-point exposure sweep gave:

| Exposure (sensor lines) | Mean raw level / 255 | 99th percentile | Clipped pixels |
|---|---|---|---|
| 514 | 26.597 | 57 | 0% |
| 1028 | 43.102 | 103 | about 0.0001% |
| 2056 | 76.141 | 196 | 0.2065% |

After allowing for the approximate dark offset around 10 counts, doubling exposure approximately doubled the scene signal. This is an exposure-response check, not calibrated timing or a sensor-linearity characterization. The original settings, 2056 lines and gain 50, were restored and live acquisition was left running. Reference PNGs and settings are under `artifacts/captures/lit-sample/`; `exposure-check.json` records the sweep. The raw PNGs are unchanged sensor intensities. The initial frame's alternating pixel means were approximately `[[89.71,78.02],[79.18,37.88]]`, consistent with a Bayer mosaic whose green positions are off the diagonal; red versus blue order requires further verification. Neutral aluminium alone cannot establish which diagonal is red.

### Resolved smartphone color check

The user placed a smartphone showing white under the objective; individual display subpixels were resolved. Lowering exposure to 125 sensor lines at gain 40 avoided clipping in the reference capture (raw 99th percentile 159, no samples above 240). A fixed balance of approximately `(1.3182, 1.0000, 1.2177)` produced clearly separated red, green, and blue subpixel features. Three consecutive API captures were verified as 2592 × 1944, 8-bit RGB PNGs (PNG color type 2), with matching processing metadata. The live UI also displayed `LIVE · RGB` at 5.04 MP. References are in `artifacts/captures/color/phone-reference-raw.png` and `phone-reference-color.png`; `live-color.png` is a subsequent full-resolution RGB capture. Earlier files named `phone-white-*` include exploratory overexposed captures and are not the accepted reference.

Next hardware validation: orientation against a known spatial target, independent gain sweep, color response against a known-color target, long-duration acquisition at both resolutions, and unplug/replug. Physical disconnection has not been tested; the automated fault tests cover the software error path.

### Offline raw dataset

The 2026-09-23 offline dataset contains 18 checksum-verified RAW8 frames: 12 at 2592 × 1944 and six at 1280 × 960, at gain 40 with several exposure line counts. Full metadata and SHA-256 digests are in `artifacts/datasets/phone-screen-20260923/manifest.json`. The camera handle was closed after acquisition. Raw files contain exactly width × height sensor bytes, without USB header/trailer, demosaicing, gains, or PNG compression.

`python3 server.py --replay artifacts/datasets/phone-screen-20260923` verifies the complete dataset before starting. `replay.py` groups frames by recorded resolution/exposure/gain and loops the selected group. The service retains original timestamps and uses the same `Frame` color/PNG and white-balance methods as live acquisition. It never calls USB discovery or opens `Camera`; tests explicitly fail if those paths are reached. Corrupt, truncated, or out-of-directory files are rejected. Exposure/gain requests are refused, while selecting a recording updates the displayed capture settings and clears measurement calibration. Playback timing is for inspection and is not original acquisition timing.
