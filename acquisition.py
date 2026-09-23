"""Serialized local UI access to the native SDK, with an idle-device lease."""
import threading
import time
from dili import Camera, CameraError, available, RESOLUTIONS, color_gains


class Acquisition:
    source_type = 'camera'

    def __init__(self):
        self.lock = threading.RLock()
        self.camera = None
        self.error = None
        self.settings = {'exposure_lines': 500, 'gain': 40}
        self.resolution = '1280x960'
        self.display_mode = 'color'
        self.white_balance_gains = (1.0, 1.0, 1.0)
        self.last_access = 0
        self.frames = 0
        self.shutdown = threading.Event()
        self.monitor = threading.Thread(target=self._idle_watch, daemon=True)
        self.monitor.start()

    def _idle_watch(self):
        while not self.shutdown.wait(2):
            with self.lock:
                if self.camera and time.monotonic() - self.last_access > 30:
                    self._close()

    def _close(self):
        if self.camera:
            self.camera.close()
            self.camera = None

    def state(self):
        with self.lock:
            return {'source_type': self.source_type, 'driver_available': available(), 'running': self.camera is not None,
                    'settings': dict(self.settings), 'error': self.error, 'frames': self.frames,
                    'resolution': self.resolution,
                    'width': RESOLUTIONS[self.resolution][1], 'height': RESOLUTIONS[self.resolution][2],
                    'display_mode': self.display_mode, 'white_balance_gains': self.white_balance_gains,
                    'bayer_pattern': 'RGGB', 'preview': 'RGB color (uncalibrated)' if self.display_mode == 'color' else 'Raw sensor intensities, grayscale'}

    def start(self):
        with self.lock:
            self.last_access = time.monotonic()
            if not self.camera:
                try:
                    self.camera = Camera()
                    self.camera.start(**self.settings, resolution=self.resolution)
                    self.error = None
                    self.frames = 0
                except Exception as error:
                    self._close(); self.error = str(error)
                    raise
            return self.state()

    def stop(self):
        with self.lock:
            self._close()
            return self.state()

    def configure(self, settings):
        if set(settings) != {'exposure_lines', 'gain'}:
            raise ValueError('Supply exposure_lines and gain')
        for key, maximum in [('exposure_lines', 3000), ('gain', 70)]:
            if type(settings[key]) is not int or not 1 <= settings[key] <= maximum:
                raise ValueError(f'{key} must be an integer in 1..{maximum}')
        with self.lock:
            if self.camera:
                try:
                    self.camera.set_exposure_lines(settings['exposure_lines'])
                    self.camera.set_gain(settings['gain'])
                except Exception as error:
                    self._close(); self.error = str(error)
                    raise
            self.settings = dict(settings)
            self.last_access = time.monotonic()
            return self.state()

    def set_resolution(self, resolution):
        if not isinstance(resolution, str) or resolution not in RESOLUTIONS:
            raise ValueError('Resolution must be 1280x960 or 2592x1944')
        with self.lock:
            if resolution != self.resolution and self.camera:
                try:
                    self.camera.stop()
                    self.camera.start(**self.settings, resolution=resolution)
                except Exception as error:
                    self._close(); self.error = str(error)
                    raise
            self.resolution = resolution
            self.last_access = time.monotonic()
            return self.state()

    def set_processing(self, data):
        if not isinstance(data, dict) or set(data) != {'display_mode', 'white_balance_gains'}:
            raise ValueError('Supply display_mode and white_balance_gains')
        if data['display_mode'] not in ('color', 'raw'):
            raise ValueError('Display mode must be color or raw')
        gains = color_gains(data['white_balance_gains'])
        with self.lock:
            self.display_mode = data['display_mode']
            self.white_balance_gains = gains
            return self.state()

    def _read(self):
        # Caller holds the lock: camera handles must never be used concurrently.
        if not self.camera:
            raise CameraError('Acquisition is stopped. Start live view to capture.')
        try:
            frame = self.camera.read()
            self.frames += 1
            self.last_access = time.monotonic()
            return frame
        except Exception as error:
            self._close(); self.error = str(error)
            raise

    def balance_neutral(self):
        with self.lock:
            frame = self._read()
            # A rejected optical reference must not stop a working USB stream.
            gains = frame.white_balance()
            self.white_balance_gains = gains
            return self.state()

    def read_png(self, with_metadata=False):
        with self.lock:
            frame = self._read()
            mode, gains = self.display_mode, self.white_balance_gains
            metadata = self._frame_metadata(frame)
        payload = frame.png(mode, gains)
        metadata.update(display_mode=mode, white_balance_gains=gains)
        return (payload, metadata) if with_metadata else payload

    def _frame_metadata(self, frame):
        return {'source_type': self.source_type, 'captured_at': frame.captured_at,
                'exposure_lines': self.settings['exposure_lines'], 'gain': self.settings['gain']}

    def close(self):
        self.shutdown.set()
        with self.lock:
            self._close()
        self.monitor.join(timeout=3)
