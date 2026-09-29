"""Display-lattice calibration: scale, lateral and axial chromatic checks from an OLED subpixel lattice.

  python3 -m tools.display_lattice SERIES [--pitch-um 55.2174]     # series under artifacts/captures/

The display pitch p comes from the manufacturer's pixel density (iPhone 17 Pro: 460 ppi, p = 25.4 mm / 460). In the
diamond (RGBG) OLED layout, green subpixels lie on a square lattice of pitch p and red and blue on square lattices of
pitch p*sqrt(2). A least-squares lattice fit to subpixel centroids in each raw Bayer plane gives micrometres per raw
pixel per colour:
  * scale per zoom mark and camera mode, compared with the stored USAF marked-setting profiles;
  * lateral chromatic aberration as the red/green and blue/green scale ratios and radial terms;
  * axial chromatic aberration from a through-focus series: each colour's subpixel image width against the focus step
    given in the field name (e.g. "focus+2") or note ("focus=+2"); the step of minimum width per colour.
Frames showing a single colour (from a colour-cycling page) are classified automatically. In white frames the blue plane
also sees green light, so blue detections close to green subpixels are discarded.

Needs numpy, scipy and matplotlib (analysis only). Results: artifacts/captures/SERIES/display-lattice/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / 'artifacts' / 'captures'
PITCH_UM = 25400 / 460
FACTOR = {'G': 1.0, 'R': np.sqrt(2), 'B': np.sqrt(2)}
OFFSET = {'R': (0.0, 0.0), 'G': (0.5, 0.5), 'B': (1.0, 1.0)}  # raw (x, y) phase of each Bayer plane


def planes(raw):
    raw = raw.astype(float)
    return {'R': raw[0::2, 0::2], 'G': (raw[0::2, 1::2] + raw[1::2, 0::2]) / 2, 'B': raw[1::2, 1::2]}


def spots(img, channel, sigma=1.2, frac=0.35):
    """Subpixel centroids (raw x, y) and intensity-weighted RMS radii (raw px) in one Bayer plane."""
    smooth = ndimage.gaussian_filter(img, sigma)
    lo, hi = np.percentile(smooth, 50), np.percentile(smooth, 99.5)
    if hi - lo < 8:
        return np.empty((0, 2)), np.empty(0)
    mask = smooth > lo + frac * (hi - lo)
    lab, n = ndimage.label(mask)
    if n == 0:
        return np.empty((0, 2)), np.empty(0)
    idx = np.arange(1, n + 1)
    weight = np.clip(img - lo, 0, None)
    sizes = ndimage.sum(mask, lab, idx)
    cm = np.array(ndimage.center_of_mass(weight, lab, idx))
    yy, xx = np.indices(img.shape)
    total = ndimage.sum(weight, lab, idx)
    m2 = (ndimage.sum(weight * yy ** 2, lab, idx) + ndimage.sum(weight * xx ** 2, lab, idx)) / np.maximum(total, 1e-9)
    radius = 2 * np.sqrt(np.clip(m2 - (cm ** 2).sum(1), 0, None))  # plane px -> raw px
    keep = (sizes >= 4) & (sizes <= 4 * np.median(sizes))
    ox, oy = OFFSET[channel]
    points = np.column_stack([2 * cm[keep, 1] + ox, 2 * cm[keep, 0] + oy])
    return points, radius[keep]


def fit_lattice(points, iterations=4):
    """Bravais lattice P = P0 + i*a1 + j*a2 by least squares, with a joint radial term k (relative displacement
    at the image half-diagonal). Returns None when the points do not form a clean lattice."""
    if len(points) < 30:
        return None
    tree = cKDTree(points)
    _, nn = tree.query(points, k=5)
    vec = (points[nn[:, 1:]] - points[:, None, :]).reshape(-1, 2)
    ang = np.degrees(np.arctan2(vec[:, 1], vec[:, 0]))
    first, second = vec[(ang > -45) & (ang <= 45)], vec[(ang > 45) & (ang <= 135)]
    if len(first) < 10 or len(second) < 10:
        return None
    a1, a2 = np.median(first, axis=0), np.median(second, axis=0)
    origin = points[np.argmin(np.hypot(*(points - points.mean(0)).T))]
    inliers = np.ones(len(points), bool)
    for _ in range(iterations):
        ij = np.round(np.linalg.solve(np.column_stack([a1, a2]), (points - origin).T).T)
        design = np.column_stack([np.ones(len(points)), ij])
        coef, *_ = np.linalg.lstsq(design[inliers], points[inliers], rcond=None)
        origin, a1, a2 = coef
        residual = points - design @ coef
        inliers = np.hypot(*residual.T) < 0.2 * np.hypot(*a1)
    if inliers.sum() < 0.7 * len(points) or inliers.sum() < 30:
        return None
    return {'a1': a1, 'a2': a2, 'area': abs(a1[0] * a2[1] - a1[1] * a2[0]), 'ij': ij, 'inliers': inliers,
            'rms': float(np.sqrt((residual[inliers] ** 2).sum(1).mean())), 'n': int(inliers.sum())}


def radial_term(points, lattice, width, height):
    """Joint linear fit of the lattice plus k * (P - c) * (|P - c| / half-diagonal)^2."""
    c = np.array([width / 2, height / 2])
    half = np.hypot(width, height) / 2
    inl, ij = lattice['inliers'], lattice['ij']
    g = (points - c) * ((np.hypot(*(points - c).T) / half) ** 2)[:, None]
    n = inl.sum()
    design = np.zeros((2 * n, 7))
    design[:n, 0], design[:n, 1], design[:n, 3], design[:n, 6] = 1, ij[inl, 0], ij[inl, 1], g[inl, 0]
    design[n:, 2], design[n:, 4], design[n:, 5], design[n:, 6] = 1, ij[inl, 0], ij[inl, 1], g[inl, 1]
    sol, *_ = np.linalg.lstsq(design, np.concatenate([points[inl, 0], points[inl, 1]]), rcond=None)
    centre_area = abs(sol[1] * sol[5] - sol[4] * sol[3])
    return float(sol[6]), float(centre_area)


def analyse_frame(raw, pitch_um=PITCH_UM):
    """Per-colour lattice scale (um per raw px), radial term, spot width and the displayed colour."""
    P = planes(raw)
    height, width = raw.shape
    found = {c: spots(P[c], c) for c in 'RGB'}
    level = {c: float(np.percentile(P[c], 99.5) - np.percentile(P[c], 50)) for c in 'RGB'}
    lit = [c for c in 'RGB' if level[c] > 0.25 * max(level.values()) and len(found[c][0]) >= 30]
    shown = 'white' if lit == ['R', 'G', 'B'] or ('R' in lit and 'G' in lit) else (lit[0] if len(lit) == 1 else '+'.join(lit))
    if shown == 'white' and len(found['G'][0]) and len(found['B'][0]):
        # The blue plane also records green light: keep only detections away from green subpixels.
        green = cKDTree(found['G'][0])
        spacing = np.median(green.query(found['G'][0], k=2)[0][:, 1])
        far = green.query(found['B'][0])[0] > 0.3 * spacing
        found['B'] = (found['B'][0][far], found['B'][1][far])
    out = {'shown': shown, 'channels': {}}
    for c in 'RGB':
        points, radius = found[c]
        lattice = fit_lattice(points) if c in lit or shown == 'white' else None
        if not lattice:
            continue
        k, centre_area = radial_term(points, lattice, width, height)
        out['channels'][c] = {
            'um_per_px': float(FACTOR[c] * pitch_um / np.sqrt(lattice['area'])),
            'um_per_px_centre': float(FACTOR[c] * pitch_um / np.sqrt(centre_area)),
            'axis_ratio': float(np.hypot(*lattice['a1']) / np.hypot(*lattice['a2'])),
            'angle_deg': float(np.degrees(np.arccos(lattice['a1'] @ lattice['a2'] /
                                                    np.hypot(*lattice['a1']) / np.hypot(*lattice['a2'])))),
            'radial_k': k, 'rms_px': lattice['rms'], 'n': lattice['n'],
            'spot_rms_radius_px': float(np.median(radius[lattice['inliers']]))}
    return out


def focus_step(field):
    text = f"{field.get('field', '')} {field.get('position_note', '')}"
    match = re.search(r'focus\s*[=+]?\s*([+-]?\d+(?:\.\d+)?)', text, re.I)
    return float(match.group(1)) if match else None


def usaf_profiles():
    path = ROOT / 'sessions' / 'calibrations.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    profiles = data['profiles'] if isinstance(data, dict) else data
    table = {}
    for p in profiles:
        match = re.match(r'Zoom ring ([0-9.]+);', p['optical_configuration'])
        if match:
            table[(match.group(1), p['resolution'])] = p['um_per_pixel']
    return table


def analyse_series(series, pitch_um=PITCH_UM):
    folder = CAPTURES / series
    usaf = usaf_profiles()
    rows = []
    for field_path in sorted((folder / 'fields').glob('*/field.json')):
        field = json.loads(field_path.read_text())
        for record in field['records']:
            base = ROOT / record['directory'] / record['capture_id']
            meta = json.loads(base.with_suffix('.json').read_text())
            raw = base.with_suffix('.raw').read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta['sha256']:
                raise SystemExit(f"Checksum mismatch: {record['capture_id']}")
            result = analyse_frame(np.frombuffer(raw, np.uint8).reshape(meta['height'], meta['width']), pitch_um)
            zoom = str(field['zoom_ring_marking'])
            reference = usaf.get((zoom, meta['resolution']))
            green = result['channels'].get('G')
            rows.append({'field_id': field['field_id'], 'zoom': zoom, 'focus_step': focus_step(field),
                         'name': record['name'], 'capture_id': record['capture_id'], 'captured_at': meta['captured_at'],
                         'resolution': meta['resolution'], 'exposure_lines': meta['exposure_lines'], 'gain': meta['gain'],
                         'percent_ge_240': record.get('percent_ge_240'), 'sha256': meta['sha256'], **result,
                         'usaf_um_per_px': reference,
                         'phone_over_usaf': green['um_per_px_centre'] / reference if green and reference else None})
            ch = result['channels']
            print(f"{field['field_id']:<28} {record['name']:<10} {meta['resolution']:>9} {result['shown']:<6} "
                  + ' '.join(f"{c}:{v['um_per_px']:.5f}" for c, v in ch.items())
                  + (f"  vs USAF {rows[-1]['phone_over_usaf'] - 1:+.3%}" if rows[-1]['phone_over_usaf'] else ''))
    out = folder / 'display-lattice'
    out.mkdir(exist_ok=True)
    (out / 'results.json').write_text(json.dumps({'format': 'display-lattice-v1', 'pitch_um': pitch_um,
                                                  'frames': rows}, indent=2) + '\n')
    figures(rows, out)
    return rows


def figures(rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colours = {'R': '#e34948', 'G': '#008300', 'B': '#2a78d6'}
    full = [r for r in rows if r['resolution'] == '2592x1944' and 'G' in r['channels'] and r['focus_step'] in (None, 0)]
    if full:
        fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4))
        for r in full:
            z = float(r['zoom'])
            a.plot(z, r['channels']['G']['um_per_px_centre'], 'o', color=colours['G'])
            if r['usaf_um_per_px']:
                a.plot(z, r['usaf_um_per_px'], 's', mfc='none', color='#52514e')
            for c in 'RB':
                if c in r['channels']:
                    b.plot(z, 100 * (r['channels'][c]['um_per_px'] / r['channels']['G']['um_per_px'] - 1), 'o',
                           color=colours[c])
        a.set_yscale('log'); a.set_xlabel('zoom mark'); a.set_ylabel('µm per raw px (centre)')
        a.set_title('Display lattice (green dots) vs USAF profile (open squares)', fontsize=9)
        b.axhline(0, color='#52514e', lw=0.8); b.set_xlabel('zoom mark'); b.set_ylabel('scale − green scale (%)')
        b.set_title('Lateral colour: red and blue lattice scale relative to green', fontsize=9)
        fig.tight_layout(); fig.savefig(out / 'scale-and-lateral-colour.png', dpi=150); plt.close(fig)
    series = [r for r in rows if r['focus_step'] is not None]
    if series:
        zooms = sorted({r['zoom'] for r in series}, key=float)
        fig, axes = plt.subplots(1, len(zooms), figsize=(4 * len(zooms), 3.4), squeeze=False)
        for ax, z in zip(axes[0], zooms):
            for c in 'RGB':
                pts = sorted((r['focus_step'], r['channels'][c]['spot_rms_radius_px'])
                             for r in series if r['zoom'] == z and c in r['channels'])
                if pts:
                    ax.plot(*zip(*pts), 'o-', color=colours[c], label=c)
            ax.set_title(f'zoom {z}: subpixel image width vs focus', fontsize=9)
            ax.set_xlabel('focus step'); ax.set_ylabel('RMS radius (raw px)'); ax.legend(frameon=False, fontsize=8)
        fig.tight_layout(); fig.savefig(out / 'through-focus.png', dpi=150); plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('series')
    parser.add_argument('--pitch-um', type=float, default=PITCH_UM)
    args = parser.parse_args(argv)
    analyse_series(args.series, args.pitch_um)


if __name__ == '__main__':
    main()
