"""F4 reports local database bytes and volume capacity without catalog queries."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from vfs.storage_status import storage_status


class StorageStatusTests(unittest.TestCase):
    def test_databases_sidecars_and_shared_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main, fragment = root / 'catalog', root / 'fragment'
            main.write_bytes(b'x' * 1024)
            fragment.write_bytes(b'x' * 2048)
            Path(str(main) + '-wal').write_bytes(b'x' * 1024)
            usage = SimpleNamespace(total=8192, used=5120, free=3072)
            with patch('vfs.storage_status.shutil.disk_usage', return_value=usage) as probe:
                text = '\n'.join(storage_status([str(main), str(fragment), str(main)], str(root)))
            self.assertIn(str(main), text)
            self.assertIn(str(fragment), text)
            self.assertIn('File 1 KB · sidecars 1 KB · total 2 KB', text)
            self.assertIn('Database files total (including sidecars): 4 KB', text)
            self.assertIn('Total 8 KB · used 5 KB · free 3 KB', text)
            probe.assert_called_once()

    def test_memory_and_unavailable_paths(self):
        text = '\n'.join(storage_status([':memory:'], None))
        self.assertIn('in memory', text)
        with tempfile.TemporaryDirectory() as directory:
            text = '\n'.join(storage_status([directory + '/missing'], directory))
            self.assertIn('Database size unavailable', text)
            self.assertIn('Disk containing browsed files', text)
        self.assertIn('No local database files', '\n'.join(storage_status([])))

    def test_disk_error_does_not_hide_database_size(self):
        with tempfile.TemporaryDirectory() as directory:
            main = Path(directory) / 'catalog'
            main.write_bytes(b'x' * 1024)
            with patch('vfs.storage_status.shutil.disk_usage', side_effect=OSError('offline')):
                text = '\n'.join(storage_status([str(main)]))
            self.assertIn('File 1 KB', text)
            self.assertIn('Disk space unavailable', text)
