"""Python binding for the experimental native Di-Li SDK; no Python dependencies.

Usage: with Camera() as camera: camera.start(); frame = camera.read()
The Camera instance is not thread-safe. Serialize calls and close it explicitly.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from functools import lru_cache
from pathlib import Path
import struct
import time
import zlib

WIDTH, HEIGHT = 1280, 960
RESOLUTIONS = {'1280x960': (0, 1280, 960), '2592x1944': (1, 2592, 1944)}
LIBRARY = Path(__file__).resolve().parent / 'artifacts' / 'libdili.dylib'


class CameraError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _library():
    if not LIBRARY.exists():
        raise CameraError('Build the native SDK first: make')
    try:
        lib = C.CDLL(str(LIBRARY))
    except OSError as error:
        raise CameraError(f'Cannot load SDK/libusb: {error}') from error
    signatures = {
        'dili_error': ([C.c_int], C.c_char_p),
        'dili_open': ([C.POINTER(C.c_void_p)], C.c_int),
        'dili_start': ([C.c_void_p, C.c_uint, C.c_uint], C.c_int),
        'dili_start_mode': ([C.c_void_p, C.c_uint, C.c_uint, C.c_uint], C.c_int),
        'dili_get_frame_size': ([C.c_void_p, C.POINTER(C.c_uint), C.POINTER(C.c_uint)], C.c_int),
        'dili_read': ([C.c_void_p, C.POINTER(C.c_uint8), C.c_size_t, C.c_uint], C.c_int),
        'dili_set_exposure_lines': ([C.c_void_p, C.c_uint], C.c_int),
        'dili_set_gain': ([C.c_void_p, C.c_uint], C.c_int),
        'dili_rgb8': ([C.POINTER(C.c_uint8), C.c_size_t, C.c_uint, C.c_uint, C.POINTER(C.c_double), C.POINTER(C.c_uint8), C.c_size_t], C.c_int),
        'dili_white_balance': ([C.POINTER(C.c_uint8), C.c_size_t, C.c_uint, C.c_uint, C.POINTER(C.c_double)], C.c_int),
        'dili_stop': ([C.c_void_p], C.c_int),
        'dili_close': ([C.c_void_p], None),
    }
    for name, (args, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes, function.restype = args, result
    return lib


def available():
    """Whether the driver can load, not a claim that USB is accessible."""
    try:
        _library()
        return True
    except CameraError:
        return False


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'Expected an integer in {minimum}..{maximum}')
    return value


@dataclass(frozen=True)
class Frame:
    pixels: bytes
    captured_at: str
    width: int = WIDTH
    height: int = HEIGHT
    pixel_format: str = 'RAW8_RGGB'

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or len(self.pixels) != self.width * self.height:
            raise ValueError('Frame dimensions do not match the pixel buffer')

    def pgm(self):
        """Raw sensor intensities as a lossless grayscale PGM."""
        return f'P5\n{self.width} {self.height}\n255\n'.encode() + self.pixels

    def rgb(self, gains=(1.0, 1.0, 1.0)):
        """Full-resolution RGB8; raw bytes are never modified. No tone/color profile."""
        gains = color_gains(gains)
        raw = (C.c_uint8 * len(self.pixels)).from_buffer_copy(self.pixels)
        rgb = (C.c_uint8 * (len(self.pixels) * 3))()
        lib = _library()
        code = lib.dili_rgb8(raw, len(raw), self.width, self.height, (C.c_double * 3)(*gains), rgb, len(rgb))
        if code < 0:
            raise CameraError(lib.dili_error(code).decode())
        return bytes(rgb)

    def white_balance(self):
        """Estimate fixed RGB gains from a neutral-reference frame, not any scene."""
        raw = (C.c_uint8 * len(self.pixels)).from_buffer_copy(self.pixels)
        gains = (C.c_double * 3)()
        lib = _library()
        code = lib.dili_white_balance(raw, len(raw), self.width, self.height, gains)
        if code < 0:
            raise CameraError(lib.dili_error(code).decode())
        return tuple(gains)

    def png(self, mode='raw', gains=(1.0, 1.0, 1.0)):
        """Lossless PNG of raw grayscale or processed RGB, at original dimensions."""
        if mode not in ('raw', 'color'):
            raise ValueError('Display mode must be raw or color')
        data = self.pixels if mode == 'raw' else self.rgb(gains)
        return _png(data, self.width, self.height, 1 if mode == 'raw' else 3)


def color_gains(values):
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise ValueError('Supply three white-balance gains: R, G, B')
    for value in values:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0.125 <= value <= 8:
            raise ValueError('White-balance gains must be finite numbers in 0.125..8')
    return tuple(float(v) for v in values)


def _png(data, width, height, channels):
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload))
    stride = width * channels
    rows = b''.join(b'\0' + data[i:i+stride] for i in range(0, len(data), stride))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0 if channels == 1 else 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 1)) + chunk(b'IEND', b''))


class Camera:
    def __init__(self):
        self._lib = _library()
        self._handle = C.c_void_p()
        self._check(self._lib.dili_open(C.byref(self._handle)))
        self.width, self.height = WIDTH, HEIGHT
        self._buffer = (C.c_uint8 * (WIDTH * HEIGHT))()

    def _check(self, code):
        if code < 0:
            raise CameraError(f'{self._lib.dili_error(code).decode()} ({code})')

    def start(self, exposure_lines=500, gain=40, resolution='1280x960'):
        _integer(exposure_lines, 1, 3000); _integer(gain, 1, 70)
        if not isinstance(resolution, str) or resolution not in RESOLUTIONS:
            raise ValueError('Resolution must be 1280x960 or 2592x1944')
        mode, width, height = RESOLUTIONS[resolution]
        # Allocate before changing the device, leaving a valid buffer on failure.
        buffer = (C.c_uint8 * (width * height))()
        self._check(self._lib.dili_start_mode(self._handle, mode, exposure_lines, gain))
        self.width, self.height, self._buffer = width, height, buffer

    def read(self, timeout_ms=5000):
        _integer(timeout_ms, 100, 30000)
        self._check(self._lib.dili_read(self._handle, self._buffer, len(self._buffer), timeout_ms))
        return Frame(bytes(self._buffer), datetime.now(timezone.utc).isoformat(), self.width, self.height)

    def set_exposure_lines(self, value):
        _integer(value, 1, 3000)
        self._check(self._lib.dili_set_exposure_lines(self._handle, value))

    def set_gain(self, value):
        _integer(value, 1, 70)
        self._check(self._lib.dili_set_gain(self._handle, value))

    def stop(self):
        self._check(self._lib.dili_stop(self._handle))

    def close(self):
        if self._handle:
            self._lib.dili_close(self._handle)
            self._handle = C.c_void_p()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main():
    parser = argparse.ArgumentParser(description='Capture real raw sensor frames from the Di-Li camera.')
    parser.add_argument('--output', type=Path, default=Path('artifacts/captures/sdk.png'))
    parser.add_argument('--frames', type=int, default=1)
    parser.add_argument('--exposure-lines', type=int, default=500)
    parser.add_argument('--gain', type=int, default=40)
    parser.add_argument('--resolution', choices=RESOLUTIONS, default='1280x960')
    parser.add_argument('--color', action='store_true', help='Export demosaiced RGB instead of raw grayscale')
    parser.add_argument('--white-balance', type=float, nargs=3, metavar=('R', 'G', 'B'), default=(1, 1, 1))
    args = parser.parse_args()
    if not 1 <= args.frames <= 1000:
        parser.error('--frames must be 1..1000')
    try:
        gains = color_gains(args.white_balance)
        with Camera() as camera:
            camera.start(args.exposure_lines, args.gain, args.resolution)
            begun = time.monotonic()
            for i in range(args.frames):
                frame = camera.read()
                print(json.dumps({'frame': i+1, 'mean': round(sum(frame.pixels)/len(frame.pixels), 3),
                                  'min': min(frame.pixels), 'max': max(frame.pixels),
                                  'elapsed_seconds': round(time.monotonic()-begun, 3)}), flush=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(frame.png('color' if args.color else 'raw', gains))
            args.output.with_suffix('.raw').write_bytes(frame.pixels)
            args.output.with_suffix('.json').write_text(json.dumps({
                'captured_at': frame.captured_at, 'width': frame.width, 'height': frame.height,
                'pixel_format': frame.pixel_format, 'resolution': args.resolution, 'exposure_lines': args.exposure_lines, 'gain': args.gain,
                'display_mode': 'color' if args.color else 'raw', 'white_balance_gains': gains,
                'note': 'RGGB is derived from the legacy driver. Color accuracy is uncalibrated; .raw preserves sensor data.'
            }, indent=2)+'\n')
            camera.stop()
            print(f'Saved {args.output}')
    except (CameraError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
