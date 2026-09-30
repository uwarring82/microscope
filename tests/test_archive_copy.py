import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from tools import archive_copy as ac


def frame(root, name, content=b'\x10\x20\x30' * 100):
    """A capture: raw frame plus metadata recording its SHA-256, as the server writes them."""
    folder = root / 'sessions' / 'session-20260930-test'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{name}.raw').write_bytes(content)
    (folder / f'{name}.json').write_text(json.dumps({'sha256': hashlib.sha256(content).hexdigest()}))
    return folder / f'{name}.raw'


class ArchiveCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root, self.dest = base / 'repo', base / 'share'
        self.dest.mkdir()
        (self.dest / '0_README').write_text('archive')
        self.raw = frame(self.root, 'capture-a')
        record = self.root / 'artifacts' / 'captures' / 'series' / 'fields' / '01' / 'field.json'
        record.parent.mkdir(parents=True)
        record.write_text('{"records": []}')
        self.record = record
        (self.root / 'sessions' / '.DS_Store').write_bytes(b'x')
        (self.root / 'artifacts' / 'other.bin').write_bytes(b'not archived')
        self.out = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def later(self, path, text):
        path.write_text(text)
        stamp = time.time() + 10
        os.utime(path, (stamp, stamp))

    def test_first_run_copies_with_the_same_relative_paths_and_logs(self):
        counts = ac.run(self.root, self.dest, out=self.out)
        self.assertEqual(counts, {'copied': 3})
        for rel in ('sessions/session-20260930-test/capture-a.raw', 'artifacts/captures/series/fields/01/field.json'):
            self.assertEqual((self.dest / rel).read_bytes(), (self.root / rel).read_bytes())
        self.assertFalse((self.dest / 'sessions' / '.DS_Store').exists())
        self.assertFalse((self.dest / 'artifacts' / 'other.bin').exists())
        self.assertEqual(len(list((self.dest / '_copylog').glob('*.tsv'))), 1)
        self.assertEqual(ac.run(self.root, self.dest, out=self.out), {'unchanged': 3})

    def test_changed_record_is_versioned_not_overwritten(self):
        ac.run(self.root, self.dest, now=ac.datetime(2026, 9, 30, 7, 0, tzinfo=ac.timezone.utc), out=self.out)
        self.later(self.record, '{"records": [1]}')
        counts = ac.run(self.root, self.dest, now=ac.datetime(2026, 9, 30, 8, 0, tzinfo=ac.timezone.utc), out=self.out)
        self.assertEqual(counts['versioned'], 1)
        rel = 'artifacts/captures/series/fields/01/field.json'
        self.assertEqual((self.dest / rel).read_text(), '{"records": [1]}')
        self.assertEqual((self.dest / '_versions' / '2026_09_30_080000_utc' / rel).read_text(), '{"records": []}')

    def test_archived_frame_is_write_once(self):
        ac.run(self.root, self.dest, out=self.out)
        archived = (self.dest / 'sessions/session-20260930-test/capture-a.raw').read_bytes()
        replaced = frame(self.root, 'capture-a', content=b'\x99' * 300)  # a different frame under the same name
        stamp = time.time() + 10
        os.utime(replaced, (stamp, stamp))
        counts = ac.run(self.root, self.dest, out=self.out)
        self.assertEqual(counts.get('conflict'), 1)
        self.assertEqual((self.dest / 'sessions/session-20260930-test/capture-a.raw').read_bytes(), archived)

    def test_damaged_local_frame_is_not_copied(self):
        self.raw.write_bytes(b'\x00' * 300)  # no longer matches the SHA-256 in its metadata
        counts = ac.run(self.root, self.dest, out=self.out)
        self.assertEqual(counts.get('failed'), 1)
        self.assertFalse((self.dest / 'sessions/session-20260930-test/capture-a.raw').exists())

    def test_evicted_files_can_be_left_for_a_later_run(self):
        original = ac.evicted
        ac.evicted = lambda path: path.suffix == '.raw'  # as if the frame were still in iCloud
        try:
            counts = ac.run(self.root, self.dest, skip_evicted=True, out=self.out)
        finally:
            ac.evicted = original
        self.assertEqual(counts, {'copied': 2, 'evicted': 1})
        self.assertFalse((self.dest / 'sessions/session-20260930-test/capture-a.raw').exists())
        self.assertEqual(ac.run(self.root, self.dest, out=self.out), {'copied': 1, 'unchanged': 2})

    def test_dry_run_writes_nothing(self):
        counts = ac.run(self.root, self.dest, dry_run=True, out=self.out)
        self.assertEqual(counts, {'copied': 3})
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ['0_README'])

    def test_destination_without_readme_is_refused(self):
        os.remove(self.dest / '0_README')
        with self.assertRaises(SystemExit):
            ac.destination(str(self.dest))

    def test_audit_finds_damage_and_restore_round_trips(self):
        ac.run(self.root, self.dest, out=self.out)
        self.assertEqual(ac.audit(self.root, self.dest, out=self.out), {'ok': 3})
        rel = 'sessions/session-20260930-test/capture-a.raw'
        target = ac.restore(self.dest, rel, Path(self.tmp.name) / 'restored', out=self.out)
        self.assertEqual(target.read_bytes(), self.raw.read_bytes())
        original = ac.evicted
        ac.evicted = lambda path: path.suffix == '.raw'  # local frame in iCloud: checked against metadata only
        try:
            self.assertEqual(ac.audit(self.root, self.dest, out=self.out), {'ok': 2, 'ok-archive-only': 1})
        finally:
            ac.evicted = original
        (self.dest / rel).write_bytes(b'\x01' * 300)
        self.assertEqual(ac.audit(self.root, self.dest, out=self.out).get('damaged'), 1)


if __name__ == '__main__':
    unittest.main()
