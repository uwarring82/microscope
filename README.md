# Di-Li microscope workspace

A local web UI and experimental native macOS SDK for the USB-connected Di-Li **5MP-B CMOS Camera**.

[Current status](docs/status.md) · [Session procedure](docs/session-procedure.md) · [Development logbook](docs/logbook.md) · [Session/data format](docs/data-format.md) · [FAIR practice](docs/fair.md) · [Citation](CITATION.cff) · [MIT license](LICENSE)

```sh
make                       # build the native SDK; uses installed libusb
python3 server.py
```

Open **http://127.0.0.1:8765**, then click **Start live view**. Stop the server with Ctrl-C. Use `--port 8766` if the default port is occupied. The server binds only to loopback; images stay on this device. Python 3.10+ is required; no pip or npm dependencies are needed. The SDK requires Clang and libusb (`/opt/homebrew` on this Mac).

## Current capabilities

- Native Apple Silicon USB capture at **1280 × 960 or full 2592 × 1944 (5 MP)**, with start/stop, exposure in sensor lines, and sensor gain controls.
- Full-resolution RGB color preview with fixed white balance from a neutral reference, plus a raw grayscale display option; stop and freeze for measurements or PNG export.
- Python and C APIs for capture and settings. [SDK usage and protocol notes](docs/native-sdk.md).
- Open local PNG, JPEG, WebP, or BMP images; zoom, pan, fit, RGB readout, crosshair, and histogram.
- Capture the exact displayed raw frame into a durable, replayable session, with settings, SHA-256, timestamps and provenance.
- A calibration workflow with persistent profiles per objective/configuration/resolution, a multi-interval fit and its standard error. Provisional USAF profiles exist locally for seven zoom marks; total uncertainty and physical validation are pending ([status](docs/status.md)).
- Editable distance lines, rectangles/areas, circles/diameters and points; labels, undo/redo and saved annotations.
- Raw FITS plus image-only, annotated and inspection-sheet PNG exports with saved settings, raw histogram, measurements and notes.
- Raw clipping and a relative central-green focus indicator, computed before white balance.

## Quick inspection workflow

1. Start the preview (or offline recording), enter a session name and sample ID, and confirm the objective/configuration. Select a matching calibration profile, or keep the visible **UNCALIBRATED** state.
2. Click **Capture & freeze**. The server saves the exact displayed raw frame, its original processing settings and its metadata into `sessions/session-…/`. It never substitutes a new frame when saving.
3. Select a marker tool; draw in the image, label markers, and add notes. **Select / move / edit endpoints** edits existing shapes. Save notes and markers; the session can be reopened from **Saved sessions and captures**.
4. **Save raw FITS** or select a PNG layout and **Save PNG**. Export automatically saves pending edits. Files and metadata remain in the session folder; the UI provides a link to the saved export.

To create a calibration, capture a stage micrometer, draw/select a line and enter its known length. Add at least three intervals in **Create a profile from a stage micrometer**, then fit and save the named profile. The displayed uncertainty is fit precision only, not a complete metrology uncertainty. Calibration profiles are local data; none ships with the source. See [USAF calibration](docs/calibration-usaf.md) for the method used on this microscope.

**Illuminated capture verified:** scratches on an aluminium optical breadboard are clearly visible, and an exposure sweep produced the expected change in brightness. Color reconstruction now resolves the red, green, and blue subpixels of a smartphone showing white. **Prototype limitations:** Absolute orientation, quantitative color accuracy, and exposure timing remain uncalibrated. Color uses bilinear RGGB demosaicing; raw grayscale retains the original sensor values. There is no simulated feed or fallback to another camera.

For white balance, fill the view with an evenly illuminated neutral grey/white reference, avoid clipping, then click **Set white balance**. Gains stay fixed as you move to the specimen; **Reset** restores unity gains. Raw display ignores these gains. A resolved white screen can serve as a practical reference when the view covers many complete display pixels, but it is not a calibrated color standard.

