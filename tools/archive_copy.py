"""Copy the microscope's local data one way to an archive folder (the group file share), with verification.

  python3 -m tools.archive_copy run [--dest DIR] [--dry-run] [--skip-evicted]   # copy new and changed files, verify, log
  python3 -m tools.archive_copy audit [--dest DIR]             # read back every archived file and compare
  python3 -m tools.archive_copy restore PATH --to DIR [--version RUN] [--dest DIR]   # copy one file back

sessions/ and artifacts/captures/ are copied under the same relative paths, so field records still find their
frames and a restore is a plain copy back. Rules (agreed 2026-09-30, see docs/logbook.md):
  * raw frames (*.raw) are write-once: an archived frame is never overwritten. If it differs from the local
    frame, the run reports a conflict and leaves both as they are; a local frame that no longer matches the
    SHA-256 in its capture metadata is not copied;
  * other files are versioned: before a changed file is replaced, the archived version moves to
    _versions/<run>/<same path>;
  * nothing is deleted. Every file written is read back and compared by SHA-256 (frames also against their
    capture metadata), and each run writes _copylog/<run>.tsv. Run names are UTC.
Routine runs treat a file with the same size and modification time as unchanged (as rsync does); the monthly
audit reads everything back and catches what that check cannot.
The destination is local configuration, not part of the repository: --dest, MICROSCOPE_ARCHIVE_DEST, or
~/.config/microscope-archive/config.json {"destination": "..."}. It must already contain a 0_README, so an
unmounted share is never mistaken for an empty folder.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ('sessions', 'artifacts/captures')
CONFIG = Path.home() / '.config' / 'microscope-archive' / 'config.json'
SKIP_NAMES = {'.DS_Store', '__pycache__'}
SKIP_SUFFIXES = ('.pyc', '.partial')
SF_DATALESS = 0x40000000  # macOS: content evicted to iCloud; reading it downloads it first


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def destination(arg=None):
    value = arg or os.environ.get('MICROSCOPE_ARCHIVE_DEST')
    if not value and CONFIG.exists():
        value = json.loads(CONFIG.read_text()).get('destination')
    if not value:
        raise SystemExit('No archive destination: use --dest, MICROSCOPE_ARCHIVE_DEST or ' + str(CONFIG))
    dest = Path(value).expanduser()
    if not (dest / '0_README').is_file():
        raise SystemExit(f'{dest} has no 0_README: not an archive folder, or the share is not mounted')
    return dest


def evicted(path):
    """True if macOS has evicted the file's content to iCloud (reading it would first download it)."""
    return bool(getattr(os.stat(path), 'st_flags', 0) & SF_DATALESS)


def local_files(root):
    for source in SOURCES:
        base = root / source
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*')):
            rel = path.relative_to(root)
            if any(part in SKIP_NAMES or part.startswith('._') for part in rel.parts) or path.name.endswith(SKIP_SUFFIXES):
                continue
            if path.is_file() and not path.is_symlink():
                yield rel


def recorded_sha(raw_path):
    """SHA-256 of a raw frame as recorded in its capture metadata (same name, .json), or None."""
    meta = raw_path.with_suffix('.json')
    try:
        return json.loads(meta.read_text()).get('sha256')
    except (OSError, ValueError):
        return None


def same_quick(a, b):
    sa, sb = a.stat(), b.stat()
    return sa.st_size == sb.st_size and abs(sa.st_mtime - sb.st_mtime) < 2


