"""Replay checksum-verified, recorded sensor frames without opening a USB device."""
import hashlib
import json
import time
from pathlib import Path

from acquisition import Acquisition
from dili import CameraError, Frame, RESOLUTIONS, color_gains, _integer


class RawDataset:
    def __init__(self, path):
        path = Path(path)
        if path.is_dir():
            path = path / 'manifest.json'
        self.path = path.resolve()
        manifest = json.loads(self.path.read_text())
        if manifest.get('format') != 'dili-raw-dataset-v1':
            raise ValueError('Unsupported raw dataset format')
        self.gains = color_gains(manifest.get('white_balance_gains', [1, 1, 1]))
        self.description = str(manifest.get('description', 'Recorded microscope frames'))
        self.groups = []
        self.records = {}
        self.frame_gains = {}
        groups_by_settings = {}
        rows = manifest.get('frames')
        if not isinstance(rows, list) or not rows:
            raise ValueError('Dataset contains no frames')
        for row in rows:
            resolution = row['resolution']
            if resolution not in RESOLUTIONS:
                raise ValueError('Unsupported recorded resolution')
            _, width, height = RESOLUTIONS[resolution]
            if (row['width'], row['height'], row['pixel_format']) != (width, height, 'RAW8_RGGB'):
                raise ValueError('Recorded dimensions or Bayer format do not match')
            exposure = _integer(row['exposure_lines'], 1, 3000)
            gain = _integer(row['gain'], 1, 70)
            filename = row['file']
            if not isinstance(filename, str) or not filename.isascii() or any(ord(c) < 32 for c in filename):
                raise ValueError('Invalid recorded filename')
            raw_path = (self.path.parent / filename).resolve()
            if raw_path.parent != self.path.parent or raw_path.name != filename:
                raise ValueError('Raw files must be directly beside the manifest')
            raw = raw_path.read_bytes()
            if len(raw) != width * height or row['byte_length'] != len(raw):
                raise ValueError(f'Incorrect raw byte count: {filename}')
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError(f'Raw checksum mismatch: {filename}')
            frame = Frame(raw, str(row['captured_at']), width, height)
            self.records[filename] = row
            self.frame_gains[filename] = color_gains(row.get('white_balance_gains', self.gains))
            key = (resolution, exposure, gain)
            if key not in groups_by_settings:
                group = {'id': str(len(self.groups)), 'resolution': resolution,
                         'settings': {'exposure_lines': exposure, 'gain': gain}, 'frames': []}
                groups_by_settings[key] = group
                self.groups.append(group)
            groups_by_settings[key]['frames'].append((filename, frame))
        preferred = manifest.get('default_resolution')
        self.default_id = next((g['id'] for g in self.groups if g['resolution'] == preferred), '0')
        if 'default_recording_id' in manifest:
            preferred_id = manifest['default_recording_id']
            if not any(g['id'] == preferred_id for g in self.groups):
                raise ValueError('Unknown default recording')
            self.default_id = preferred_id

    def choices(self):
        return [{'id': g['id'], 'resolution': g['resolution'], 'settings': dict(g['settings']),
                 'frame_count': len(g['frames'])} for g in self.groups]


class _ReplayStream:
    def __init__(self, group):
        self.frames = group['frames']
        self.index = 0
        self.last_file = None

    def read(self):
        self.last_file, frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame

    def close(self):
        pass


class ReplayAcquisition(Acquisition):
    source_type = 'replay'

    def __init__(self, path):
        self.dataset = RawDataset(path)  # Verify every file before exposing playback.
        self.selected = self.dataset.groups[int(self.dataset.default_id)]
        super().__init__()
        self.resolution = self.selected['resolution']
        self.settings = dict(self.selected['settings'])
        self.white_balance_gains = self.dataset.gains
        self.use_recorded_white_balance = True
        self.white_balance_gains = self._recorded_gains()

    def _recorded_gains(self):
        filename = self.camera.last_file if self.camera and self.camera.last_file else self.selected['frames'][0][0]
        return self.dataset.frame_gains[filename]

    def _read(self):
        frame = super()._read()
        if self.use_recorded_white_balance:
            self.white_balance_gains = self._recorded_gains()
        return frame

    def set_processing(self, data):
        with self.lock:
            data = dict(data)
            source = data.pop('white_balance_source', 'manual')
            if source not in ('recorded', 'manual'):
                raise ValueError('White balance source must be recorded or manual')
            if source == 'recorded':
                data['white_balance_gains'] = self._recorded_gains()
            super().set_processing(data)
            self.use_recorded_white_balance = source == 'recorded'
            return self.state()

    def balance_neutral(self):
        with self.lock:
            super().balance_neutral()
            self.use_recorded_white_balance = False
            return self.state()

    def state(self):
        with self.lock:
            result = super().state()
            result.update(dataset=self.dataset.path.parent.name, description=self.dataset.description,
                          recordings=self.dataset.choices(), recording_id=self.selected['id'],
                          recorded_frame_count=len(self.selected['frames']),
                          white_balance_source='recorded' if self.use_recorded_white_balance else 'manual',
                          recorded_file=self.camera.last_file if self.camera else None)
            return result

    def start(self):
        with self.lock:
            self.last_access = time.monotonic()
            if self.camera is None:
                self.camera = _ReplayStream(self.selected)
                self.frames = 0
                self.error = None
            return self.state()

    def configure(self, settings):
        raise CameraError('Exposure and gain are fixed in recorded data. Choose a recording instead.')

    def select_recording(self, recording_id):
        with self.lock:
            group = next((g for g in self.dataset.groups if g['id'] == recording_id), None)
            if group is None:
                raise ValueError('Unknown recording')
            self.selected = group
            self.resolution, self.settings = group['resolution'], dict(group['settings'])
            if self.camera is not None:
                self.camera = _ReplayStream(group)
            if self.use_recorded_white_balance:
                self.white_balance_gains = self._recorded_gains()
            self.frames = 0
            return self.state()

    def set_resolution(self, resolution):
        group = next((g for g in self.dataset.groups if g['resolution'] == resolution), None)
        if group is None:
            raise ValueError('No recorded frames for this resolution')
        return self.select_recording(group['id'])

    def _frame_metadata(self, frame):
        result = super()._frame_metadata(frame)
        result.update(recorded_file=self.camera.last_file, recording_id=self.selected['id'])
        result['white_balance_source'] = 'recorded' if self.use_recorded_white_balance else 'manual'
        row = self.dataset.records[self.camera.last_file]
        result['provenance'] = {'dataset': self.dataset.path.parent.name,
                                'file': self.camera.last_file, 'sha256': row['sha256'],
                                'previous': row.get('provenance')}
        return result
