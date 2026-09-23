"""Machine-readable build provenance, evaluated once per server process."""
from functools import lru_cache
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPOSITORY = 'https://github.com/uwarring82/microscope'


@lru_cache(maxsize=1)
def build_info():
    info = {'name': 'Di-Li microscope workspace', 'version': (ROOT/'VERSION').read_text().strip(),
            'repository': REPOSITORY, 'license': 'MIT'}
    try:
        info['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True, timeout=3).strip()
        info['modified'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True, timeout=3).strip())
    except (OSError, subprocess.SubprocessError):
        info['commit'], info['modified'] = None, None
    return info
