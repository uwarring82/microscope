"""Camera-independent relative scale checks from corresponding 2-D landmarks.

The fit uses only pixel coordinates. Calibration scales enter the subsequent
comparison, never the fitted geometry. Shared biases and absolute scale remain
unidentified, and a disagreement does not identify its physical cause.
"""
import math
from itertools import combinations


def fit_similarity(source, target):
    """Fit target = a * source + b in complex coordinates, with free rotation.

    Equal landmark weights; no reflection or scale prior. Residuals are pixel
    diagnostics, not confidence intervals (both coordinate sets have errors).
    """
    if len(source) != len(target) or len(source) < 3:
        raise ValueError('At least three corresponding landmarks are required')
    points = []
    for group in (source, target):
        if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in group):
            raise ValueError('Landmarks must be finite 2-D coordinates')
        points.append([complex(*p) for p in group])
    x, y = points
    mx, my = sum(x)/len(x), sum(y)/len(y)
    variance = sum(abs(v-mx)**2 for v in x)
    if variance == 0:
        raise ValueError('Source landmarks must have a nonzero baseline')
    a = sum((u-mx).conjugate()*(v-my) for u, v in zip(x, y))/variance
    if abs(a) == 0:
        raise ValueError('Target landmarks must span a nonzero scale')
    b = my-a*mx
    residuals = [abs(a*u+b-v) for u, v in zip(x, y)]
    return {'pixel_ratio': abs(a), 'rotation_degrees': math.degrees(math.atan2(a.imag, a.real)),
            'a_real': a.real, 'a_imag': a.imag, 'translation_x': b.real, 'translation_y': b.imag,
            'residuals_target_pixels': residuals,
            'rms_target_pixels': math.sqrt(sum(v*v for v in residuals)/len(residuals))}


def pair_ratios(source, target, min_source_distance=0):
    """Return all eligible separation ratios; shared endpoints are correlated."""
    fit_similarity(source, target)  # Validate paired coordinates and nonzero scale.
    if not math.isfinite(min_source_distance) or min_source_distance < 0:
        raise ValueError('Minimum baseline must be finite and nonnegative')
    result = []
    for i, j in combinations(range(len(source)), 2):
        ds = math.dist(source[i], source[j]);dt = math.dist(target[i], target[j])
        if ds > 0 and ds >= min_source_distance:
            result.append({'i': i, 'j': j, 'source_pixels': ds, 'target_pixels': dt, 'pixel_ratio': dt/ds})
    return result
