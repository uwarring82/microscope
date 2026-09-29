import unittest

try:  # analysis-only dependencies; the runtime and CI need only the standard library
    import numpy as np
    from scipy import ndimage
    from tools import display_lattice as dl
except ImportError:  # pragma: no cover
    np = None


def synthetic_raw(width=1280, height=960, pitch_px=30.0, angle_deg=4.0, red_magnification=1.0, colours='RGB',
                  blur=3.0, leak=0.0, brightness=2000):
    """RGGB mosaic of a diamond OLED lattice: green pitch p, red/blue on p*sqrt(2); red optionally magnified.
    `leak` adds a fraction of each colour's image to the other Bayer planes (colour-filter crosstalk): one number for
    all pairs, or {(colour, plane): fraction}; `brightness` may be given per colour."""
    a = pitch_px * np.sqrt(2)
    t = np.radians(angle_deg)
    rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    n = int(max(width, height) / a) + 3
    i, j = np.meshgrid(np.arange(-n, n + 1), np.arange(-n, n + 1))
    base = np.column_stack([i.ravel(), j.ravel()]) * a
    centre = np.array([width / 2, height / 2])
    sites = {'R': [(0, 0)], 'G': [(a / 2, 0), (0, a / 2)], 'B': [(a / 2, a / 2)]}
    raw = np.full((height, width), 10.0)
    phase = {'R': [(0, 0)], 'G': [(0, 1), (1, 0)], 'B': [(1, 1)]}
    for c in colours:
        img = np.zeros((height, width))
        for offset in sites[c]:
            pts = centre + (base + offset) @ rot.T
            if c == 'R':
                pts = centre + (pts - centre) * red_magnification
            ok = (pts[:, 0] > 2) & (pts[:, 0] < width - 3) & (pts[:, 1] > 2) & (pts[:, 1] < height - 3)
            x, y = pts[ok, 0], pts[ok, 1]
            x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
            fx, fy = x - x0, y - y0
            for dx, dy, w in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
                np.add.at(img, (y0 + dy, x0 + dx), w)
        img = ndimage.gaussian_filter(img, blur) * (brightness[c] if isinstance(brightness, dict) else brightness)
        for other in 'RGB':
            for dy, dx in phase[other]:
                share = 1 if other == c else leak.get((c, other), 0) if isinstance(leak, dict) else leak
                raw[dy::2, dx::2] += share * img[dy::2, dx::2]
    return np.clip(raw, 0, 255).astype(np.uint8)


@unittest.skipIf(np is None, 'numpy/scipy not installed')
class DisplayLatticeTests(unittest.TestCase):
    def test_scale_is_recovered_from_green_and_red_lattices(self):
        pitch_px = 30.0
        result = dl.analyse_frame(synthetic_raw(pitch_px=pitch_px), pitch_um=dl.PITCH_UM)
        self.assertEqual(result['shown'], 'white')
        expected = dl.PITCH_UM / pitch_px
        for c in 'RG':
            self.assertAlmostEqual(result['channels'][c]['um_per_px'] / expected, 1, delta=5e-4)
            self.assertAlmostEqual(result['channels'][c]['angle_deg'], 90, delta=0.05)

    def test_lateral_colour_appears_as_a_red_green_scale_difference(self):
        result = dl.analyse_frame(synthetic_raw(red_magnification=1.003))
        ratio = result['channels']['R']['um_per_px'] / result['channels']['G']['um_per_px']
        self.assertAlmostEqual(ratio, 1 / 1.003, delta=4e-4)  # a magnified red image means fewer µm per pixel

    def test_single_colour_frames_are_classified(self):
        for colour in 'RGB':
            result = dl.analyse_frame(synthetic_raw(colours=colour))
            self.assertEqual(result['shown'], colour)
            self.assertIn(colour, result['channels'])

    def test_fourier_fit_recovers_a_fine_green_lattice(self):
        pitch_px = 8.0  # too fine for centroids after smoothing, like zoom 0.58
        raw = synthetic_raw(pitch_px=pitch_px, angle_deg=3.0, colours='G')
        fit = dl.fft_lattice(dl.planes(raw)['G'], expected_period_raw=pitch_px * 1.05)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(np.sqrt(fit['area_raw']) / pitch_px, 1, delta=1e-3)
        self.assertAlmostEqual(fit['angle_deg'], 90, delta=0.3)
        self.assertIsNone(dl.fft_lattice(dl.planes(raw)['G'], expected_period_raw=3.0))  # beyond Nyquist

    def test_displayed_colour_from_measured_channel_levels(self):
        # Bayer-plane levels measured on 2026-09-29 (iPhone 17 Pro, zoom 4): light leaks into neighbouring planes.
        cases = {'white': (138, 94, 19), 'R': (197, 42, 20), 'G': (71, 178, 40), 'B': (7, 15, 43)}
        for expected, (r, g, b) in cases.items():
            self.assertEqual(dl.displayed_colour({'R': r, 'G': g, 'B': b}), expected)

    def test_cycle_frames_are_classified_by_their_own_lattice_frequency(self):
        # Blue is dim and green leaks strongly into the other planes, as on 2026-09-29: a plane's level cannot tell
        # leaked green from real blue, its amplitude at its own lattice frequency can.
        # plane levels of single-colour frames at zoom 4: green leaks 0.40 into red and 0.22 into blue
        leak = {('G', 'R'): 0.40, ('G', 'B'): 0.22, ('R', 'G'): 0.21, ('R', 'B'): 0.10, ('B', 'R'): 0.16, ('B', 'G'): 0.35}
        level = {'R': 1600, 'G': 2000, 'B': 700}
        frames = {c: synthetic_raw(colours=c, leak=leak, brightness=level) for c in 'RGB'}
        frames['white'] = synthetic_raw(leak=leak, brightness=level)
        green_blue = frames['G'].copy()
        green_blue[480:] = frames['B'][480:]  # the page changed colour during the rolling readout
        names = list(frames) + ['mixed']
        bands = [dl.band_amplitudes(raw, 30.0) for raw in list(frames.values()) + [green_blue]]
        self.assertEqual(dl.classify_cycle(bands), names)

    def test_lattice_modulation_falls_with_blur_and_ignores_other_lattices(self):
        sharp = dl.lattice_modulation(dl.planes(synthetic_raw(colours='G', blur=2.0))['G'], 30.0)
        blurred = dl.lattice_modulation(dl.planes(synthetic_raw(colours='G', blur=5.0))['G'], 30.0)
        self.assertGreater(sharp['modulation'], 1.5 * blurred['modulation'])
        # green light leaking into the blue plane has no power at the blue lattice period (p*sqrt(2))
        leaked = dl.lattice_modulation(dl.planes(synthetic_raw(colours='G', leak=0.5))['B'], 30.0 * np.sqrt(2))
        shown = dl.lattice_modulation(dl.planes(synthetic_raw(colours='B'))['B'], 30.0 * np.sqrt(2))
        self.assertLess(leaked['amplitude'], 0.1 * shown['amplitude'])
        self.assertIsNone(dl.lattice_modulation(dl.planes(synthetic_raw())['G'], 3.0))

    def test_focus_step_is_read_from_field_name_or_note(self):
        self.assertEqual(dl.focus_step({'field': 'z4 focus+2'}), 2.0)
        self.assertEqual(dl.focus_step({'field': 'z4', 'position_note': 'focus=-3 steps'}), -3.0)
        self.assertIsNone(dl.focus_step({'field': 'z4 white'}))


if __name__ == '__main__':
    unittest.main()
