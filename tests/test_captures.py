import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibration import fit_scale
from captures import CaptureStore
from dili import Frame, CameraError
from frames import FrameCache, raw_statistics
from replay import RawDataset


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = CaptureStore(Path(self.temporary.name))
        self.cache = FrameCache(capacity=2)
        # Real supported dimensions, with spatially distinct first/last rows.
        raw = bytearray(bytes([200, 60, 70, 20]) * (1280*960//4))
        raw[0], raw[-1] = 0, 255
        self.frame = Frame(bytes(raw), '2026-09-23T10:00:00+00:00')
        self.meta = self.cache.add(self.frame, {'source_type': 'replay', 'captured_at': self.frame.captured_at,
            'exposure_lines': 123, 'gain': 40, 'display_mode': 'color', 'white_balance_gains': [2, 1, 1],
            'provenance': {'dataset': 'example', 'file': 'original.raw', 'sha256': hashlib.sha256(raw).hexdigest()}})

    def capture(self, **fields):
        frame, metadata = self.cache.get(self.meta['frame_id'])
        return self.store.capture(frame, metadata, fields)

    def test_exact_frame_survives_stop_settings_changes_and_session_reopen(self):
        record = self.capture(sample_id='chip A', notes='unmodified sensor data')
        m = record['metadata']
        self.cache.add(Frame(bytes([10])*(1280*960), 'later'), {**self.meta, 'gain': 65})
        reopened = CaptureStore(self.store.root).get(m['session_id'], m['capture_id'])
        self.assertEqual(reopened['metadata']['frame_id'], self.meta['frame_id'])
        self.assertEqual(reopened['metadata']['exposure_lines'], 123)
        self.assertEqual(reopened['metadata']['white_balance_gains'], [2, 1, 1])
        raw_path = Path(record['directory']) / m['file']
        self.assertEqual(raw_path.read_bytes(), self.frame.pixels)
        replay = RawDataset(record['directory'])
        self.assertEqual(replay.groups[0]['frames'][0][1].pixels, self.frame.pixels)
        self.assertEqual(replay.records[m['file']]['provenance']['file'], 'original.raw')

    def test_expired_id_is_rejected_without_substitution(self):
        self.cache.add(self.frame, self.meta)
        self.cache.add(self.frame, self.meta)
        with self.assertRaisesRegex(CameraError, 'expired'):
            self.cache.get(self.meta['frame_id'])
        self.assertFalse(self.store.list_sessions())

    def test_raw_clipping_is_independent_of_rgb_white_balance(self):
        stats = self.meta['raw_statistics']
        self.assertEqual(stats['saturated_pixels'], 1)
        self.assertEqual(stats['zero_pixels'], 1)
        self.assertEqual(sum(stats['histogram']), 1280*960)
        self.assertGreater(self.frame.rgb([2,1,1]).count(255), stats['saturated_pixels'])

    def test_profile_fit_and_annotations_round_trip_with_mode_mismatch_rejection(self):
        record = self.capture()
        m = record['metadata']
        refs = [{'session_id':m['session_id'], 'capture_id':m['capture_id'],
                 'a': {'x':10,'y':20}, 'b': {'x':10+length,'y':20}, 'known_um':known}
                for length,known in [(100,20.1),(200,39.9),(300,60.2)]]
        p = self.store.create_profile({'name':'Test only','objective':'10x','optical_configuration':'adapter A','references':refs})
        self.assertAlmostEqual(p['um_per_pixel'], .20035714285714287)
        self.assertGreater(p['fit_standard_error'], 0)
        data = {'revision':1, 'objective':'10x','optical_configuration':'adapter A','calibration_id':p['id'],
                'markers':[{'id':'line-1','type':'line','label':'gap','a':{'x':2,'y':2},'b':{'x':202,'y':2}}]}
        saved = self.store.update(m['session_id'], m['capture_id'], data)
        self.assertEqual(saved['inspection']['calibration']['id'],p['id'])
        self.assertEqual(saved['inspection']['markers'],data['markers'])
        with self.assertRaisesRegex(CameraError,'edited elsewhere'):
            self.store.update(m['session_id'],m['capture_id'],data)
        with self.assertRaisesRegex(ValueError,'does not match'):
            self.store._inspection({**data,'objective':'20x'},m,3)
        with self.assertRaisesRegex(ValueError,'does not match'):
            self.store._inspection(data,{**m,'resolution':'2592x1944'},3)

    def test_fits_preserves_byte_order_bayer_phase_units_and_provenance(self):
        record = self.capture(objective='10x\nétalon')
        m = record['metadata']
        export = self.store.export_fits(m['session_id'],m['capture_id'])
        fits = Path(export['path']).read_bytes()
        cards = []
        for i in range(0,len(fits),80):
            cards.append(fits[i:i+80].decode('ascii'))
            if cards[-1][:8].strip() == 'END':
                break
        end = next(i for i,c in enumerate(cards) if c[:8].strip()=='END')
        header = cards[:end]
        self.assertTrue(all(32 <= ord(char) <= 126 for c in header for char in c))
        offset = ((end+1)*80+2879)//2880*2880
        self.assertEqual(fits[offset:offset+len(self.frame.pixels)],self.frame.pixels)
        self.assertEqual(len(fits)%2880,0)
        keys = {c[:8].strip():c[10:] for c in header}
        self.assertIn("'RGGB",keys['BAYERPAT'])
        self.assertIn("'TOP-DOWN",keys['ROWORDER'])
        self.assertIn('123',keys['EXPLINES']);self.assertIn('40',keys['SENSGAIN'])
        self.assertNotIn('EXPTIME',keys);self.assertNotIn('GAIN',keys)
        self.assertIn(m['sha256'],keys['RAWSHA']);self.assertIn('original.raw',keys['SRCFILE'])
        self.assertEqual(fits[offset],0);self.assertEqual(fits[offset+len(self.frame.pixels)-1],255)

    def test_invalid_annotations_and_corrupted_saved_raw_are_rejected(self):
        record=self.capture();m=record['metadata']
        with self.assertRaisesRegex(ValueError,'inside'):
            self.store.update(m['session_id'],m['capture_id'],{'revision':1,'markers':[{'id':'bad','type':'point','a':{'x':-1,'y':1},'b':{'x':1,'y':1}}]})
        (Path(record['directory'])/m['file']).write_bytes(b'bad')
        with self.assertRaisesRegex(CameraError,'checksum'):
            self.store.export_fits(m['session_id'],m['capture_id'])

    def test_stale_report_revision_and_path_traversal_are_rejected(self):
        record=self.capture();m=record['metadata']
        png=base64.b64encode(self.frame.png()).decode()
        with self.assertRaisesRegex(CameraError,'changed during export'):
            self.store.save_png(m['session_id'],m['capture_id'],{'revision':0,'kind':'inspection.png','png':png})
        with self.assertRaises(ValueError):
            self.store.get('../outside',m['capture_id'])
        with self.assertRaises(ValueError):
            self.store.get(m['session_id'],'../outside')


class CalibrationTests(unittest.TestCase):
    def test_known_slope_and_rejected_nonfinite_intervals(self):
        fit=fit_scale([(10,2),(20,4),(30,6)])
        self.assertEqual(fit['um_per_pixel'],.2)
        self.assertEqual(fit['fit_standard_error'],0)
        for samples in [[(1,1)],[(10,1),(20,2),(30,float('nan'))]]:
            with self.assertRaises(ValueError):fit_scale(samples)
