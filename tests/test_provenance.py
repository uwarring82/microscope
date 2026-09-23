from datetime import datetime
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import provenance


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git('init', '-q')
        for name in ('VERSION', 'changed.py', 'deleted.py', 'old name.py'):
            (self.root / name).write_text('0.0.0\n')
        (self.root / '.gitignore').write_text('ignored/\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic fixture')
        root_patch = patch.object(provenance, 'ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        provenance.build_info.cache_clear()
        self.addCleanup(provenance.build_info.cache_clear)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def test_paths_cover_staged_unstaged_deleted_renamed_and_untracked(self):
        (self.root / 'changed.py').write_text('edited\n')
        (self.root / 'deleted.py').unlink()
        self.git('mv', 'old name.py', 'new name.py')
        (self.root / 'staged.py').write_text('staged\n')
        self.git('add', 'staged.py')
        unusual = 'new dir/space\ttab\nµ.py'
        (self.root / 'new dir').mkdir()
        (self.root / unusual).write_text('untracked\n')
        (self.root / 'ignored').mkdir()
        (self.root / 'ignored/private.raw').write_bytes(b'private fixture')
        info = provenance.build_info()
        self.assertTrue(info['modified'])
        self.assertEqual(info['modified_paths'], sorted([
            'changed.py', 'deleted.py', 'old name.py', 'new name.py', 'staged.py', unusual]))
        self.assertEqual(json.loads(json.dumps(info)), info)
        self.assertEqual(info['commit'], self.git('rev-parse', 'HEAD').decode().strip())

    def test_clean_snapshot_is_explicitly_cached_at_first_use(self):
        info = provenance.build_info()
        self.assertFalse(info['modified'])
        self.assertEqual(info['modified_paths'], [])
        self.assertEqual(info['snapshot_scope'], 'process_first_use')
        self.assertIsNotNone(datetime.fromisoformat(info['snapshot_at']).utcoffset())
        (self.root / 'changed.py').write_text('later\n')
        self.assertEqual(provenance.build_info(), info)
        provenance.build_info.cache_clear()
        self.assertEqual(provenance.build_info()['modified_paths'], ['changed.py'])

    def test_git_failure_is_unknown_not_clean(self):
        with patch('provenance.subprocess.check_output', side_effect=FileNotFoundError):
            info = provenance.build_info()
        self.assertIsNone(info['commit'])
        self.assertIsNone(info['modified'])
        self.assertIsNone(info['modified_paths'])
        provenance.build_info.cache_clear()
        with patch('provenance.subprocess.check_output', side_effect=[
                'abc123\n', subprocess.TimeoutExpired('git status', 3)]):
            info = provenance.build_info()
        self.assertEqual(info['commit'], 'abc123')
        self.assertIsNone(info['modified'])
        self.assertIsNone(info['modified_paths'])

    def test_copy_and_incomplete_status_records(self):
        self.assertEqual(provenance._modified_paths(b'C  copy.py\0original.py\0'),
                         ['copy.py', 'original.py'])
        for status in (b' M truncated.py', b'R  missing-source.py\0', b'\0'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                provenance._modified_paths(status)


if __name__ == '__main__':
    unittest.main()
