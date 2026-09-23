import struct
import unittest
import zlib
from unittest.mock import patch
from acquisition import Acquisition
from dili import Frame, CameraError, _integer


class FrameTests(unittest.TestCase):
    def test_png_preserves_raw_intensity_and_dimensions(self):
        frame = Frame(bytes([0, 255, 128, 11]), 'test', width=2, height=2)
        png = frame.png()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        offset = 8
        chunks = {}
        while offset < len(png):
            length = struct.unpack_from('>I', png, offset)[0]
            kind = png[offset+4:offset+8]
            data = png[offset+8:offset+8+length]
            crc = struct.unpack_from('>I', png, offset+8+length)[0]
            self.assertEqual(crc, zlib.crc32(kind+data))
            chunks[kind] = data
            offset += length+12
        self.assertEqual(struct.unpack('>IIBBBBB', chunks[b'IHDR']), (2, 2, 8, 0, 0, 0, 0))
        self.assertEqual(zlib.decompress(chunks[b'IDAT']), b'\0\0\xff\0\x80\x0b')

    def test_partial_frames_are_rejected(self):
        with self.assertRaises(ValueError):
            Frame(b'\0', 'test', width=2, height=2)

    def test_settings_do_not_wrap_or_coerce_ctypes_unsigned_values(self):
        for value in [-1, 2**32+1, 0.5, True, '1']:
            with self.assertRaises(ValueError):
                _integer(value, 1, 3000)


class AcquisitionTests(unittest.TestCase):
    @patch('acquisition.Camera')
    def test_failed_read_closes_device_and_preserves_error(self, camera):
        service = Acquisition()
        try:
            service.start()
            camera.return_value.read.side_effect = CameraError('USB disconnected')
            with self.assertRaises(CameraError):
                service.read_png()
            camera.return_value.close.assert_called_once()
            self.assertFalse(service.state()['running'])
            self.assertEqual(service.state()['error'], 'USB disconnected')
        finally:
            service.close()

    @patch('acquisition.Camera')
    def test_failed_settings_close_device_without_claiming_success(self, camera):
        service = Acquisition()
        try:
            service.start()
            camera.return_value.set_gain.side_effect = CameraError('USB stalled')
            with self.assertRaises(CameraError):
                service.configure({'exposure_lines': 1000, 'gain': 50})
            self.assertFalse(service.state()['running'])
            self.assertEqual(service.settings, {'exposure_lines': 500, 'gain': 40})
            camera.return_value.close.assert_called_once()
        finally:
            service.close()

    @patch('acquisition.Camera')
    def test_resolution_change_restarts_stream_with_existing_settings(self, camera):
        service = Acquisition()
        try:
            service.start()
            service.set_resolution('2592x1944')
            camera.return_value.stop.assert_called_once()
            camera.return_value.start.assert_called_with(exposure_lines=500, gain=40, resolution='2592x1944')
            state = service.state()
            self.assertEqual((state['width'], state['height']), (2592, 1944))
            self.assertTrue(state['running'])
            with self.assertRaises(ValueError):
                service.set_resolution('5000x5000')
            self.assertEqual(service.state()['resolution'], '2592x1944')
        finally:
            service.close()

    @patch('acquisition.Camera')
    def test_failed_resolution_change_closes_handle_and_keeps_last_mode(self, camera):
        service = Acquisition()
        try:
            service.start()
            camera.return_value.start.side_effect = CameraError('USB mode change failed')
            with self.assertRaises(CameraError):
                service.set_resolution('2592x1944')
            self.assertFalse(service.state()['running'])
            self.assertEqual(service.state()['resolution'], '1280x960')
            camera.return_value.close.assert_called_once()
        finally:
            service.close()

    @patch('acquisition.Camera')
    def test_white_balance_failure_keeps_stream_and_prior_gains(self, camera):
        service = Acquisition()
        try:
            service.start()
            camera.return_value.read.return_value.white_balance.side_effect = CameraError('Reference clipped')
            with self.assertRaises(CameraError):
                service.balance_neutral()
            self.assertTrue(service.state()['running'])
            self.assertEqual(service.white_balance_gains, (1, 1, 1))
            camera.return_value.close.assert_not_called()
        finally:
            service.close()

    @patch('acquisition.Camera')
    def test_processing_is_software_only_and_metadata_matches_frame(self, camera):
        service = Acquisition()
        try:
            service.start()
            frame = camera.return_value.read.return_value
            frame.png.return_value = b'encoded PNG'
            service.set_processing({'display_mode': 'color', 'white_balance_gains': [0.5, 1, 2]})
            payload, metadata = service.read_png(with_metadata=True)
            self.assertEqual(payload, b'encoded PNG')
            self.assertEqual(metadata['white_balance_gains'], (0.5, 1, 2))
            frame.png.assert_called_once_with('color', (0.5, 1, 2))
            camera.return_value.set_gain.assert_not_called()
            camera.return_value.set_exposure_lines.assert_not_called()
            with self.assertRaises(ValueError):
                service.set_processing({'display_mode': 'color', 'white_balance_gains': [float('nan'), 1, 2]})
            self.assertEqual(service.white_balance_gains, (0.5, 1, 2))
        finally:
            service.close()


class ColorPNGTests(unittest.TestCase):
    def test_color_png_channel_order_dimensions_and_raw_preservation(self):
        raw = bytes([200,100,200,100, 100,50,100,50] * 2)
        frame = Frame(raw, 'test', width=4, height=4)
        png = frame.png('color')
        self.assertEqual(frame.pixels, raw)
        self.assertEqual(struct.unpack_from('>IIBBBBB', png, 16), (4,4,8,2,0,0,0))
        offset = 8
        compressed = b''
        while offset < len(png):
            length = struct.unpack_from('>I', png, offset)[0]
            if png[offset+4:offset+8] == b'IDAT':
                compressed += png[offset+8:offset+8+length]
            offset += length + 12
        self.assertEqual(zlib.decompress(compressed), (b'\0'+bytes([200,100,50])*4)*4)
