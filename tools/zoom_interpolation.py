"""Offline zoom interpolation; no camera access or automatic profile creation.

Scale is in micrometres per image pixel. Zoom is the physical ring marking.
Intermediate settings are rough planning estimates until ring setting/return
and specimen-plane transfer are validated. This numerical model does not
establish mechanical repeatability or total accuracy, even at a measured node.
"""
import bisect
import math


def interpolate_scale(zoom, zooms, scales, method='reciprocal'):
    """Interpolate measured nodes without extrapolation.

    ``reciprocal`` linearly interpolates pixels/um against ring marking, then
    inverts. Other methods are sensitivity comparisons, not uncertainty bounds.
    """
    if len(zooms) != len(scales) or len(zooms) < 2:
        raise ValueError('At least two paired calibration nodes are required')
    if not all(math.isfinite(v) and v > 0 for v in [zoom, *zooms, *scales]):
        raise ValueError('Zoom and scales must be finite and positive')
    if any(a >= b for a, b in zip(zooms, zooms[1:])):
        raise ValueError('Zoom nodes must be strictly increasing')
    if method not in ('reciprocal', 'inverse_zoom', 'power', 'linear_scale'):
        raise ValueError('Unknown interpolation method')
    if not zooms[0] <= zoom <= zooms[-1]:
        raise ValueError('Extrapolation is not supported')
    i = bisect.bisect_left(zooms, zoom)
    if i < len(zooms) and zooms[i] == zoom:
        return float(scales[i])
    lo, hi = i - 1, i
    z0, z1 = zooms[lo], zooms[hi]
    s0, s1 = scales[lo], scales[hi]
    t = (zoom - z0) / (z1 - z0)
    if method == 'reciprocal':
        return 1 / ((1 - t) / s0 + t / s1)
    if method == 'inverse_zoom':
        t = (1 / zoom - 1 / z0) / (1 / z1 - 1 / z0)
    elif method == 'power':
        t = math.log(zoom / z0) / math.log(z1 / z0)
        return math.exp((1 - t) * math.log(s0) + t * math.log(s1))
    return (1 - t) * s0 + t * s1


def interior_cross_validation(zooms, scales, method='reciprocal'):
    """Withhold each interior node; endpoints are never extrapolated.

    The errors are sparse empirical diagnostics, not confidence intervals.
    """
    if len(zooms) < 3:
        raise ValueError('At least three nodes are required for an interior check')
    interpolate_scale(zooms[0], zooms, scales, method)
    errors = []
    for i in range(1, len(zooms) - 1):
        predicted = interpolate_scale(zooms[i], zooms[:i] + zooms[i+1:],
                                      scales[:i] + scales[i+1:], method)
        errors.append({'zoom': zooms[i], 'error_percent': 100 * (predicted / scales[i] - 1)})
    return {'errors': errors,
            'rms_percent': math.sqrt(sum(v['error_percent']**2 for v in errors) / len(errors)),
            'max_abs_percent': max(abs(v['error_percent']) for v in errors)}
