"""Spatial calibration fit; uncertainty is fit precision, not total metrology error."""
import math


def fit_scale(samples):
    if not isinstance(samples, list) or not 3 <= len(samples) <= 100:
        raise ValueError('Use 3–100 stage-micrometer intervals for a calibration fit')
    for x, y in samples:
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (x, y)) or x < 1 or y <= 0:
            raise ValueError('Calibration intervals need at least 1 pixel and a positive known length')
    sum_xx = sum(x*x for x, _ in samples)
    scale = sum(x*y for x, y in samples) / sum_xx
    residuals = [y-scale*x for x, y in samples]
    variance = sum(r*r for r in residuals)/(len(samples)-1)
    return {'um_per_pixel': scale, 'fit_standard_error': math.sqrt(variance/sum_xx),
            'residuals_um': residuals, 'fit_method': 'least squares through origin',
            'uncertainty_note': '1 standard error of the fit only; excludes reference accuracy, distortion and positioning systematics'}


def validate_markers(markers, width, height):
    if not isinstance(markers, list) or len(markers) > 200:
        raise ValueError('At most 200 markers are supported')
    result, ids = [], set()
    for marker in markers:
        if not isinstance(marker, dict) or marker.get('type') not in ('line', 'rectangle', 'circle', 'point'):
            raise ValueError('Unknown marker type')
        identifier = marker.get('id')
        if not isinstance(identifier, str) or not identifier or len(identifier) > 80 or identifier in ids:
            raise ValueError('Marker IDs must be unique, nonempty strings')
        ids.add(identifier)
        label = marker.get('label', '')
        if not isinstance(label, str) or len(label) > 120:
            raise ValueError('Marker labels are limited to 120 characters')
        clean = {'id': identifier, 'type': marker['type'], 'label': label}
        for name in ('a', 'b'):
            point = marker.get(name)
            if not isinstance(point, dict) or set(point) != {'x', 'y'}:
                raise ValueError('Marker endpoints require x and y')
            x, y = point['x'], point['y']
            if not all(type(v) in (int, float) and math.isfinite(v) for v in (x, y)) or not (0 <= x < width and 0 <= y < height):
                raise ValueError('Marker coordinates must lie inside the captured image')
            clean[name] = {'x': x, 'y': y}
        result.append(clean)
    return result