## Offline UI development

The local dataset `artifacts/datasets/phone-screen-20260923/` contains **18 original RAW8 RGGB frames** (67,838,976 sensor bytes): 12 full-resolution frames at 347, 173, and 86 exposure lines, plus six preview frames at 347 and 86 lines, all at gain 40. `manifest.json` records each file's dimensions, capture timestamp, acquisition settings, byte count, and SHA-256 checksum. The captured scene varies in brightness; the default 86-line full-resolution group shows a stable display subpixel pattern. These files are local artifacts ignored by source control; keep the directory for future development.

```sh
python3 server.py --replay artifacts/datasets/phone-screen-20260923
```

Click **Play recording**. The UI labels the source **Offline replay** and loops only the frames in the selected recording. Choose a recording to change resolution/exposure; exposure and gain sliders are disabled because those settings were fixed when the data was captured. Color/raw display, white balance, zoom, histogram, freeze, measurement, and PNG export use the normal processing path. Playback preserves the original sensor bytes and capture timestamps; it does not reproduce original frame timing. The replay server neither discovers nor opens a USB camera, even if one is attached. It still uses the built native library for color processing.

Each replay frame uses its own recorded white balance, with manifest gains as a legacy fallback. **Set white balance** and **Reset** select a manual override; **Use recorded balance** restores per-frame gains. Use preview resolution for focusing; full-resolution preview is around 2 fps on the tested Mac. Sessions may mix resolutions or camera/replay captures; the UI shows a notice and keeps every frame's provenance.

To return to hardware, stop the replay server with Ctrl-C and run `python3 server.py` without `--replay`. There is no automatic fallback between hardware and recordings.

Calibration profiles are matched to the exact image resolution and manually selected objective/configuration. Opening a saved inspection restores its calibration snapshot; changing resolution never rescales a profile by a presumed binning ratio. Use a stage micrometer; nominal objective magnification alone does not establish an accurate scale.

## Hardware investigation, 2026-09-23

Observed locally:

| Field | Value |
|---|---|
| Camera label, supplied by user | Di-Li Mikroskope-Kamera, www.di-li.eu |
| USB product string | `5MP-B CMOS Camera` |
| USB manufacturer string | `123456789` (this is not a serial number) |
| USB vendor/product IDs | `0547:c004` |
| USB interface class | `255 / 0xff`, vendor-specific, not UVC |
| USB link speed | 480 Mb/s |
| Host | macOS, Apple Silicon (`arm64`) |

