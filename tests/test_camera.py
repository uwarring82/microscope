import subprocess
import unittest
from unittest.mock import patch

import camera


REGISTRY = '''
+-o Other Camera <class IOUSBHostDevice, id 1>
  | { "idVendor" = 99
  |   "idProduct" = 49156
  | }
+-o  5MP-B CMOS Camera@02100000 <class IOUSBHostDevice, id 2>
  | {
  |   "idVendor" = 1351
  |   "idProduct" = 49156
  |   "USB Product Name" = " 5MP-B CMOS Camera"
  |   "USB Vendor Name" = "123456789"
  |   "UsbLinkSpeed" = 480000000
  | }
  +-o IOUSBHostInterface@0 <class IOUSBHostInterface, id 3>
      { "bInterfaceClass" = 255 }
+-o Unrelated Camera <class IOUSBHostDevice, id 4>
  | { "idVendor" = 111
  |   "idProduct" = 222
  | }
  +-o IOUSBHostInterface@0 <class IOUSBHostInterface, id 5>
      { "bInterfaceClass" = 14 }
'''


class CameraTests(unittest.TestCase):
    def test_only_target_camera_and_its_interfaces_are_reported(self):
        devices = camera.parse_registry(REGISTRY)
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['name'], '5MP-B CMOS Camera')
        self.assertEqual(devices[0]['interface_classes'], [255])
        self.assertEqual(devices[0]['link_mbps'], 480)
        self.assertIsNone(devices[0]['serial'])

    @patch('camera.platform.system', return_value='Darwin')
    @patch('camera.subprocess.run')
    def test_usb_presence_never_claims_capture_support(self, run, system):
        run.return_value = subprocess.CompletedProcess([], 0, REGISTRY, '')
        result = camera.status()
        self.assertEqual(result['usb_state'], 'connected')
        self.assertFalse(result['capture_available'])
        self.assertEqual(result['capture_state'], 'driver_required')

    @patch('camera.platform.system', return_value='Darwin')
    @patch('camera.subprocess.run')
    def test_failed_probe_is_distinct_from_disconnected(self, run, system):
        run.side_effect = subprocess.TimeoutExpired('ioreg', 8)
        self.assertEqual(camera.status()['usb_state'], 'unknown')
        run.side_effect = None
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.assertEqual(camera.status()['usb_state'], 'disconnected')


if __name__ == '__main__':
    unittest.main()