def copy_verified(src, dst, expected):
    """Copy through a .partial file, read it back, and rename only if the SHA-256 matches."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + '.partial')
    shutil.copyfile(src, tmp)
    stat = src.stat()
    os.utime(tmp, (stat.st_atime, stat.st_mtime))
    if sha256(tmp) != expected:
        tmp.unlink()
        return False
    os.replace(tmp, dst)
    return True


def run_name(now=None):
    return (now or datetime.now(timezone.utc)).strftime('%Y_%m_%d_%H%M%S_utc')


def run(root, dest, dry_run=False, skip_evicted=False, now=None, out=sys.stdout):
    """Copy new and changed files. Returns counts per action; 'conflict' and 'failed' need attention.
    With skip_evicted, files whose content is still in iCloud are left for a later run ('evicted')."""
    name = run_name(now)
    counts, log = {}, []
    dataless = 0
    for rel in local_files(root):
        src, dst = root / rel, dest / rel
        if dst.exists() and same_quick(src, dst):  # needs only the file sizes and times, not the content
            counts['unchanged'] = counts.get('unchanged', 0) + 1
            continue
        if evicted(src):
            if skip_evicted:
                counts['evicted'] = counts.get('evicted', 0) + 1
                log.append(('evicted', rel.as_posix(), str(src.stat().st_size), '', 'content still in iCloud; left for a later run'))
                continue
            dataless += 1
        raw = rel.suffix == '.raw'
        action, note, digest = None, '', ''
        if dst.exists() and same_quick(src, dst):
            action = 'unchanged'
        else:
            digest = sha256(src)
            expected_raw = recorded_sha(src) if raw else None
            if raw and expected_raw and digest != expected_raw:
                action, note = 'failed', 'local frame does not match its capture metadata; not copied'
            elif dst.exists():
                if sha256(dst) == digest:
                    action = 'unchanged'
                elif raw:
                    action, note = 'conflict', 'archived frame differs; write-once, left as is'
                else:
                    action = 'versioned'
            else:
                action = 'copied'
            if action in ('copied', 'versioned') and not dry_run:
                if action == 'versioned':
                    previous = dest / '_versions' / name / rel
                    previous.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(dst, previous)
                    note = f'previous version in _versions/{name}/'
                if not copy_verified(src, dst, digest):
                    action, note = 'failed', 'read-back SHA-256 differs; not renamed into place'
        counts[action] = counts.get(action, 0) + 1
        if action != 'unchanged':
            log.append((action, rel.as_posix(), str(src.stat().st_size), digest, note))
    if dataless:
        print(f'note: {dataless} local files were evicted to iCloud and had to be downloaded', file=out)
    if not dry_run and log:
        (dest / '_copylog').mkdir(exist_ok=True)
        with open(dest / '_copylog' / f'{name}.tsv', 'w') as handle:
            handle.write(f'# archive_copy run {name}; counts {json.dumps(counts, sort_keys=True)}\n')
            handle.write('action\tpath\tbytes\tsha256\tnote\n')
            handle.writelines('\t'.join(row) + '\n' for row in log)
    for row in log:
        if row[0] in ('conflict', 'failed'):
            print(f'{row[0]}: {row[1]} ({row[4]})', file=out)
    print(('dry run: ' if dry_run else f'run {name}: ') + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())), file=out)
    return counts


def audit(root, dest, now=None, out=sys.stdout):
    """Read back every archived file (outside _versions and _copylog) and compare with the local copy and,
    for frames, with the capture metadata. A local copy evicted to iCloud is not read: frames are then checked
    against their metadata only. Returns counts; 'mismatch' and 'damaged' need attention."""
    name = run_name(now)
    counts, log = {}, []
    archived = set()
    for source in SOURCES:
        base = dest / source
        if base.is_dir():
            archived.update(p.relative_to(dest) for p in base.rglob('*') if p.is_file() and not p.name.endswith('.partial')
                            and not any(part.startswith('._') or part == '.DS_Store' for part in p.relative_to(dest).parts))
    local = set(local_files(root))
    for rel in sorted(archived | local):
        a, l = dest / rel, root / rel
        if rel not in archived:
            action, note = 'not-archived', ''
        elif rel not in local:
            action, note = 'archive-only', 'no local copy (kept; nothing is deleted)'
        else:
            da = sha256(a)
            expected = recorded_sha(a) if rel.suffix == '.raw' else None
            if expected and da != expected:
                action, note = 'damaged', 'archived frame does not match its capture metadata'
            elif evicted(l):
                # the local copy is in iCloud; reading it would wait for a download
                action, note = 'ok-archive-only' if expected else 'not-compared', 'local copy evicted to iCloud'
            elif da != sha256(l):
                action, note = 'mismatch', 'archived and local files differ'
            else:
                action, note = 'ok', ''
        counts[action] = counts.get(action, 0) + 1
        if action != 'ok':
            log.append((action, rel.as_posix(), note))
    (dest / '_copylog').mkdir(exist_ok=True)
    with open(dest / '_copylog' / f'{name}-audit.tsv', 'w') as handle:
        handle.write(f'# archive_copy audit {name}; counts {json.dumps(counts, sort_keys=True)}\n')
        handle.write('result\tpath\tnote\n')
        handle.writelines('\t'.join(row) + '\n' for row in log)
    print(f'audit {name}: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())), file=out)
    return counts


def restore(dest, rel, target_dir, version=None, out=sys.stdout):
    """Copy one archived file (or an earlier version) to target_dir and verify the copy."""
    source = (dest / '_versions' / version / rel) if version else (dest / rel)
    if not source.is_file():
        raise SystemExit(f'not in the archive: {source}')
    target = Path(target_dir) / Path(rel).name
    digest = sha256(source)
    if not copy_verified(source, target, digest):
        raise SystemExit('restore failed: the copy does not match the archived file')
    expected = recorded_sha(source) if Path(rel).suffix == '.raw' else None
    status = 'matches its capture metadata' if expected == digest else ('DOES NOT match its capture metadata' if expected else 'verified')
    print(f'restored {rel} → {target} (SHA-256 {digest[:16]}…, {status})', file=out)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dest', help='archive folder (overrides the environment and config file)')
    commands = parser.add_subparsers(dest='command', required=True)
    run_parser = commands.add_parser('run')
    run_parser.add_argument('--dry-run', action='store_true')
    run_parser.add_argument('--skip-evicted', action='store_true', help='leave files evicted to iCloud for a later run')
    commands.add_parser('audit')
    restore_parser = commands.add_parser('restore')
    restore_parser.add_argument('path', help='path relative to the repository, e.g. sessions/<session>/<capture>.raw')
    restore_parser.add_argument('--to', required=True)
    restore_parser.add_argument('--version', help='run name under _versions/')
    args = parser.parse_args(argv)
    dest = destination(args.dest)
    if args.command == 'run':
        counts = run(ROOT, dest, dry_run=args.dry_run, skip_evicted=args.skip_evicted)
        return 2 if counts.get('conflict') or counts.get('failed') else 0
    if args.command == 'audit':
        counts = audit(ROOT, dest)
        return 2 if counts.get('mismatch') or counts.get('damaged') else 0
    restore(dest, args.path, args.to, args.version)
    return 0


if __name__ == '__main__':
    sys.exit(main())