[Tucsen's legacy device list](https://www.tucsen.com/uploads/Software-and-Driver-download-links.pdf) maps this USB ID to the **IS500 / Beta** family and lists ISCapture 3.6.8 for Windows. This is an identification by USB ID, not a confirmed Di-Li model number. A generic browser webcam/OpenCV interface cannot by itself implement this vendor-specific protocol.

[Di-Li's camera page](https://www.di-li.eu/kameras.html) points to `http://www.loetdampf.de/USB_Treiber.zip`; the link redirected to HTTPS and returned HTTP 404 when checked.

An [archived IS300/500/1000 software page](https://sios.net.au/software/is-300-500-1000-iscapture-islisten-software) supplies an old Mac archive. Inspection of its **ISListen V2.5 (Mac X86_64)** package found a 2012 Intel x86_64 application, no separate camera SDK/library, and a dependency on `/usr/lib/libstdc++.6.dylib`. It was inspected in `/tmp`, not installed or executed. This does **not** establish compatibility with the attached camera or current macOS. The newer ISH/H series has different USB IDs; its driver must not be assumed compatible.

The original Di-Li software copy was subsequently found in a user-supplied laboratory software archive. It includes IS500 Windows driver installers, a 32-bit Windows `TS500SDK.dll`, and a 32-bit Intel ISListen V2.0G Mac application. The DLL exports image acquisition and exposure/gain functions, but no camera API headers were found in the inspected distribution. See [driver discovery notes](docs/driver-discovery.md) for the relative file inventory and compatibility findings.

The initial SDK investigation recovered the relevant `VA500C` USB protocol from the old x86_64 Mac executable. The new C/libusb implementation now captures real data on this ARM64 Mac; no vendor binary is executed. Ten sequential dark frames, setting changes, three stop/start cycles, an illuminated-sample exposure check, and full-resolution acquisition/mode-switch checks passed. See [native SDK notes](docs/native-sdk.md) for evidence and remaining validation.

## Lab notes to Mattermost

`tools/labnotes.py` posts dedicated lab notes, not every capture, to the group's lab-book channel
(`logbook-microscope` in the `oneworld` team). It follows the lab's lab-book conventions for machine
channels: labels `[NOTE]`, `[SETTING]`, `[SERVICE]` and `[RUN]`, a stable event ID and the UTC event time
in every post, and a "late post" marker when a note is delivered long after the event. A note is a
Markdown file with a short header; see the module docstring.

```sh
python3 -m tools.labnotes preview FIG.png --out DIR   # low-resolution JPEG preview (≤1280 px) to attach
python3 -m tools.labnotes check NOTE.md      # print the exact message; sends nothing
python3 -m tools.labnotes enqueue NOTE.md    # durable local outbox (artifacts/labnotes/), idempotent per event ID
python3 -m tools.labnotes deliver            # send due events, with retry and backoff
python3 -m tools.labnotes status
```

Posts are Markdown. Image attachments must be low-resolution previews (≤1600 px, ≤1 MB), which Mattermost shows inline; full-resolution figures and raw data stay local. Delivery is a separate step, so acquisition never waits for the network. A changed note under an existing ID
is refused: post a correction with `corrects:` instead. Mentions such as `@channel` are neutralised. A
timeout may have posted anyway, so a retry is marked in the text. With the API transport, the channel is
checked for the event ID before re-posting. Credentials stay outside Git in
`~/.config/microscope-labnotes/config.json` (mode 600). Use either a channel-locked incoming webhook (text only)
or a token (text and attachments). A `token_file` option reads the token from an existing private `.env`, so it is not copied. The current pilot posts from the operator's own computer with his personal access token, in his name (his decision, 2026-09-26). An app used by other lab members needs a bot token instead. Notes and the
outbox are local lab data.

## Development

```sh
make test
python3 camera.py                    # read-only USB discovery JSON
python3 dili.py --resolution 2592x1944 --frames 10  # full 5 MP capture
python3 dili.py --resolution 2592x1944 --color --output artifacts/captures/color.png
python3 -m examples.capture          # minimal Python SDK example
```

`sdk/dili.h` is the native API, `sdk/dili.c` implements the USB driver, `sdk/color.c` provides software color processing, and `dili.py` is the Python binding/CLI. `acquisition.py` serializes camera access for `server.py`; `web/` contains the UI. `camera.py` remains a separate read-only USB discovery module. The server exposes local start/stop/settings/resolution/processing/white-balance and PNG frame endpoints; mutations require a same-origin JSON request with `X-Microscope-Client: local-ui`. `POST /api/camera/settings` accepts `exposure_lines`, `gain` or both; an omitted value keeps its current setting. The camera closes after 30 seconds without frame requests.

`frames.py` retains preview frame identities; `captures.py`, `calibration.py` and `fits_export.py` implement durable inspection records. Browser viewing, markers, calibration and export are separate modules. Runtime Python has no pip dependencies; `make test` uses generated fixtures and never opens hardware. See [contribution guidance](CONTRIBUTING.md) and update the [logbook](docs/logbook.md) with consequential changes and validation.

The code and documentation use MIT. Captured data is local and separately licensed by its owner. The public repository includes a versioned JSON Schema, CITATION.cff and CodeMeta; no specimen datasets or vendor executables are distributed. A DOI/archive deposit has not yet been established.
