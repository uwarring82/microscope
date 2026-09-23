import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from dili import CameraError
from replay import RawDataset, ReplayAcquisition
from server import acquisition_report


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.manifest = {'format': 'dili-raw-dataset-v1', 'white_balance_gains': [1.2, 1, 1.4],
                         'default_resolution': '1280x960', 'frames': []}
        for i, (width, height, exposure) in enumerate([(1280, 960, 100), (1280, 960, 100), (2592, 1944, 200)]):
            raw = bytes([40 + i, 80, 80, 20]) * (width * height // 4)
            filename = f'frame-{i}.raw'
            (self.folder / filename).write_bytes(raw)
            self.manifest['frames'].append({'file': filename, 'resolution': f'{width}x{height}',
                'width': width, 'height': height, 'pixel_format': 'RAW8_RGGB',
                'captured_at': f'2026-09-23T10:00:0{i}+00:00', 'exposure_lines': exposure, 'gain': 40,
                'byte_length': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        self.write_manifest()

    def write_manifest(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    @patch('server.status', side_effect=AssertionError('Replay must not query USB'))
    @patch('acquisition.Camera', side_effect=AssertionError('Replay must not open USB'))
    def test_replay_loops_original_bytes_and_timestamps_without_usb(self, *_):
        service = ReplayAcquisition(self.folder)
        self.addCleanup(service.close)
        self.assertEqual(acquisition_report(service)['usb_state'], 'not_used')
        service.start()
        with service.lock:
            frames = [service._read() for _ in range(3)]
        self.assertEqual(frames[0].pixels, (self.folder / 'frame-0.raw').read_bytes())
        self.assertEqual(frames[0], frames[2])
        self.assertNotEqual(frames[0].pixels, frames[1].pixels)
        self.assertEqual(frames[1].captured_at, self.manifest['frames'][1]['captured_at'])
        self.assertEqual(service.state()['white_balance_gains'], (1.2, 1, 1.4))
        with self.assertRaises(CameraError):
            service.configure({'exposure_lines': 500, 'gain': 60})
        self.assertEqual(service.state()['settings'], {'exposure_lines': 100, 'gain': 40})
        self.assertTrue(service.state()['running'])

    def test_recording_switch_changes_dimensions_and_exact_frame_metadata(self):
        self.manifest['default_recording_id'] = '1'
        self.write_manifest()
        service = ReplayAcquisition(self.folder)
        self.addCleanup(service.close)
        self.assertEqual(service.state()['resolution'], '2592x1944')
        service.start()
        service.select_recording('1')
        service.set_processing({'display_mode': 'raw', 'white_balance_gains': [2, 1, 3]})
        payload, metadata = service.read_png(with_metadata=True)
        self.assertEqual(struct.unpack_from('>IIBB', payload, 16), (2592, 1944, 8, 0))
        self.assertEqual(metadata['recorded_file'], 'frame-2.raw')
        self.assertEqual(metadata['captured_at'], self.manifest['frames'][2]['captured_at'])
        self.assertEqual(metadata['exposure_lines'], 200)
        self.assertEqual(metadata['source_type'], 'replay')
        service.set_resolution('1280x960')
        self.assertEqual(service.state()['settings']['exposure_lines'], 100)
        with self.assertRaises(ValueError):
            service.select_recording('unknown')
        self.assertEqual(service.state()['recording_id'], '0')
        service.stop()
        self.assertFalse(service.state()['running'])

    def test_modified_and_truncated_raw_files_are_rejected(self):
        path = self.folder / 'frame-0.raw'
        original = path.read_bytes()
        path.write_bytes(b'\xff' + original[1:])
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            RawDataset(self.folder)
        path.write_bytes(original[:-1])
        with self.assertRaisesRegex(ValueError, 'byte count'):
            RawDataset(self.folder)

    def test_each_frame_uses_recorded_balance_with_explicit_manual_override(self):
        self.manifest['frames'][1]['white_balance_gains'] = [2, 1, .5]
        self.write_manifest()
        service = ReplayAcquisition(self.folder)
        self.addCleanup(service.close)
        service.start()
        for expected in [(1.2, 1, 1.4), (2, 1, .5), (1.2, 1, 1.4)]:
            png, meta = service.read_png(with_metadata=True)
            frame, retained = service.retained.get(meta['frame_id'])
            self.assertEqual(meta['white_balance_gains'], expected)
            self.assertEqual(png, frame.png('color', expected))
            self.assertEqual(retained['white_balance_source'], 'recorded')
        service.set_processing({'display_mode':'raw', 'white_balance_source':'recorded'})
        _, meta = service.read_png(with_metadata=True)
        self.assertEqual(meta['white_balance_gains'], (2, 1, .5))
        service.set_processing({'display_mode':'color', 'white_balance_gains':[1,1,1]})
        for _ in range(2):
            _, meta = service.read_png(with_metadata=True)
            self.assertEqual(meta['white_balance_gains'], (1,1,1))
            self.assertEqual(meta['white_balance_source'], 'manual')
        service.set_processing({'display_mode':'color', 'white_balance_source':'recorded'})
        service.read_png()
        _, meta = service.read_png(with_metadata=True)
        self.assertEqual(meta['white_balance_gains'], (2,1,.5))
        service.select_recording('1')
        self.assertEqual(service.state()['white_balance_gains'], (1.2,1,1.4))

    def test_invalid_per_frame_white_balance_is_rejected(self):
        self.manifest['frames'][1]['white_balance_gains'] = [float('nan'),1,1]
        self.write_manifest()
        with self.assertRaises(ValueError):
            RawDataset(self.folder)

    def test_manifest_cannot_reference_raw_files_outside_dataset(self):
        self.manifest['frames'][0]['file'] = '../outside.raw'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'directly beside'):
            RawDataset(self.folder)
