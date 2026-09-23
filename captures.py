"""Durable inspection sessions using the existing raw replay dataset format."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import threading
import uuid

from calibration import fit_scale, validate_markers
from dili import CameraError, Frame
from fits_export import fits_bytes


def now():
    return datetime.now(timezone.utc).isoformat()


def text_field(data, name, limit=120):
    value = data.get(name, '')
    if not isinstance(value, str) or len(value) > limit or '\0' in value:
        raise ValueError(f'{name} must be text of at most {limit} characters')
    return value.strip()


def atomic_bytes(path, payload):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, data):
    atomic_bytes(path, (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode())


class CaptureStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _folder(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r'session-[a-zA-Z0-9-]{1,60}', session_id):
            raise ValueError('Invalid session ID')
        folder = self.root / session_id
        if folder.resolve().parent != self.root:
            raise ValueError('Invalid session path')
        return folder

    def _base(self, session_id, capture_id):
        if not isinstance(capture_id, str) or not re.fullmatch(r'capture-[a-f0-9]{32}', capture_id):
            raise ValueError('Invalid capture ID')
        return self._folder(session_id) / capture_id

    def profiles(self):
        with self.lock:
            path = self.root / 'calibrations.json'
            return json.loads(path.read_text()) if path.exists() else []

    def _inspection(self, data, metadata, revision):
        objective = text_field(data, 'objective')
        configuration = text_field(data, 'optical_configuration')
        profile_id = data.get('calibration_id')
        profile = None
        if profile_id:
            profile = next((p for p in self.profiles() if p['id'] == profile_id), None)
            if profile is None or (profile['objective'], profile['optical_configuration'], profile['resolution']) != (objective, configuration, metadata['resolution']):
                raise ValueError('Calibration does not match the selected objective, optical configuration and resolution')
        return {'revision': revision, 'updated_at': now(), 'sample_id': text_field(data, 'sample_id'),
                'notes': text_field(data, 'notes', 10000), 'objective': objective,
                'optical_configuration': configuration, 'calibration': deepcopy(profile),
                'markers': validate_markers(data.get('markers', []), metadata['width'], metadata['height'])}

    def capture(self, frame, metadata, data):
        with self.lock:
            inspection = self._inspection(data, metadata, 1)
            session_id = data.get('session_id')
            if session_id:
                folder = self._folder(session_id)
                manifest = json.loads((folder/'manifest.json').read_text())
            else:
                session_id = 'session-' + datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:12]
                folder = self._folder(session_id)
                manifest = {'format': 'dili-raw-dataset-v1', 'session_id': session_id,
                            '$schema': 'https://raw.githubusercontent.com/uwarring82/microscope/v0.2.0/schemas/dili-raw-dataset-v1.schema.json',
                            'identifier': 'urn:uuid:' + str(uuid.uuid4()),
                            'data_license': 'unspecified; software license does not license specimen data',
                            'name': text_field(data, 'session_name') or 'Lab inspection', 'created_at': now(),
                            'description': 'Saved microscope inspection captures',
                            'white_balance_gains': metadata['white_balance_gains'],
                            'default_resolution': metadata['resolution'], 'frames': []}
                folder.mkdir()
            capture_id = 'capture-' + uuid.uuid4().hex
            base = self._base(session_id, capture_id)
            metadata = deepcopy(metadata)
            metadata.update(session_id=session_id, capture_id=capture_id, saved_at=now(), file=base.name+'.raw')
            png = frame.png(metadata['display_mode'], metadata['white_balance_gains'])
            atomic_bytes(base.with_suffix('.raw'), frame.pixels)
            write_json(base.with_suffix('.json'), metadata)
            write_json(base.with_suffix('.annotations.json'), inspection)
            atomic_bytes(base.with_suffix('.png'), png)
            manifest['frames'].append({**metadata, 'annotation_file': base.name+'.annotations.json'})
            write_json(folder/'manifest.json', manifest)  # Commit point after all frame files exist.
            return self.get(session_id, capture_id)

    def get(self, session_id, capture_id):
        with self.lock:
            base = self._base(session_id, capture_id)
            manifest = json.loads((base.parent/'manifest.json').read_text())
            if not any(row.get('capture_id') == capture_id for row in manifest['frames']):
                raise FileNotFoundError('Capture is not committed in this session')
            return {'metadata': json.loads(base.with_suffix('.json').read_text()),
                    'inspection': json.loads(base.with_suffix('.annotations.json').read_text()),
                    'image_url': f'/api/sessions/{session_id}/{capture_id}/image.png',
                    'directory': str(base.parent), 'session_name': manifest['name']}

    def update(self, session_id, capture_id, data):
        with self.lock:
            record = self.get(session_id, capture_id)
            if data.get('revision') != record['inspection']['revision']:
                raise CameraError('This capture was edited elsewhere. Reopen it before saving changes.')
            inspection = self._inspection(data, record['metadata'], record['inspection']['revision']+1)
            write_json(self._base(session_id, capture_id).with_suffix('.annotations.json'), inspection)
            return self.get(session_id, capture_id)

    def list_sessions(self):
        with self.lock:
            result = []
            for path in sorted(self.root.glob('session-*/manifest.json'), reverse=True):
                manifest = json.loads(path.read_text())
                captures = []
                for row in reversed(manifest['frames']):
                    annotation = json.loads((path.parent/row['annotation_file']).read_text())
                    captures.append({'id': row['capture_id'], 'captured_at': row['captured_at'],
                                     'resolution': row['resolution'], 'source_type': row['source_type'],
                                     'sample_id': annotation['sample_id']})
                result.append({'id': manifest['session_id'], 'name': manifest['name'], 'captures': captures})
            return result

    def create_profile(self, data):
        with self.lock:
            name, objective, configuration = (text_field(data, key) for key in ('name', 'objective', 'optical_configuration'))
            if not all((name, objective, configuration)):
                raise ValueError('Name, objective and optical configuration are required')
            references = data.get('references')
            if not isinstance(references, list) or not 3 <= len(references) <= 100:
                raise ValueError('Measure at least three stage-micrometer intervals')
            samples, saved_references = [], []
            resolution = None
            for reference in references:
                record = self.get(reference['session_id'], reference['capture_id'])
                meta = record['metadata']
                if resolution is not None and meta['resolution'] != resolution:
                    raise ValueError('All calibration references must have the same resolution')
                resolution = meta['resolution']
                marker = validate_markers([{'id': 'ref', 'type': 'line', 'label': '', 'a': reference['a'], 'b': reference['b']}], meta['width'], meta['height'])[0]
                length = math.hypot(marker['b']['x']-marker['a']['x'], marker['b']['y']-marker['a']['y'])
                samples.append((length, reference['known_um']))
                saved_references.append({**marker, 'known_um': reference['known_um'], 'pixel_length': length,
                                         'session_id': meta['session_id'], 'capture_id': meta['capture_id'], 'sha256': meta['sha256']})
            profile = {'id': uuid.uuid4().hex, 'name': name, 'objective': objective,
                       'optical_configuration': configuration, 'resolution': resolution, 'created_at': now(),
                       'references': saved_references, **fit_scale(samples)}
            profiles = self.profiles()
            profiles.append(profile)
            write_json(self.root/'calibrations.json', profiles)
            return profile

    def _raw(self, record):
        metadata = record['metadata']
        raw = self._base(metadata['session_id'], metadata['capture_id']).with_suffix('.raw').read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata['sha256']:
            raise CameraError('Saved raw checksum mismatch; export refused')
        return Frame(raw, metadata['captured_at'], metadata['width'], metadata['height'])

    def _export_path(self, record, kind):
        metadata, inspection = record['metadata'], record['inspection']
        return self._base(metadata['session_id'], metadata['capture_id']).with_name(f"{metadata['capture_id']}-r{inspection['revision']}-{kind}")

    def export_fits(self, session_id, capture_id):
        with self.lock:
            record = self.get(session_id, capture_id)
            path = self._export_path(record, 'raw.fits')
            atomic_bytes(path, fits_bytes(self._raw(record), record['metadata'], record['inspection']))
            return {'path': str(path), 'url': f'/api/sessions/{session_id}/{capture_id}/raw.fits'}

    def save_png(self, session_id, capture_id, data):
        with self.lock:
            record = self.get(session_id, capture_id)
            if data.get('revision') != record['inspection']['revision']:
                raise CameraError('Annotations changed during export; export again')
            kind = data.get('kind')
            if kind not in ('image-only.png', 'annotated.png', 'inspection.png'):
                raise ValueError('Unknown PNG export kind')
            try:
                png = base64.b64decode(data['png'], validate=True)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError('Expected base64 PNG data') from error
            if len(png) < 33 or len(png) > 24*1024*1024 or png[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
                raise ValueError('Invalid PNG export')
            width, height = struct.unpack_from('>II', png, 16)
            if not 1 <= width <= 12000 or not 1 <= height <= 12000:
                raise ValueError('PNG dimensions exceed export limits')
            metadata = record['metadata']
            if kind != 'inspection.png' and (width, height) != (metadata['width'], metadata['height']):
                raise ValueError('Image exports must retain captured dimensions')
            path = self._export_path(record, kind)
            atomic_bytes(path, png)
            write_json(path.with_suffix('.json'), {'metadata': metadata, 'inspection': record['inspection'], 'exported_at': now(), 'kind': kind})
            return {'path': str(path), 'url': f'/api/sessions/{session_id}/{capture_id}/{kind}'}

    def asset(self, session_id, capture_id, kind):
        with self.lock:
            record = self.get(session_id, capture_id)
            base = self._base(session_id, capture_id)
            if kind == 'image.png':
                return base.with_suffix('.png').read_bytes(), 'image/png'
            if kind == 'annotations.json':
                return base.with_suffix('.annotations.json').read_bytes(), 'application/json'
            if kind in ('raw.fits', 'image-only.png', 'annotated.png', 'inspection.png'):
                return self._export_path(record, kind).read_bytes(), 'application/fits' if kind.endswith('.fits') else 'image/png'
            raise FileNotFoundError('Unknown capture asset')
