"""Specimen inspection series: capture fields, verify files, draw overviews.

Run from the repository root against a running server (python3 server.py).

  python3 -m tools.specimen_session capture SERIES --sample LABEL --zoom 4 --field streak \
      [--note TEXT] [--illumination TEXT] [--resolutions preview,full] [--bracket]
  python3 -m tools.specimen_session verify SERIES
  python3 -m tools.specimen_session overview SERIES     # needs numpy and matplotlib

SERIES is a folder under artifacts/captures/ (ignored by Git). Each capture
field gets its own subfolder; nothing is overwritten. The profile matching the
recorded zoom marking and exact resolution is assigned at capture when one
exists. It stays provisional: ring return, specimen height and field
dependence are unvalidated (docs/calibration-validation-plan.md).
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / 'artifacts' / 'captures'
OBJECTIVE = 'Default objective'
NEAR_SATURATION = 240
RESOLUTIONS = {'preview': '1280x960', 'full': '2592x1944'}
PROVISIONAL = ('PROVISIONAL MARKED-SETTING SCALE: measured USAF profile for this zoom marking and '
               'resolution. Ring return, target-to-specimen height transfer and field dependence are '
               'unvalidated; total measurement uncertainty is unknown.')


def configuration(zoom):
    return f'Zoom ring {zoom}; default objective and camera adapter unchanged'


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


class Server:
    def __init__(self, url):
        self.url = url.rstrip('/')

    def request(self, path, data=None, raw=False):
        request = urllib.request.Request(
            self.url + path, data=None if data is None else json.dumps(data).encode(),
            headers={'Content-Type': 'application/json', 'X-Microscope-Client': 'local-ui'})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return (response.read(), response.headers) if raw else json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'{path}: {json.load(error).get("error", error)}') from None
        except urllib.error.URLError as error:
            raise SystemExit(f'Server not reachable at {self.url} ({error.reason}); start python3 server.py') from None


def series_folder(name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{2,80}', name):
        raise SystemExit('Series names use lowercase letters, digits, dots and hyphens')
    return CAPTURES / name


def relative(path):
    path = Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def fits_pixel_offset(data):
    for position in range(0, len(data), 80):
        if data[position:position + 8] == b'END     ':
            return (position // 2880 + 1) * 2880
    raise ValueError('FITS header has no END card')


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:40] or 'field'


def capture(args):
    server = Server(args.server)
    folder = series_folder(args.series)
    series_path = folder / 'series.json'
    series = json.loads(series_path.read_text()) if series_path.exists() else {
        'format': 'microscope-specimen-series-v1', 'series': args.series, 'sample_id': args.sample,
        'created_at': now(), 'steward': args.steward, 'fields': []}
    if series['sample_id'] != args.sample:
        raise SystemExit(f'Series belongs to sample {series["sample_id"]!r}; use a new series name')
    state = server.request('/api/status')
    acquisition = state['acquisition']
    replay = acquisition['source_type'] == 'replay'
    if not state['capture_available']:
        raise SystemExit(state.get('message') or 'Capture unavailable')
    original = {'settings': dict(acquisition['settings']), 'resolution': acquisition['resolution']}
    # A fixed --gain overrides the live setting, so a series stays matched if the operator changes it.
    capture_settings = {**original['settings'], **({'gain': args.gain} if args.gain else {})}
    if not replay and capture_settings['gain'] != original['settings']['gain']:
        print(f"Live gain {original['settings']['gain']} differs; capturing at series gain {capture_settings['gain']}.")
    profiles = server.request('/api/profiles')
    existing = len(list((folder / 'fields').glob('*'))) if (folder / 'fields').exists() else 0
    field_id = f'{existing + 1:02d}-z{args.zoom}-{slug(args.field)}'
    field = folder / 'fields' / field_id
    field.mkdir(parents=True, exist_ok=False)
    notes = (f'Zoom ring {args.zoom} (operator). Field: {args.field}. Position: {args.note or "not recorded"}. '
             f'Illumination: {args.illumination or "not recorded"}. Sample label transcribed verbatim. '
             'No material, coating identity or defect classification inferred.')
    records, session, complete = [], None, False
    try:
        for mode in args.resolutions.split(','):
            resolution = RESOLUTIONS[mode]
            server.request('/api/camera/resolution', {'resolution': resolution})
            server.request('/api/camera/start', {})
            expected = dict(capture_settings)  # what every saved frame of this mode must record
            if not replay:
                server.request('/api/camera/settings', capture_settings)
            match = [p for p in profiles if (p['objective'], p['optical_configuration'], p['resolution'])
                     == (OBJECTIVE, configuration(args.zoom), resolution)]
            profile = match[0] if len(match) == 1 else None
            ladder = args.exposures if args.exposures and mode == 'full' else [None]
            count = len(ladder) * args.frames + (args.max_brackets if args.bracket and mode == 'full' else 0)
            for n in range(1, count + 1):
                if ladder[0] is not None and (n - 1) % args.frames == 0 and n <= len(ladder) * args.frames:
                    expected = {'exposure_lines': ladder[(n - 1) // args.frames], 'gain': capture_settings['gain']}
                    server.request('/api/camera/settings', expected)
                _, headers = server.request('/api/camera/frame.png', raw=True)
                record = server.request('/api/capture', {
                    'frame_id': headers['X-Frame-ID'], 'session_id': session,
                    'session_name': f'{args.sample} - {field_id}', 'sample_id': args.sample,
                    'objective': OBJECTIVE, 'optical_configuration': configuration(args.zoom),
                    'calibration_id': profile['id'] if profile else None, 'markers': [],
                    'notes': notes + (' ' + PROVISIONAL if profile else ' UNCALIBRATED: no matching profile.')})
                meta = record['metadata']
                session = meta['session_id']
                directory = Path(record['directory'])
                raw = (directory / meta['file']).read_bytes()
                if len(raw) != meta['width'] * meta['height'] or hashlib.sha256(raw).hexdigest() != meta['sha256']:
                    raise SystemExit(f'Saved raw frame failed verification: {meta["capture_id"]}')
                fits = server.request('/api/export/fits', {'session_id': session, 'capture_id': meta['capture_id']})
                clipped = meta['raw_statistics']['saturated_pixels']
                # This sensor can plateau at ~246-254 without reaching 255, so also count >= 240.
                near = sum(meta['raw_statistics']['histogram'][NEAR_SATURATION:])
                maximum = max(i for i, c in enumerate(meta['raw_statistics']['histogram']) if c)
                records.append({'name': f'{mode}-{n}', 'session_id': session, 'capture_id': meta['capture_id'],
                                'directory': relative(directory),
                                'resolution': resolution, 'captured_at': meta['captured_at'],
                                'exposure_lines': meta['exposure_lines'], 'gain': meta['gain'],
                                'pixels_at_255': clipped, 'pixels_ge_240': near,
                                'percent_ge_240': 100 * near / (meta['width'] * meta['height']), 'raw_max': maximum, 'sha256': meta['sha256'],
                                'profile_id': profile['id'] if profile else None,
                                'um_per_pixel': profile['um_per_pixel'] if profile else None,
                                'fits': relative(Path(fits['path']))})
                print(f'{mode}-{n}: {meta["capture_id"]} {meta["exposure_lines"]} lines gain {meta["gain"]} '
                      f'max {maximum} at255 {clipped} >=240 {100 * near / (meta["width"] * meta["height"]):.2f}% scale {profile["um_per_pixel"] if profile else "UNCALIBRATED"}')
                # The server labels each frame with the settings in force when it was read. A mismatch means the
                # settings were changed elsewhere (e.g. the dashboard) during capture: keep the frame, stop the field.
                if not replay and (meta['gain'], meta['exposure_lines']) != (expected['gain'], expected['exposure_lines']):
                    raise SystemExit(f"Settings changed during capture: {mode}-{n} recorded {meta['exposure_lines']} lines/"
                                     f"gain {meta['gain']}, expected {expected['exposure_lines']}/{expected['gain']}. "
                                     'Field kept and marked incomplete; do not touch the dashboard sliders while capturing.')
                if n >= len(ladder) * args.frames:
                    # Brackets halve exposure until nothing reaches 240; originals are kept.
                    if replay or not args.bracket or mode != 'full' or near == 0 or meta['exposure_lines'] <= 1:
                        break
                    expected = {'exposure_lines': max(1, meta['exposure_lines'] // 2), 'gain': capture_settings['gain']}
                    server.request('/api/camera/settings', expected)
        complete = True
    finally:
        # Keep whatever was saved, even after a failure; an incomplete field is marked as such.
        entry = {'field_id': field_id, 'zoom_ring_marking': args.zoom, 'field': args.field,
                 'position_note': args.note, 'illumination': args.illumination, 'recorded_at': now(),
                 'source_type': acquisition['source_type'], 'complete': complete, 'records': records}
        write_json(field / 'field.json', entry)
        series['fields'].append({k: entry[k] for k in ('field_id', 'zoom_ring_marking', 'field', 'recorded_at', 'complete')})
        write_json(series_path, series)
        lab_notes(field, series, entry)
        try:
            server.request('/api/camera/stop', {})
            server.request('/api/camera/resolution', {'resolution': original['resolution']})
            if not replay:
                # Live exposure is restored; with --gain the series gain stays, so the dashboard shows the data's gain.
                live = {'exposure_lines': original['settings']['exposure_lines'], 'gain': capture_settings['gain']}
                server.request('/api/camera/settings', live)
                if live['gain'] != original['settings']['gain']:
                    print(f"Live view left at series gain {live['gain']} (was {original['settings']['gain']}).")
        except (SystemExit, OSError) as error:
            print(f'Could not restore camera state: {error}', file=sys.stderr)
    print(f'Saved {len(records)} captures to {relative(field)}')


def lab_notes(field, series, entry):
    rows = ''.join(f"| {r['name']} | {r['resolution']} | {r['captured_at'][11:19]} UTC | {r['exposure_lines']} | "
                   f"{r['gain']} | {r['raw_max']} | {r['pixels_at_255']} | {r.get('percent_ge_240', 0):.2f} | "
                   f"{scale_text(r['um_per_pixel'])} |\n" for r in entry['records'])
    ids = ''.join(f"- {r['name']}: session `{r['session_id']}`, capture `{r['capture_id']}`, "
                  f"raw SHA-256 `{r['sha256']}`\n" for r in entry['records'])
    (field / 'lab-notes.md').write_text(
        f"# {series['sample_id']} — field {entry['field_id']}\n\n"
        f"Zoom ring **{entry['zoom_ring_marking']}** (operator). Field: {entry['field']}. "
        f"Position: {entry['position_note'] or 'not recorded'}. "
        f"Illumination: {entry['illumination'] or 'not recorded'}. Source: {entry['source_type']}."
        f"{'' if entry['complete'] else ' **INCOMPLETE: capture stopped early.**'}\n\n"
        '| Capture | Resolution | Host read | Exposure lines | Gain | Raw max | Pixels at 255 | % ≥240 | µm/px (provisional) |\n'
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |\n' + rows +
        f"\n{PROVISIONAL}\n\nExposure is in sensor lines. The sensor can saturate at about 246-254 DN without "
        'reaching 255, so % ≥240 is the practical clipping indicator; neither is a saturation calibration. Shorter brackets supplement the original frames; no raw frame is replaced.\n\n' + ids)


def iter_records(folder):
    for path in sorted((folder / 'fields').glob('*/field.json')):
        entry = json.loads(path.read_text())
        for record in entry['records']:
            yield entry, record


def verify(args):
    import numpy as np
    from dili import Frame
    folder = series_folder(args.series)
    profiles = {p['id']: p for p in Server(args.server).request('/api/profiles')} if args.server else None
    checks = []
    for entry, r in iter_records(folder):
        base = ROOT / r['directory'] / r['capture_id']
        meta = json.loads(base.with_suffix('.json').read_text())
        inspection = json.loads(base.with_suffix('.annotations.json').read_text())
        raw = base.with_suffix('.raw').read_bytes()
        problems = []
        if hashlib.sha256(raw).hexdigest() != meta['sha256'] or meta['sha256'] != r['sha256']:
            problems.append('raw checksum')
        if np.bincount(np.frombuffer(raw, np.uint8), minlength=256).tolist() != meta['raw_statistics']['histogram']:
            problems.append('histogram')
        if Frame(raw, meta['captured_at'], meta['width'], meta['height']).png(
                meta['display_mode'], meta['white_balance_gains']) != base.with_suffix('.png').read_bytes():
            problems.append('PNG reconstruction')
        fits = (ROOT / r['fits']).read_bytes()
        offset = fits_pixel_offset(fits)
        if fits[offset:offset + len(raw)] != raw:
            problems.append('FITS pixels')
        calibration = inspection['calibration']
        if (calibration or {}).get('id') != r['profile_id'] or (
                calibration and (calibration['resolution'] != meta['resolution'] or
                                 calibration['optical_configuration'] != configuration(entry['zoom_ring_marking']))):
            problems.append('profile match')
        if profiles is not None and calibration and calibration['id'] not in profiles:
            problems.append('profile missing from server')
        checks.append({'field_id': entry['field_id'], 'name': r['name'], 'capture_id': r['capture_id'],
                       'sha256': r['sha256'], 'ok': not problems, 'problems': problems})
        print(('OK  ' if not problems else 'FAIL') + f" {entry['field_id']}/{r['name']} {', '.join(problems)}")
    write_json(folder / 'verification.json', {
        'format': 'specimen-file-verification-v1', 'checked_at': now(), 'checks': checks,
        'scope': 'Raw checksum, histogram, PNG reconstruction, FITS pixel payload and profile match; '
                 'not an independent FITS standards validation or an image interpretation.'})
    failed = sum(not c['ok'] for c in checks)
    print(f'{len(checks) - failed}/{len(checks)} captures verified')
    return 1 if failed else 0


def green(meta, raw):
    import numpy as np
    a = np.frombuffer(raw, np.uint8).reshape(meta['height'], meta['width']).astype(float)
    return (a[0::2, 1::2] + a[1::2, 0::2]) / 2


def overview(args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = series_folder(args.series)
    series = json.loads((folder / 'series.json').read_text())
    items = list(iter_records(folder))
    if not items:
        raise SystemExit('No captures in this series')
    out = folder / 'overview'
    out.mkdir(exist_ok=True)
    columns = 4
    rows = -(-len(items) // columns)
    figure, axes = plt.subplots(rows, columns, figsize=(4 * columns, 3.3 * rows), squeeze=False)
    display = []
    for ax, (label, (entry, r)) in zip(axes.flat, ((f'B{i + 1:02d}', item) for i, item in enumerate(items))):
        base = ROOT / r['directory'] / r['capture_id']
        meta = json.loads(base.with_suffix('.json').read_text())
        raw = base.with_suffix('.raw').read_bytes()
        image = green(meta, raw)
        # The rightmost raw column is always zero; keep it out of the stretch only.
        low, high = np.percentile(image[:, :-1], [1, 99.8])
        ax.imshow(image, cmap='gray', vmin=low, vmax=high, extent=(0, meta['width'], meta['height'], 0))
        mode = 'F' if r['resolution'] == RESOLUTIONS['full'] else 'P'
        ax.set_title(f"{label} | z{entry['zoom_ring_marking']} {mode} | {r['exposure_lines']} lines | "
                     f"≥240: {r.get('percent_ge_240', 0):.2f}%", fontsize=8)
        ax.set_xticks([]); ax.set_yticks([])
        if r['um_per_pixel']:
            length = scale_bar(meta['width'] * r['um_per_pixel'] / 4)
            pixels = length / r['um_per_pixel']
            x0, y0 = meta['width'] * 0.05, meta['height'] * 0.92
            ax.plot([x0, x0 + pixels], [y0, y0], color='orange', lw=2)
            ax.text(x0, y0 - meta['height'] * 0.03, f'{format_length(length)}*', color='orange', fontsize=7)
        display.append({'label': label, 'field_id': entry['field_id'], 'capture_id': r['capture_id'],
                        'sha256': r['sha256'], 'display_low_dn': float(low), 'display_high_dn': float(high)})
    for ax in list(axes.flat)[len(items):]:
        ax.axis('off')
    figure.suptitle(f"{series['sample_id']} — {args.series}\nRaw-green 2×2 means, independent 1–99.8% "
                    'linear stretch per panel. *Provisional scale bars.', fontsize=10)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    figure.savefig(out / 'contact-sheet.png', dpi=150)
    plt.close(figure)
    ledger = ('| ID | Field | Zoom | Mode | Host read (UTC) | Lines | Gain | Raw max | N255 | % ≥240 | µm/px* | SHA-256 |\n'
              '| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |\n')
    for d, (entry, r) in zip(display, items):
        ledger += (f"| {d['label']} | {entry['field_id']} | {entry['zoom_ring_marking']} | {r['resolution']} | "
                   f"{r['captured_at'][11:19]} | {r['exposure_lines']} | {r['gain']} | {r['raw_max']} | "
                   f"{r['pixels_at_255']} | {r.get('percent_ge_240', 0):.2f} | {scale_text(r['um_per_pixel'])} | `{r['sha256'][:12]}` |\n")
    (out / 'ledger.md').write_text(f"# Capture ledger — {series['sample_id']}\n\n{ledger}\n"
                                   f"*Provisional. {PROVISIONAL}\n")
    write_json(out / 'display-provenance.json', display)
    print(f'Wrote {relative(out)}/contact-sheet.png and ledger.md ({len(items)} captures)')


def scale_text(um_per_pixel):
    return f'{um_per_pixel:.5f}' if um_per_pixel else 'UNCALIBRATED'


def scale_bar(target_um):
    steps = [s * 10 ** e for e in range(0, 5) for s in (1, 2, 5)]
    return max((s for s in steps if s <= target_um), default=1)


def format_length(um):
    return f'{um / 1000:g} mm' if um >= 1000 else f'{um:g} µm'


def main(argv=None):
    global CAPTURES
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--server', default='http://127.0.0.1:8765')
    parser.add_argument('--captures', type=Path, help=argparse.SUPPRESS)  # tests only
    commands = parser.add_subparsers(dest='command', required=True)
    c = commands.add_parser('capture', help='Capture one field at the current exposure/gain')
    c.add_argument('series')
    c.add_argument('--sample', required=True, help='Specimen label, transcribed verbatim')
    c.add_argument('--zoom', required=True, help='Zoom ring marking read by the operator')
    c.add_argument('--field', required=True, help='Short field name, e.g. "streak" or "centre"')
    c.add_argument('--note', default='', help='Position/orientation/stage note')
    c.add_argument('--illumination', default='', help='Source, setting, direction/angle')
    c.add_argument('--steward', default='U.Warring')
    c.add_argument('--resolutions', default='preview,full', choices=['preview', 'full', 'preview,full', 'full,preview'])
    c.add_argument('--frames', type=int, default=1, help='Frames per resolution at the set exposure')
    c.add_argument('--bracket', action='store_true', help='Full resolution: halve exposure until no pixel is >= 240')
    c.add_argument('--gain', type=int, help='Fixed gain register for all frames (default: live setting)')
    c.add_argument('--exposures', type=lambda text: [int(v) for v in text.split(',')],
                   help='Full resolution: comma-separated exposure lines, e.g. 129,258,515 (gain unchanged)')
    c.add_argument('--max-brackets', type=int, default=5)
    for name in ('verify', 'overview'):
        commands.add_parser(name).add_argument('series')
    args = parser.parse_args(argv)
    CAPTURES = args.captures or CAPTURES
    if args.command == 'capture':
        if args.frames < 1 or args.max_brackets < 0:
            raise SystemExit('Use at least one frame and a non-negative bracket count')
        return capture(args)
    return {'verify': verify, 'overview': overview}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
