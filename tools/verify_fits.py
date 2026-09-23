"""Independent synthetic FITS checks. Run: python -m tools.verify_fits [--fitsverify]."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import warnings

import astropy
from astropy.io import fits

from dili import Frame
from fits_export import fits_bytes
from frames import FrameCache


def verify(folder, external=False):
    for width, height in ((1280, 960), (2592, 1944)):
        # Spatial pattern with distinct first/last rows detects flips and truncation.
        raw = b''.join(bytes((x + 7*y) % 256 for x in range(width)) for y in range(height))
        frame = Frame(raw, '2026-09-23T10:00:00.123456+00:00', width, height)
        metadata = FrameCache().add(frame, {
            'captured_at': frame.captured_at, 'source_type': 'replay',
            'exposure_lines': 123, 'gain': 40, 'display_mode': 'color',
            'white_balance_gains': [2, 1, .5], 'capture_id': 'synthetic-capture',
            'provenance': {'dataset': 'synthetic', 'file': 'source.raw',
                           'sha256': hashlib.sha256(raw).hexdigest()}})
        inspection = {'objective': "10×\nO'Brien", 'optical_configuration': 'test only',
                      'sample_id': 'synthetic', 'revision': 1, 'calibration': None,
                      'notes': 'Unicode retained: µm', 'markers': []}
        path = folder / f'synthetic-{width}x{height}.fits'
        path.write_bytes(fits_bytes(frame, metadata, inspection))
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            with fits.open(path, memmap=False) as hdus:
                hdus.verify('exception')
                assert len(hdus) == 2
                primary = hdus[0]
                assert primary.data.dtype.name == 'uint8'
                assert primary.data.shape == (height, width)
                assert primary.data.tobytes() == raw
                assert primary.header['ROWORDER'] == 'TOP-DOWN'
                assert primary.header['BAYERPAT'] == 'RGGB'
                assert primary.header['TSOURCE'] == 'HOSTREAD'
                assert primary.header['EXPLINES'] == 123 and primary.header['SENSGAIN'] == 40
                assert not {'EXPTIME', 'GAIN', 'TIMETYPE'} & set(primary.header)
                assert hashlib.sha256(primary.data.tobytes()).hexdigest() == primary.header['RAWSHA']
                assert hdus['METADATA'].header['CONTENT'] == 'JSON-ASCII'
                document = json.loads(hdus['METADATA'].data.tobytes().decode('ascii'))
                assert document == {'metadata': json.loads(json.dumps(metadata)), 'inspection': inspection}
        if external:
            subprocess.run(['fitsverify', '-q', str(path)], check=True)
        print(f'{width}x{height}: Astropy {astropy.__version__}, raw bytes and JSON round trip passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fitsverify', action='store_true', help='Also run the separately installed NASA fitsverify executable')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        verify(Path(directory), args.fitsverify)
