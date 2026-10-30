"""Real 10,000-file listings must avoid whole-directory work on warm redraws."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('large_grid_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class LargeGridTests(unittest.TestCase):
    def test_ten_thousand_files_warm_redraw_and_viewport_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {}
            for index in range(10000):
                path = root / f'photo-{index:05}.jpg'
                path.touch()
                files[str(path)] = {'same:0'}
            fs = VirtualFS({'files': files})
            fs.cwd = fs.get_from_path(str(root))
            with patch.object(fs, 'start_in_current_directory'):
                browser = tui.DriveBrowser(fs, input=DummyInput(), output=DummyOutput())
            browser.graphics_mode = True
            content = browser.control.create_content(80, 30)
            for line in range(30):
                content.get_line(line)
            maximum = browser.filename_maximum()
            groups, locations = browser.grid_media_layout()
            self.assertEqual(len(locations), 10000)
            self.assertEqual(len(browser.rows), 10001)
            with patch.object(tui, 'filename_end', side_effect=AssertionError('rescanned names')), patch.object(
                    tui.os.path, 'islink', side_effect=AssertionError('filesystem check on redraw')):
                for _ in range(20):
                    content = browser.control.create_content(80, 30)
                    for line in range(30):
                        content.get_line(line)
                    self.assertEqual(browser.filename_maximum(), maximum)
                    self.assertIs(browser.grid_media_layout()[0], groups)
                    tui.PreviewMapMargin(browser).create_margin(None, browser.grid_columns, 30)
                self.assertGreater(content.line_count, 1000)
            class Pending(dict):
                def items(self):
                    raise AssertionError('scanned entire pending queue')
            pending = Pending(enumerate(browser.rows))
            for top in (0, 1, len(browser.grid_lines) // 2, len(browser.grid_lines) - 30):
                actual = browser.visible_thumbnail_rows(pending, top, 30)
                expected = {i for i in pending if top <= browser.grid_positions[i][1] < top + 30
                            and browser.grid_positions[i][3]}
                self.assertEqual(set(actual), expected)
                self.assertLessEqual(len(actual), 30 * browser.grid_columns)
            browser.filename_width = 1
            self.assertGreater(browser.filename_maximum(), maximum)
            browser.show_path_prefixes = not browser.show_path_prefixes
            with patch.object(browser, 'file_list_path', wraps=browser.file_list_path) as labels:
                browser.filename_maximum()
                self.assertEqual(labels.call_count, len(browser.rows))
