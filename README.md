# Di-Li microscope workspace

A local web UI and experimental native macOS SDK for the USB-connected Di-Li **5MP-B CMOS Camera**.

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
- Draw measurement lines, calibrate with a known distance in micrometers, and export an image with the measurement.

**Illuminated capture verified:** scratches on an aluminium optical breadboard are clearly visible, and an exposure sweep produced the expected change in brightness. Color reconstruction now resolves the red, green, and blue subpixels of a smartphone showing white. **Prototype limitations:** Absolute orientation, quantitative color accuracy, and exposure timing remain uncalibrated. Color uses bilinear RGGB demosaicing; raw grayscale retains the original sensor values. There is no simulated feed or fallback to another camera.

For white balance, fill the view with an evenly illuminated neutral grey/white reference, avoid clipping, then click **Set white balance**. Gains stay fixed as you move to the specimen; **Reset** restores unity gains. Raw display ignores these gains. A resolved white screen can serve as a practical reference when the view covers many complete display pixels, but it is not a calibrated color standard.

## Offline UI development

The local dataset `artifacts/datasets/phone-screen-20260923/` contains **18 original RAW8 RGGB frames** (67,838,976 sensor bytes): 12 full-resolution frames at 347, 173, and 86 exposure lines, plus six preview frames at 347 and 86 lines, all at gain 40. `manifest.json` records each file's dimensions, capture timestamp, acquisition settings, byte count, and SHA-256 checksum. The captured scene varies in brightness; the default 86-line full-resolution group shows a stable display subpixel pattern. These files are local artifacts ignored by source control; keep the directory for future development.

```sh
python3 server.py --replay artifacts/datasets/phone-screen-20260923
```

Click **Play recording**. The UI labels the source **Offline replay** and loops only the frames in the selected recording. Choose a recording to change resolution/exposure; exposure and gain sliders are disabled because those settings were fixed when the data was captured. Color/raw display, white balance, zoom, histogram, freeze, measurement, and PNG export use the normal processing path. Playback preserves the original sensor bytes and capture timestamps; it does not reproduce original frame timing. The replay server neither discovers nor opens a USB camera, even if one is attached. It still uses the built native library for color processing.

To return to hardware, stop the replay server with Ctrl-C and run `python3 server.py` without `--replay`. There is no automatic fallback between hardware and recordings.

Calibration applies to the current image and optical setup. Opening another image resets calibration. Changing objective, optical zoom, camera resolution, binning, or resizing requires recalibration. Use a stage micrometer; nominal objective magnification alone does not establish an accurate scale.

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

## Development

```sh
make test
python3 camera.py                    # read-only USB discovery JSON
python3 dili.py --resolution 2592x1944 --frames 10  # full 5 MP capture
python3 dili.py --resolution 2592x1944 --color --output artifacts/captures/color.png
python3 -m examples.capture          # minimal Python SDK example
```

`sdk/dili.h` is the native API, `sdk/dili.c` implements the USB driver, `sdk/color.c` provides software color processing, and `dili.py` is the Python binding/CLI. `acquisition.py` serializes camera access for `server.py`; `web/` contains the UI. `camera.py` remains a separate read-only USB discovery module. The server exposes local start/stop/settings/resolution/processing/white-balance and PNG frame endpoints; mutations require a same-origin JSON request with `X-Microscope-Client: local-ui`. The camera closes after 30 seconds without frame requests.
