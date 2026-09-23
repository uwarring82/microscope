"""Bounded retention of the exact raw frame and processing used for each preview."""
from collections import Counter, OrderedDict
from copy import deepcopy
import hashlib
import threading
import uuid

from dili import CameraError
from provenance import build_info


def raw_statistics(frame):
    counts = Counter(frame.pixels)
    total = len(frame.pixels)
    # Same Bayer green phase at each sample, in a small central sensor region.
    w, h, raw = frame.width, frame.height, frame.pixels
    x0, y0 = max(0, (w - 256) // 2) & ~1, max(0, (h - 256) // 2) & ~1
    x1, y1 = min(w - 2, x0 + 256), min(h - 2, y0 + 256)
    energy, samples = 0, 0
    for y in range(y0, y1, 2):
        for x in range(x0 + 1, x1, 2):
            p = y*w+x
            energy += (raw[p] - raw[p+2])**2 + (raw[p] - raw[p+2*w])**2
            samples += 2
    return {'histogram': [counts[i] for i in range(256)], 'pixel_count': total,
            'mean': sum(value*count for value, count in counts.items()) / total,
            'saturated_pixels': counts[255], 'saturated_percent': 100*counts[255]/total,
            'zero_pixels': counts[0], 'zero_percent': 100*counts[0]/total,
            'focus': energy/samples if samples else None,
            'focus_method': 'Mean squared same-phase green differences, DN^2; exposure dependent',
            'focus_region': [x0, y0, max(0, x1-x0), max(0, y1-y0)]}


class FrameCache:
    def __init__(self, capacity=8):
        self.capacity = capacity
        self._frames = OrderedDict()
        self._lock = threading.Lock()

    def add(self, frame, metadata):
        metadata = deepcopy(metadata)
        metadata.update(frame_id=uuid.uuid4().hex, width=frame.width, height=frame.height,
                        resolution=f'{frame.width}x{frame.height}', pixel_format=frame.pixel_format,
                        byte_length=len(frame.pixels), sha256=hashlib.sha256(frame.pixels).hexdigest(),
                        raw_statistics=raw_statistics(frame),
                        camera={'name': 'Di-Li 5MP-B CMOS Camera', 'vid': '0547', 'pid': 'c004', 'revision': 'a000'},
                        row_order='top-to-bottom as acquired', timestamp_basis='host read completion (UTC)')
        metadata.update(software=build_info(), units={'pixel_values':'DN (unsigned 8-bit)', 'exposure_lines':'sensor lines',
                                                     'gain':'sensor register units', 'spatial_scale':'um/pixel', 'focus':'DN^2'})
        with self._lock:
            self._frames[metadata['frame_id']] = (frame, metadata)
            while len(self._frames) > self.capacity:
                self._frames.popitem(last=False)
        return deepcopy(metadata)

    def get(self, frame_id):
        with self._lock:
            if not isinstance(frame_id, str) or frame_id not in self._frames:
                raise CameraError('This preview frame has expired. Resume preview and capture again; no substitute frame was saved.')
            frame, metadata = self._frames[frame_id]
            return frame, deepcopy(metadata)
