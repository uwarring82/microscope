import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import specimen_session as tool


class FakeServer:
    """Camera stand-in: pixels at 255 fall as exposure is halved."""

    def __init__(self, url, directory):
        self.directory = directory
        self.settings = {'exposure_lines': 800, 'gain': 60}
        self.resolution = '1280x960'
        self.calls = []
        self.count = 0

    def request(self, path, data=None, raw=False):
        self.calls.append((path, data))
        if path == '/api/status':
            return {'capture_available': True, 'acquisition': {
                'source_type': 'camera', 'settings': dict(self.settings), 'resolution': self.resolution}}
        if path == '/api/profiles':
            return [{'id': 'p-full', 'objective': tool.OBJECTIVE, 'optical_configuration': tool.configuration('4'),
                     'resolution': '2592x1944', 'um_per_pixel': 1.08929}]
        if path == '/api/camera/settings':
            self.settings = dict(data)
        elif path == '/api/camera/resolution':
            self.resolution = data['resolution']
        elif path == '/api/camera/frame.png':
            return b'', {'X-Frame-ID': 'f'}
        elif path == '/api/capture':
            self.count += 1
            pixels = bytes([7]) * 12
            capture_id = f'capture-{self.count:032x}'
            (self.directory / f'{capture_id}.raw').write_bytes(pixels)
            clipped = max(0, self.settings['exposure_lines'] - 200) // 100
            histogram = [0] * 256
            histogram[255] = clipped
            histogram[7] = 12 - clipped
            return {'directory': str(self.directory), 'metadata': {
                'session_id': 'session-test', 'capture_id': capture_id, 'file': f'{capture_id}.raw',
                'width': 4, 'height': 3, 'sha256': hashlib.sha256(pixels).hexdigest(),
                'captured_at': '2026-09-24T10:00:00+00:00', 'exposure_lines': self.settings['exposure_lines'],
                'gain': self.settings['gain'], 'raw_statistics': {'saturated_pixels': clipped, 'histogram': histogram}}}
        elif path == '/api/export/fits':
            return {'path': str(self.directory / 'x.fits')}
        return {}


class SpecimenSessionTests(unittest.TestCase):
    def run_capture(self, *extra):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fake = FakeServer(None, root)
        with patch.object(tool, 'Server', lambda url: fake):
            tool.main(['--captures', str(root / 'captures'), 'capture', 'test-series', '--sample', 'Mirror',
                       '--zoom', '4', '--field', 'Streak field', *extra])
        field = json.loads((root / 'captures/test-series/fields/01-z4-streak-field/field.json').read_text())
        return fake, field

    def test_bracketing_halves_full_exposure_until_unclipped_and_restores_settings(self):
        fake, field = self.run_capture('--bracket')
        self.assertTrue(field['complete'])
        self.assertEqual([(r['name'], r['exposure_lines']) for r in field['records']],
                         [('preview-1', 800), ('full-1', 800), ('full-2', 400), ('full-3', 200)])
        self.assertEqual([r['pixels_at_255'] for r in field['records']], [6, 6, 2, 0])
        # Only the matching full-resolution profile exists; preview stays uncalibrated.
        self.assertEqual([r['profile_id'] for r in field['records']], [None, 'p-full', 'p-full', 'p-full'])
        self.assertEqual((fake.settings, fake.resolution), ({'exposure_lines': 800, 'gain': 60}, '1280x960'))
        self.assertEqual(fake.calls[-3][0], '/api/camera/stop')

    def test_without_bracketing_clipped_frames_are_kept_as_recorded(self):
        _, field = self.run_capture('--resolutions', 'full', '--frames', '2')
        self.assertEqual([(r['name'], r['exposure_lines']) for r in field['records']],
                         [('full-1', 800), ('full-2', 800)])

    def test_exposure_ladder_applies_to_full_resolution_only_with_fixed_gain(self):
        fake, field = self.run_capture('--exposures', '100,200,400')
        self.assertEqual([(r['name'], r['exposure_lines'], r['gain']) for r in field['records']],
                         [('preview-1', 800, 60), ('full-1', 100, 60), ('full-2', 200, 60), ('full-3', 400, 60)])
        self.assertEqual(fake.settings, {'exposure_lines': 800, 'gain': 60})


if __name__ == '__main__':
    unittest.main()
