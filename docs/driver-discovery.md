# Di-Li driver discovery — 2026-09-23

## Location

Found in a user-supplied laboratory software archive, in its Di-Li camera distribution. The private server name and mount path are intentionally omitted from the public repository.

The share was inspected read-only. Four relevant binaries were copied into `/tmp/microscope-di-li/` for static inspection. No installer, driver, or camera application was executed. No files on the share were modified. Vendor binaries are not included in this project.

## Relevant files

Paths below are relative to the Di-Li folder.

| File | Findings |
|---|---|
| `5MP/IS500 Camera Driver Setup.exe` | Windows Inno Setup 5.5.0 installer, 4,105,304 bytes; share modification date 2013-05-15. Embedded strings identify Fuzhou Tucsen Image Technology. Installer payload has not been extracted or tested. |
| `5MP/IS500 Camera Driver Setup.old` | Earlier installer, 4,104,568 bytes. |
| `5MP/IS500 Directshow and Twain Plug-in.exe` | Windows DirectShow/TWAIN installer, 654,144 bytes. |
| `5MP/Treiber-5mp.zip` | Contains the earlier IS500 driver installer and the DirectShow/TWAIN installer; no API headers or Mac driver. |
| `TS500SDK.dll` | 32-bit Intel Windows PE DLL, 278,528 bytes; PE timestamp 2012-05-02. Exports 49 camera functions. |
| `Software/ISCapture/ISCapture.exe` | Windows capture application/installer, not executed. |
| `Software/ISCapture/ISCapture 3.0.0.0.exe` | Windows capture package, not executed. |
| `ISListen V2.0G.app for MacOS/Contents/MacOS/USBListen` | Single-architecture **32-bit Intel i386 Mach-O** executable. Not compatible with current macOS. |
| `IS_Capture_En_2.6.pdf` | Capture-software manual available in the distribution. |
| `Software einrichten.pdf` | Setup instructions available in the distribution. |

The IS500 naming agrees with the connected camera's USB ID mapping in [Tucsen's legacy device list](https://www.tucsen.com/uploads/Software-and-Driver-download-links.pdf). The Windows installer's internal INF hardware IDs have not yet been verified, so a successful match at installation and capture time remains untested.

## SDK evidence

`objdump -p TS500SDK.dll` exposes actual camera API entry points, including:

- Lifecycle: `CameraInit`, `CameraUnInit`, `CameraPlay`, `CameraPause`, `CameraStop`.
- Frames: `CameraGetImageData`, `CameraGetImageDataRGB24`, `CameraGetImageSize`, `CameraCaptureFile`.
- Exposure: `CameraGetExposureTime`, `CameraSetExposureTime`, `CameraGetAeState`, `CameraSetAeState`, AE target and row-time functions.
- Gain: `CameraGetAnalogGain`, `CameraSetAnalogGain`, `CameraGetGain`, `CameraSetGain`.
- White balance: `CameraGetAWBState`, `CameraSetAWBState`, `CameraGetAWBStateResult`.
- Region and modes: ROI, frame speed, subsampling, mirror, monochrome.
- Processing: gamma, contrast, saturation, color enhancement, dead-pixel correction.

Imports include `DeviceIoControl` and Windows SetupAPI, consistent with communication through a Windows device driver. Export names alone do not establish argument types, calling conventions, frame ownership, or callback lifetime rules. A wrapper must use verified headers/documentation or independently verified ABI information.

No camera SDK `.h`, `.hpp`, `.lib`, `.dylib`, or `.so` files were found in the inspected Di-Li software distribution outside its unrelated `misc` folder. The `CMakeLists.txt` in the Mac application's resources is for the bundled JPEG library, not camera-driver source.

## Mac compatibility

The recovered ISListen V2.0G is i386 only. Apple documents that [32-bit applications are unsupported starting with macOS Catalina 10.15](https://support.apple.com/en-za/103076). It therefore cannot run on the current Apple Silicon Mac.

It also links the old `/usr/lib/libstdc++.6.dylib`. Static inspection found a separate integrity issue: its Mach-O `__LINKEDIT` segment ends at byte 617,988, while the stored executable has 617,986 bytes. `nm` reports a malformed/truncated object. The file was not repaired or executed; the architecture incompatibility alone is sufficient to rule out running this copy on current macOS.

The separately downloaded ISListen V2.5 from the earlier investigation is x86_64, but it is not a SDK and has not been validated with this camera. Further static inspection with `nm` found preserved Objective-C method names for `CamBase` and `VA500C`, including `_init_device:`, `_data:length:`, `_submit_out_ctl:`, `_set_resolution:`, `_set_exposure:`, `_set_analog_gain:`, and `_raw2image:img:c:`. These are useful starting points for reconstructing the USB protocol. The `VA500C` name alone does not prove that the routines match USB `0547:c004`.

Raw string inspection of the recovered V2.0G binary also found `IS500.`, `IS500 BW.`, `IOUSBDevice`, and C++ constructor names for `CamBase` and `VA500C1`. A separate `/tmp/microscope-di-li/USBListen.analysis-only` copy was padded with two zero bytes solely to permit further static-tool inspection. It was not executed; the original on the share and the original temporary copy remain unchanged. No initialization sequence, firmware requirement, pixel format, or working image acquisition has yet been established.

## Next integration step

The original software has been located; obtaining it is no longer the blocker. What remains is a working capture runtime and a verified API:

1. For direct capture on this Mac, obtain a compatible IS500/Beta macOS SDK or the USB protocol/source needed to implement a native backend.
2. As an alternative, test the recovered driver and ISCapture on an appropriate Intel/AMD Windows host, then obtain the `TS500SDK.dll` headers/API reference before writing a camera service for the UI. Current Windows driver compatibility is not established by this inspection.

## Checksums of inspected copies

| File | SHA-256 |
|---|---|
| `TS500SDK.dll` | `c71086bfb30b3a5aa30f039aca8b2102f348ddeb742198e6c08094d24652d7eb` |
| `5MP/IS500 Camera Driver Setup.exe` | `08553cc17781c27077bf534267c65dc11fefcc1206be4f5ad17ee3a649cdc864` |
| `5MP/IS500 Directshow and Twain Plug-in.exe` | `efd3944ac4f3ebff1c0e82d9b055d7cd87f6214489fbda63000b9a0e3ced8f64` |
| `ISListen V2.0G.app for MacOS/Contents/MacOS/USBListen` | `2816c417230ba26ddd6812855992c5ac3c4c76afc3c6ae01827cbddda2574ffb` |

## Native SDK follow-up

The x86_64 archive subsequently yielded a working USB initialization and capture sequence for the exact camera. A new C/libusb SDK now reads 1280 × 960 raw frames on this ARM64 Mac. See [native SDK notes](native-sdk.md) for protocol details, hardware checks, and unresolved image validation. Earlier statements above describe the discovery stage.
