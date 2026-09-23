"""FITS 4.0 primary RAW8 image and an ASCII JSON metadata image extension.

The acquisition row order is preserved byte for byte. The first stored row is
the UI's TOP row, regardless of a FITS viewer's display orientation convention.
"""
import json
from datetime import datetime, timezone


def card(key, value=None, comment=None):
    if value is None:
        text = key if key == 'END' else f'{key:<8} {comment or ""}'
    else:
        if isinstance(value, bool):
            encoded = ('T' if value else 'F').rjust(20)
        elif isinstance(value, (int, float)):
            encoded = (str(value) if isinstance(value, int) else f'{value:.12G}').rjust(20)
        else:
            # Full Unicode and long strings are retained in the JSON extension.
            value = ''.join(char if 32 <= ord(char) <= 126 else '?' for char in str(value))
            escaped = ''
            for char in value:
                piece = "''" if char == "'" else char
                if len(escaped) + len(piece) > 68:
                    break
                escaped += piece
            encoded = "'" + escaped.ljust(8) + "'"
        text = f'{key:<8}= {encoded}'
        if comment and len(text) + 3 < 80:
            text += ' / ' + comment
    return text[:80].ljust(80).encode('ascii', 'replace')


def header(cards):
    result = b''.join(cards + [card('END')])
    return result + b' ' * (-len(result) % 2880)


def padded(data):
    return data + b'\0' * (-len(data) % 2880)


def fits_bytes(frame, metadata, inspection):
    date = datetime.fromisoformat(frame.captured_at).astimezone(timezone.utc).isoformat().replace('+00:00', '')
    cards = [card('SIMPLE', True), card('BITPIX', 8), card('NAXIS', 2),
             card('NAXIS1', frame.width), card('NAXIS2', frame.height), card('EXTEND', True),
             card('BAYERPAT', 'RGGB'), card('ROWORDER', 'TOP-DOWN'),
             card('COMMENT', comment='Raw acquisition order preserved. First stored row is top in the UI.'),
             card('COMMENT', comment='FITS viewers may display axis 2 upward; no pixel rows are flipped.'),
             card('DATE-OBS', date), card('TIMESYS', 'UTC'),
             card('TSOURCE', 'HOSTREAD', 'Custom: UTC host read completion, not exposure start'),
             card('EXPLINES', metadata['exposure_lines'], 'sensor lines; duration not calibrated'),
             card('SENSGAIN', metadata['gain'], 'sensor register setting, not electrons/ADU'),
             card('RAWSHA', metadata['sha256']), card('FRAMEID', metadata['frame_id']),
             card('CAPTID', metadata['capture_id']), card('SOURCE', metadata['source_type']),
             card('OBJECTIV', inspection['objective']), card('OPTCONF', inspection['optical_configuration']),
             card('SAMPLEID', inspection['sample_id']), card('ANNREV', inspection['revision'])]
    provenance = metadata.get('provenance') or {}
    if provenance:
        cards += [card('SRCFILE', provenance['file']), card('SRCSHA', provenance['sha256']),
                  card('SRCDATA', provenance['dataset'])]
    profile = inspection['calibration']
    cards += [card('CALPROF', profile['name'] if profile else 'UNCALIBRATED')]
    if profile:
        cards += [card('CALID', profile['id']), card('SCALEUM', profile['um_per_pixel'], 'micrometers / image pixel'),
                  card('SCALERR', profile['fit_standard_error'], 'fit standard error only, um/pixel')]
    for key, gain in zip(('WBR', 'WBG', 'WBB'), metadata['white_balance_gains']):
        cards.append(card(key, gain, 'display gain only; not applied to raw'))
    document = json.dumps({'metadata': metadata, 'inspection': inspection}, ensure_ascii=True, allow_nan=False).encode('ascii')
    extension = header([card('XTENSION', 'IMAGE'), card('BITPIX', 8), card('NAXIS', 1),
                        card('NAXIS1', len(document)), card('PCOUNT', 0), card('GCOUNT', 1),
                        card('EXTNAME', 'METADATA'), card('CONTENT', 'JSON-ASCII')])
    return header(cards) + padded(frame.pixels) + extension + padded(document)
