import math
import unittest
from tools.relative_scale import fit_similarity, pair_ratios


class RelativeScaleTests(unittest.TestCase):
    def test_free_scale_rotation_and_translation(self):
        source = [(2, 3), (95, 14), (31, 120), (-30, 43)]
        a = 1.83 * complex(math.cos(.15), math.sin(.15));b = complex(-700, 390)
        target = [(v.real, v.imag) for v in (a*complex(*p)+b for p in source)]
        fit = fit_similarity(source, target)
        self.assertAlmostEqual(fit['pixel_ratio'], 1.83)
        self.assertAlmostEqual(fit['rotation_degrees'], math.degrees(.15))
        self.assertLess(fit['rms_target_pixels'], 1e-12)
        for pair in pair_ratios(source, target, 50):
            self.assertAlmostEqual(pair['pixel_ratio'], 1.83)

    def test_coordinate_disturbance_is_visible(self):
        source = [(0, 0), (100, 0), (0, 100), (100, 100)]
        target = [(0, 0), (200, 0), (0, 200), (210, 200)]
        fit = fit_similarity(source, target)
        self.assertGreater(fit['rms_target_pixels'], 2)
        self.assertGreater(max(p['pixel_ratio'] for p in pair_ratios(source, target)), 2.05)

    def test_rejects_invalid_and_degenerate_data(self):
        for x, y in [([(0, 0)]*3, [(1, 1)]*3), ([(0, 0)]*2, [(0, 0)]*2),
                     ([(0, 0), (1, 0), (0, math.nan)], [(0, 0), (1, 0), (0, 1)])]:
            with self.assertRaises(ValueError):
                fit_similarity(x, y)


if __name__ == '__main__':
    unittest.main()
