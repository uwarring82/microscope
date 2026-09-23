import math
import unittest

from tools.zoom_interpolation import interpolate_scale, interior_cross_validation


class ZoomInterpolationTests(unittest.TestCase):
    def test_reciprocal_model_recovers_linear_magnification(self):
        zooms = [2, 3, 4, 5, 6, 7]
        scales = [1 / (0.03 + 0.22 * z) for z in zooms]
        for z in [2, 2.5, 3.5, 6.5, 7]:
            self.assertAlmostEqual(interpolate_scale(z, zooms, scales), 1 / (0.03 + 0.22 * z))
        result = interior_cross_validation(zooms, scales)
        self.assertEqual([v['zoom'] for v in result['errors']], [3, 4, 5, 6])
        self.assertLess(result['max_abs_percent'], 1e-10)

    def test_alternatives_and_error_sign(self):
        self.assertAlmostEqual(interpolate_scale(3, [2, 4], [2, 1], 'inverse_zoom'), 4 / 3)
        self.assertAlmostEqual(interpolate_scale(3, [2, 4], [2, 1], 'power'), 4 / 3)
        self.assertEqual(interpolate_scale(3, [2, 4], [2, 1], 'linear_scale'), 1.5)
        check = interior_cross_validation([2, 3, 4], [2, 1, 1])
        self.assertAlmostEqual(check['errors'][0]['error_percent'], 100 / 3)

    def test_rejects_extrapolation_and_ambiguous_nodes(self):
        for z, zs, ss in [(1, [2, 4], [2, 1]), (5, [2, 4], [2, 1]),
                          (2, [2, 2], [2, 1]), (2, [4, 2], [1, 2]),
                          (2, [2, 4], [2]), (2, [2, 4], [2, 0]),
                          (math.nan, [2, 4], [2, 1])]:
            with self.subTest(zoom=z, nodes=zs, scales=ss), self.assertRaises(ValueError):
                interpolate_scale(z, zs, ss)


if __name__ == '__main__':
    unittest.main()
