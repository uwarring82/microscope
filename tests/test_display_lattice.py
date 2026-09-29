import unittest

try:  # analysis-only dependencies; the runtime and CI need only the standard library
    import numpy as np
    from scipy import ndimage
    from tools import display_lattice as dl
except ImportError:  # pragma: no cover
    np = None


def synthetic_raw(width=1280, height=960, pitch_px=30.0, angle_deg=4.0, red_magnification=1.0, colours='RGB'):
    """RGGB mosaic of a diamond OLED lattice: green pitch p, red/blue on p*sqrt(2); red optionally magnified."""
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
        img = ndimage.gaussian_filter(img, 3.0) * 2000
        for dy, dx in phase[c]:
            raw[dy::2, dx::2] += img[dy::2, dx::2]
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

    def test_focus_step_is_read_from_field_name_or_note(self):
        self.assertEqual(dl.focus_step({'field': 'z4 focus+2'}), 2.0)
        self.assertEqual(dl.focus_step({'field': 'z4', 'position_note': 'focus=-3 steps'}), -3.0)
        self.assertIsNone(dl.focus_step({'field': 'z4 white'}))


if __name__ == '__main__':
    unittest.main()
