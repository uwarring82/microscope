"""Display-lattice calibration: scale, lateral and axial chromatic checks from an OLED subpixel lattice.

  python3 -m tools.display_lattice SERIES [--pitch-um 55.2174]     # series under artifacts/captures/

The display pitch p comes from the manufacturer's pixel density (iPhone 17 Pro: 460 ppi, p = 25.4 mm / 460). In the
diamond (RGBG) OLED layout, green subpixels lie on a square lattice of pitch p and red and blue on square lattices of
pitch p*sqrt(2). A least-squares lattice fit to subpixel centroids in each raw Bayer plane gives micrometres per raw
pixel per colour:
  * scale per zoom mark and camera mode, compared with the stored USAF marked-setting profiles;
  * lateral chromatic aberration as the red/green and blue/green scale ratios and radial terms;
  * axial chromatic aberration from a through-focus series: each colour's lattice modulation (Fourier amplitude at its
    own lattice fundamental over the plane mean, which needs no spot detection) and subpixel image width against the
    focus step given in the field name (e.g. "focus+2") or note ("focus=+2"); the step of maximum modulation per colour.
Frames of a colour-cycling field are classified by each plane's amplitude at its own lattice frequency, relative to the
field's maximum, in four row bands; a frame whose bands disagree changed colour during readout and is marked "mixed".
Frequency selection removes leakage at other lattice frequencies (green light in the blue plane) but not between red and
blue, which share their lattice frequency, nor the p*sqrt(2) component that green subpixels of alternating orientation
put into the red plane; check the classification against the page's known colour order. Other fields are taken as white. In white frames the blue plane also sees green light, so blue detections close to green
subpixels are discarded.

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


def fft_lattice(plane, expected_period_raw, tolerance=0.15):
    """Square-lattice fit in Fourier space for lattices too fine for centroids.

    `plane` is one Bayer plane (half resolution). The two fundamental peaks nearest the expected period (raw px,
    used only to choose between the lattice and its harmonics or the p*sqrt(2) lattice) are located with a quadratic
    fit of the log-magnitude around each maximum. Returns the lattice cell area in raw px^2, both periods and their
    angle, the reciprocal vectors (cycles per raw px), or None when no clear peak pair exists (for example a lattice
    below the plane's Nyquist limit)."""
    img = plane[:, :plane.shape[1] - plane.shape[1] % 2].astype(float)
    img = img - img.mean()
    img *= np.hanning(img.shape[0])[:, None] * np.hanning(img.shape[1])[None, :]
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(img)))
    h, w = spectrum.shape
    fy, fx = np.meshgrid((np.arange(h) - h // 2) / h, (np.arange(w) - w // 2) / w, indexing='ij')
    radius = np.hypot(fx, fy)
    target = 2 / expected_period_raw                     # cycles per plane pixel
    if target > 0.5:
        return None                                      # beyond the plane's Nyquist frequency
    ring = (radius > target * (1 - tolerance)) & (radius < target * (1 + tolerance)) & (fy >= 0)
    if not ring.any():
        return None
    masked = np.where(ring, spectrum, 0)
    peaks = []
    for _ in range(2):
        iy, ix = np.unravel_index(np.argmax(masked), masked.shape)
        if masked[iy, ix] <= 0 or not (1 <= iy < h - 1 and 1 <= ix < w - 1):
            return None
        patch = np.log(spectrum[iy - 1:iy + 2, ix - 1:ix + 2] + 1e-9)
        dy = 0.5 * (patch[0, 1] - patch[2, 1]) / (patch[0, 1] - 2 * patch[1, 1] + patch[2, 1])
        dx = 0.5 * (patch[1, 0] - patch[1, 2]) / (patch[1, 0] - 2 * patch[1, 1] + patch[1, 2])
        peaks.append(np.array([(ix + dx - w // 2) / w, (iy + dy - h // 2) / h]))
        # suppress this peak (and anything within 30 degrees of it) before looking for the second one
        # a peak and its mirror image (-g) lie 180 degrees apart; compare directions modulo 180 degrees
        difference = np.abs(np.angle(np.exp(2j * (np.arctan2(fy, fx) - np.arctan2(peaks[-1][1], peaks[-1][0]))))) / 2
        near = np.degrees(difference) < 30
        masked = np.where(near, 0, masked)
    g1, g2 = peaks
    cross = abs(g1[0] * g2[1] - g1[1] * g2[0])
    if cross < 0.5 * np.hypot(*g1) * np.hypot(*g2):
        return None                                      # the two peaks are not a lattice basis
    area_plane = 1 / cross                               # real-space cell area in plane px^2
    # reciprocal vectors in cycles per raw px: with lattice vectors a_j (raw px), g_i . a_j = delta_ij, so the scale along an
    # image direction d is pitch * |G d| for G with rows g1, g2 (sign and order do not matter)
    return {'area_raw': 4 * area_plane, 'reciprocal_raw': [(g1 / 2).tolist(), (g2 / 2).tolist()],
            'period1_raw': 2 / np.hypot(*g1), 'period2_raw': 2 / np.hypot(*g2),
            'angle_deg': float(np.degrees(np.arccos(abs(g1 @ g2) / np.hypot(*g1) / np.hypot(*g2))))}


def lattice_modulation(plane, expected_period_raw, tolerance=0.15):
    """Strength of a square lattice near the expected period (raw px) in one Bayer plane, without detecting spots.

    Returns the cosine amplitude of the two fundamental Fourier peaks (root of the power within +-2 bins of each peak,
    mean of both; DN) and the modulation (amplitude over the plane mean), or None beyond the plane's Nyquist limit. The
    modulation falls as the image defocuses. A lattice at other frequencies does not contribute, but red and blue share
    their lattice frequency and green subpixels of alternating orientation add a p*sqrt(2) component, so in a frame
    showing several colours a plane's modulation mixes them."""
    img = plane[:, :plane.shape[1] - plane.shape[1] % 2].astype(float)
    h, w = img.shape
    power = np.abs(np.fft.fftshift(np.fft.fft2(img * np.hanning(h)[:, None] * np.hanning(w)[None, :]))) ** 2
    fy, fx = np.meshgrid((np.arange(h) - h // 2) / h, (np.arange(w) - w // 2) / w, indexing='ij')
    target = 2 / expected_period_raw                     # cycles per plane pixel
    if target * (1 + tolerance) > 0.5:
        return None
    ring = (np.hypot(fx, fy) > target * (1 - tolerance)) & (np.hypot(fx, fy) < target * (1 + tolerance)) & (fy >= 0)
    ring[:2, :] = ring[-2:, :] = ring[:, :2] = ring[:, -2:] = False
    masked = np.where(ring, power, 0)
    amplitudes = []
    for _ in range(2):
        iy, ix = np.unravel_index(np.argmax(masked), masked.shape)
        amplitudes.append(np.sqrt(power[iy - 2:iy + 3, ix - 2:ix + 3].sum()))
        difference = np.abs(np.angle(np.exp(2j * (np.arctan2(fy, fx) - np.arctan2(fy[iy, ix], fx[iy, ix]))))) / 2
        masked = np.where(np.degrees(difference) < 30, 0, masked)
    dc = np.sqrt(power[h // 2 - 2:h // 2 + 3, w // 2 - 2:w // 2 + 3].sum())
    modulation = 2 * float(np.mean(amplitudes)) / dc     # a cosine a*cos(kx) on a mean m gives a/m
    return {'amplitude': modulation * float(img.mean()), 'modulation': modulation}


def band_amplitudes(raw, green_period_raw, bands=4):
    """Per row band, each colour plane's lattice amplitude at its own lattice period (green p, red and blue p*sqrt(2))."""
    out = []
    for pairs in np.array_split(np.arange(raw.shape[0] // 2), bands):  # whole Bayer row pairs keep the RGGB phase
        P = planes(raw[2 * pairs[0]:2 * (pairs[-1] + 1)])
        out.append({c: (lattice_modulation(P[c], FACTOR[c] * green_period_raw) or {'amplitude': 0.0})['amplitude']
                    for c in 'RGB'})
    return out


def classify_cycle(frames, on=0.5):
    """Displayed colour of each frame of one colour-cycling field (one zoom, exposure and position).

    `frames` holds band_amplitudes() per frame. Each amplitude is normalised by the field's maximum for that band and
    colour, so every colour must appear at least once in the field. A colour counts as shown above `on`: all three ->
    'white', one -> that colour; other combinations, or bands that disagree (the page changed colour during the
    rolling readout) -> 'mixed'. Leakage at a plane's own frequency (red/blue, green in red) must stay below `on`."""
    top = [{c: max(f[b][c] for f in frames) or 1e-9 for c in 'RGB'} for b in range(len(frames[0]))]
    labels = []
    for f in frames:
        per_band = set()
        for b, band in enumerate(f):
            lit = [c for c in 'RGB' if band[c] / top[b][c] > on]
            per_band.add('white' if len(lit) == 3 else lit[0] if len(lit) == 1 else 'mixed')
        labels.append(per_band.pop() if len(per_band) == 1 else 'mixed')
    return labels


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


def analyse_frame(raw, pitch_um=PITCH_UM, shown=None, expected_um_per_px=None):
    """Per-colour lattice scale (um per raw px), radial term, spot width and the displayed colour.

    `shown` ('white', 'R', 'G', 'B' or 'mixed') overrides the level-based guess; with `expected_um_per_px` the lattice
    modulation of each colour plane is added (for through-focus series)."""
    P = planes(raw)
    height, width = raw.shape
    if shown is None:
        shown = displayed_colour({c: float(np.percentile(P[c], 99.5) - np.percentile(P[c], 50)) for c in 'RGB'})
    out = {'shown': shown, 'channels': {}}
    if expected_um_per_px:
        out['modulation'] = {}
        for c in 'RGB':
            m = lattice_modulation(P[c], FACTOR[c] * pitch_um / expected_um_per_px)
            if m:
                out['modulation'][c] = m['modulation']
    if shown == 'mixed':
        return out
    found = {c: spots(P[c], c) for c in 'RGB'}
    if shown != 'white':
        lit = [shown]  # single colour: the other Bayer planes only see leakage of the same subpixels
    else:
        lit = ['R', 'G', 'B']
        if len(found['G'][0]) and len(found['B'][0]):
            # The blue plane also records green light: keep only detections away from green subpixels.
            green = cKDTree(found['G'][0])
            spacing = np.median(green.query(found['G'][0], k=2)[0][:, 1])
            far = green.query(found['B'][0])[0] > 0.3 * spacing
            found['B'] = (found['B'][0][far], found['B'][1][far])
    for c in 'RGB':
        points, radius = found[c]
        lattice = fit_lattice(points) if c in lit else None
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
    # Red and blue share the p*sqrt(2) lattice. A blue fit far from red (or from green when red is absent) latched
    # onto green light leaking into the blue plane; drop it rather than report a wrong scale.
    ch = out['channels']
    if 'B' in ch:
        ref = ch.get('R') or ch.get('G')
        if ref and abs(ch['B']['um_per_px'] / ref['um_per_px'] - 1) > 0.05:
            out['rejected_blue'] = ch.pop('B')['um_per_px']
    return out


def displayed_colour(level):
    """White or the single displayed colour, from the signal level (p99.5 - median) of each Bayer plane.
    Thresholds from 2026-09-29 frames: red-only G/R 0.21; green-only R/G 0.40, B/G 0.22; white G/R 0.68 or more."""
    dominant = max(level, key=level.get)
    top = max(level[dominant], 1e-9)
    if dominant == 'R' and level['G'] / top < 0.35 and level['B'] / top < 0.25:
        return 'R'
    if dominant == 'G' and level['R'] / top < 0.5 and level['B'] / top < 0.35:
        return 'G'
    if dominant == 'B':
        return 'B'
    return 'white'


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
    paths = sorted((folder / 'fields').glob('*/field.json'), key=lambda p: int(p.parent.name.split('-')[0]))
    for field_path in paths:
        field = json.loads(field_path.read_text())
        if 'dark' in field['field']:
            continue
        zoom = str(field['zoom_ring_marking'])
        frames = []
        for record in field['records']:
            base = ROOT / record['directory'] / record['capture_id']
            meta = json.loads(base.with_suffix('.json').read_text())
            raw = base.with_suffix('.raw').read_bytes()
            if hashlib.sha256(raw).hexdigest() != meta['sha256']:
                raise SystemExit(f"Checksum mismatch: {record['capture_id']}")
            frames.append((record, meta, np.frombuffer(raw, np.uint8).reshape(meta['height'], meta['width'])))
        shown = [None] * len(frames)
        cycle = 'cycle' in field['field']
        if not cycle:
            shown = ['white'] * len(frames)  # white page held (protocol); colour-cycling fields are classified
        elif frames:
            # expected lattice period: the USAF profile, else a green fit at this zoom earlier in the series
            expected = usaf.get((zoom, frames[0][1]['resolution'])) or next(
                (r['channels']['G']['um_per_px_centre'] for r in rows if r['zoom'] == zoom
                 and r['resolution'] == frames[0][1]['resolution'] and 'G' in r['channels']), None)
            if expected:
                shown = classify_cycle([band_amplitudes(raw, pitch_um / expected) for _, _, raw in frames])
        for (record, meta, raw), label in zip(frames, shown):
            reference = usaf.get((zoom, meta['resolution']))
            result = analyse_frame(raw, pitch_um, shown=label,
                                   expected_um_per_px=reference if focus_step(field) is not None else None)
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
                for exposure in sorted({r['exposure_lines'] for r in series if r['zoom'] == z}):
                    pts = sorted((r['focus_step'], r['modulation'][c]) for r in series if r['zoom'] == z
                                 and r['exposure_lines'] == exposure and c in r.get('modulation', {}))
                    if pts:
                        top = max(m for _, m in pts)
                        ax.plot([f for f, _ in pts], [m / top for _, m in pts], 'o-', color=colours[c],
                                label=f'{c}, {exposure} lines', alpha=1 if exposure == min(r['exposure_lines'] for r in series) else 0.5)
            ax.set_title(f'zoom {z}: lattice modulation vs focus (÷ maximum)', fontsize=9)
            ax.set_xlabel('focus step'); ax.set_ylabel('relative modulation'); ax.legend(frameon=False, fontsize=7)
        fig.tight_layout(); fig.savefig(out / 'through-focus.png', dpi=150); plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('series')
    parser.add_argument('--pitch-um', type=float, default=PITCH_UM)
    args = parser.parse_args(argv)
    analyse_series(args.series, args.pitch_um)


if __name__ == '__main__':
    main()
