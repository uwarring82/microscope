"""Repository-state snapshot, cached at first use in each server process.

This identifies a disk state, not an attestation of loaded modules or binaries.
Restart after source changes. Ignored data and generated binaries are excluded.
"""
from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPOSITORY = 'https://github.com/uwarring82/microscope'


def _modified_paths(status):
    """Decode porcelain v1 -z, retaining both paths of renames/copies."""
    if not status:
        return []
    if not status.endswith(b'\0'):
        raise ValueError('Incomplete Git status')
    records = iter(status[:-1].split(b'\0'))
    paths = set()
    for record in records:
        if len(record) < 4 or record[2:3] != b' ':
            raise ValueError('Invalid Git status record')
        paths.add(os.fsdecode(record[3:]))
        if b'R' in record[:2] or b'C' in record[:2]:
            original = next(records, None)
            if not original:
                raise ValueError('Missing original Git path')
            paths.add(os.fsdecode(original))
    return sorted(paths)


@lru_cache(maxsize=1)
def build_info():
    info = {'name': 'Di-Li microscope workspace', 'version': (ROOT/'VERSION').read_text().strip(),
            'repository': REPOSITORY, 'license': 'MIT',
            'snapshot_at': datetime.now(timezone.utc).isoformat(),
            'snapshot_scope': 'process_first_use',
            'commit': None, 'modified': None, 'modified_paths': None}
    try:
        info['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True, timeout=3).strip()
        status = subprocess.check_output(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignore-submodules=none'],
                                         cwd=ROOT, stderr=subprocess.DEVNULL, timeout=3)
        info['modified_paths'] = _modified_paths(status)
        info['modified'] = bool(info['modified_paths'])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass  # Unknown is distinct from a verified clean working tree.
    return info
