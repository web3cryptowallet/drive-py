"""Directory copy CLI: Git ignore rules, safe merges and symlinks."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'copy-dir.py'


@unittest.skipUnless(SCRIPT.exists(), 'Python copier is no longer present')
class CopyDirectoryTests(unittest.TestCase):
    def test_copy_contents_with_nested_ignore_rules_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source dir', root / 'output dir'
            source.mkdir()
            destination.mkdir()
            (source / '.gitignore').write_text('*.tmp\n/root-only\nignored/\n')
            (source / '.git').mkdir()
            (source / '.git' / 'private').write_text('metadata')
            (source / 'ignored').mkdir()
            (source / 'ignored' / 'secret').write_text('ignored')
            (source / 'root-only').write_text('ignored')
            (source / 'bad.tmp').write_text('ignored')
            (source / '.hidden').write_text('hidden')
            (source / 'name with\nnewline.txt').write_text('newlines work')
            (source / 'nested').mkdir()
            (source / 'nested' / '.gitignore').write_text('!keep.tmp\n')
            (source / 'nested' / 'keep.tmp').write_text('kept')
            (source / 'nested' / 'bad.tmp').write_text('ignored')
            (source / 'nested' / 'root-only').write_text('kept')
            (source / 'link').symlink_to('nested/keep.tmp')
            (source / 'empty').mkdir()
            (destination / '.hidden').write_text('old')
            (destination / 'existing').write_text('retained')
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(destination)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for relative in ['.git', 'ignored', 'root-only', 'bad.tmp', 'nested/bad.tmp']:
                self.assertFalse((destination / relative).exists(), relative)
            for relative in ['.gitignore', '.hidden', 'name with\nnewline.txt',
                             'nested/.gitignore', 'nested/keep.tmp', 'nested/root-only']:
                self.assertEqual((destination / relative).read_bytes(), (source / relative).read_bytes())
            self.assertEqual((destination / 'existing').read_text(), 'retained')
            self.assertTrue((destination / 'empty').is_dir())
            self.assertTrue((destination / 'link').is_symlink())
            self.assertEqual((destination / 'link').readlink(), Path('nested/keep.tmp'))

    def test_reject_overlap_and_destination_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source', root / 'destination'
            source.mkdir()
            (source / 'file').write_text('new')
            for target in [source, source / 'child', root]:
                result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(target)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('must not overlap', result.stderr)
            destination.mkdir()
            outside = root / 'outside'
            outside.write_text('unchanged')
            (destination / 'file').symlink_to(outside)
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(destination)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(outside.read_text(), 'unchanged')


class ShellCopyDirectoryTests(unittest.TestCase):
    def test_rsync_ignore_lists_and_plan(self):
        import shutil
        if not shutil.which('rsync'):
            self.skipTest('rsync unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, destination = root / 'source dir', root / 'destination dir'
            source.mkdir()
            (source / '.gitignore').write_text('*.tmp\nignored/\n.cache/\n.venv/\ntexual.removed/\n')
            for excluded in ['.cache', '.venv', 'texual.removed']:
                (source / excluded).mkdir()
                (source / excluded / 'excluded.txt').write_text('excluded')
            (source / 'keep.txt').write_text('keep')
            (source / 'drop.tmp').write_text('ignored')
            (source / 'ignored').mkdir()
            (source / 'ignored' / 'secret').write_text('ignored')
            (source / '.git').mkdir()
            (source / '.git' / 'metadata').write_text('ignored')
            (source / 'nested').mkdir()
            (source / 'nested' / '.gitignore').write_text('private.txt\n')
            (source / 'nested' / 'private.txt').write_text('ignored')
            (source / 'nested' / 'public.txt').write_text('public')
            (source / 'link').symlink_to('keep.txt')
            destination.mkdir()
            (destination / 'unrelated').write_text('retained')
            result = subprocess.run([str(SCRIPT.with_suffix('.sh')), str(source), str(destination)],
                                    cwd=source, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((destination / 'keep.txt').read_text(), 'keep')
            self.assertEqual((destination / 'nested' / 'public.txt').read_text(), 'public')
            self.assertEqual((destination / 'unrelated').read_text(), 'retained')
            self.assertTrue((destination / 'link').is_symlink())
            for name in ['drop.tmp', 'ignored', '.git', '.cache', '.venv', 'texual.removed',
                         'nested/private.txt', 'files_dst.copy']:
                self.assertFalse((destination / name).exists(), name)
            plan = (source / 'files_dst.copy').read_text()
            self.assertIn('keep.txt', plan)
            self.assertIn('nested/public.txt', plan)
            self.assertNotIn('private.txt', plan)
            self.assertNotIn('drop.tmp', plan)
            result = subprocess.run([str(SCRIPT.with_suffix('.sh')), str(source), str(source / 'child')],
                                    cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
