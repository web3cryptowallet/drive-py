"""Files and duplicate counts have distinct visible table columns."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('count_columns_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class CountColumnsTests(unittest.TestCase):
    def test_distinct_counts_and_fixed_metadata_under_narrow_widths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'folder').mkdir()
            fs = VirtualFS({'files': {}})
            for name, digest, data in [('a', 'md5:same', b'data'), ('b', 'md5:same', b'data'),
                                       ('folder/c', 'md5:other', b'x')]:
                path = root / name
                path.write_bytes(data)
                fs.db.add_scanned_file(str(path), digest, len(data))
            browser = tui.DriveBrowser(fs, path=directory, input=DummyInput(), output=DummyOutput())
            for width in (32, 40, 80):
                content = browser.control.create_content(width, 20)
                header = ''.join(text for _, text in browser.column_header())
                for title in ('Size', 'Files', 'Dups'):
                    self.assertIn(title, header)
                self.assertLessEqual(tui.get_cwidth(header), width)
                for index, row in enumerate(browser.rows):
                    fragments = content.get_line(index)
                    rendered = ''.join(text for _, text in fragments)
                    self.assertLessEqual(tui.get_cwidth(rendered), width)
                    counts = fragments[-1][1].split()[-2:]
                    if row['name'] == 'folder':
                        self.assertEqual(counts, ['1', '—'])
                    elif row['name'] in ('a', 'b'):
                        self.assertEqual(counts, ['1', '2'])
                    elif row['name'] == '..':
                        self.assertEqual(counts, ['—', '—'])
