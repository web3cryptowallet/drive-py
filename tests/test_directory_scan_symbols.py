"""Files summaries match scanner state precedence and refresh only on reload."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import unittest

spec = importlib.util.spec_from_file_location('directory_symbols_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class DirectorySymbolsTests(unittest.TestCase):
    def test_listing_confirms_empty_before_scan_and_rechecks_on_refresh(self):
        import tempfile
        from prompt_toolkit.input import DummyInput
        from prompt_toolkit.output import DummyOutput
        from vfs import VirtualFS
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'empty'
            folder.mkdir()
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            def marker():
                index = next(i for i, row in enumerate(browser.rows) if row['name'] == 'empty')
                return browser.control.create_content(80, 10).get_line(index)[0]
            self.assertEqual(marker()[1], '·')
            self.assertIn('class:green', marker()[0])
            browser.refresh_scan_symbols()
            self.assertEqual(marker()[1], '·')
            (folder / '.hidden').touch()
            browser.refresh()
            self.assertEqual(marker()[1], '●')
            self.assertIn('class:orange', marker()[0])
            (folder / '.hidden').unlink()
            entries = [(row['name'], row['node']) for row in browser.rows]
            with patch.object(tui.os, 'scandir', side_effect=PermissionError('denied')):
                browser.refresh(_entries=entries)
            self.assertEqual(marker()[1], '●')

    def test_completed_directory_renders_settled_color_without_navigation(self):
        import tempfile
        from prompt_toolkit.input import DummyInput
        from prompt_toolkit.output import DummyOutput
        from vfs import VirtualFS
        from vfs.scanner import ScanEntry, ScanStats
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'folder'
            folder.mkdir()
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = tui.ScannerView(browser, startup=False)
            browser.scanners = [scanner]
            path = str(folder / 'file')
            index = next(i for i, row in enumerate(browser.rows) if row['name'] == 'folder')
            browser.rows[index]['indicator'] = 'orange'
            scanner.model.update(ScanEntry(path, path, False, state='unknown'))
            scanner.stats = ScanStats(path=path, active=True)
            browser.refresh_scan_symbols()
            active = browser.control.create_content(80, 10).get_line(index)[0]
            self.assertIn('fg:#ffd700', active[0])
            scanner.model.update(ScanEntry(path, path, False, state='verified'))
            scanner.events.put(('stats', ScanStats(path=path, active=False)))
            scanner.drain_all()
            settled = browser.control.create_content(80, 10).get_line(index)[0]
            self.assertEqual(settled[1], '●')
            self.assertIn('class:green', settled[0])
            self.assertNotIn('fg:#ffd700', settled[0])
            for state, symbol, color in [('modified', 'M', 'orange'), ('missing', 'U', 'red')]:
                scanner.model.update(ScanEntry(path, path, False, state=state))
                browser.refresh_scan_symbols()
                marker = browser.control.create_content(80, 10).get_line(index)[0]
                self.assertEqual(marker[1], symbol)
                self.assertIn('class:' + color, marker[0])
            browser.scanners = []
            browser.refresh_scan_symbols()
            self.assertNotIn('scan_color', browser.rows[index])

    def test_pass_completion_refreshes_folder_summary_without_navigation(self):
        from queue import Queue
        from vfs.scanner import ScanStats
        view = object.__new__(tui.ScannerView)
        view.events = Queue()
        view.browser = Mock()
        view.stats = ScanStats(active=True)
        view.events.put(('stats', ScanStats(active=True)))
        view.events.put(('stats', ScanStats(active=False)))
        view.events.put(('stats', ScanStats(active=False)))
        view.drain_all()
        view.browser.refresh_scan_symbols.assert_called_once_with()

    def test_completed_file_marker_uses_live_result_color(self):
        from vfs.scanner import ScanEntry
        browser = object.__new__(tui.DriveBrowser)
        scanner = NS(closing=False, paused_modes=None,
                     controls=NS(modes=(False, False, True)),
                     stats=NS(active=True, path='/scan/file'),
                     model=NS(entries={}))
        browser.scanners = [scanner]
        row = dict(node=NS(id='/scan/file', is_dir=False), name='file',
                   label='● 📄 file', indicator='orange')
        scanner.model.entries[row['node'].id] = ScanEntry(
            '/scan/file', '/scan/file', False, state='verified')
        browser.scan_row_marker(row)
        self.assertTrue(row['scan_active'])
        scanner.stats.active = False
        self.assertEqual(browser.scan_row_marker(row), '●')
        self.assertFalse(row['scan_active'])
        self.assertEqual(row['indicator'], 'green')
        for state, expected in [('modified', 'orange'), ('missing', 'red'),
                                ('unknown', 'white')]:
            scanner.model.entries[row['node'].id] = ScanEntry(
                '/scan/file', '/scan/file', False, state=state)
            browser.scan_row_marker(row)
            self.assertEqual(row['indicator'], expected)

    def test_heavy_circle_is_gold_but_settled_empty_dot_is_green(self):
        import tempfile
        from prompt_toolkit.input import DummyInput
        from prompt_toolkit.output import DummyOutput
        from vfs import VirtualFS
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'empty'
            folder.mkdir()
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            scanner = NS(closing=False, paused_modes=None,
                         controls=NS(modes=(False, False, True)),
                         stats=NS(active=True, path=str(folder / 'file')),
                         model=NS(entries={}))
            browser.scanners = [scanner]
            index = next(index for index, row in enumerate(browser.rows) if row['name'] == 'empty')
            browser.rows[index]['scan_symbol'] = '·'
            with patch.object(tui.time, 'monotonic', return_value=0):
                active = browser.control.create_content(80, 10).get_line(index)[0]
            self.assertEqual(active[1], '◐')
            self.assertIn('fg:#ffd700', active[0])
            scanner.stats.active = False
            settled = browser.control.create_content(80, 10).get_line(index)[0]
            self.assertEqual(settled[1], '·')
            self.assertIn('class:green', settled[0])
            self.assertNotIn('fg:#ffd700', settled[0])
            scanner.stats.active = True
            scanner.controls.modes = (False, True, False)
            with patch.object(tui.time, 'monotonic', return_value=0):
                medium = browser.control.create_content(80, 10).get_line(index)[0]
            self.assertEqual(medium[1], '\\')
            self.assertIn('fg:#af5fff', medium[0])


    def test_heavy_rotating_frames_in_files_and_map_keep_colors_and_width(self):
        from vfs.scanner import FileMap, ScanEntry
        browser = object.__new__(tui.DriveBrowser)
        scanner = NS(closing=False, paused_modes=None, controls=NS(modes=(False, False, True)),
                     stats=NS(active=True, path='/scan/file'), model=FileMap())
        scanner.model.update(ScanEntry('/scan/file', '/scan/file', False))
        scanner.model.buckets[0].updated = 0
        scanner.backgrounds, scanner.expert_blue = {}, set()
        scanner.selected, scanner.follow_end = 1, False
        browser.scanners = [scanner]
        row = dict(node=NS(id='/scan', is_dir=True), name='scan', label='● 📁 scan')
        grid = tui.MapControl(scanner)
        for index, expected in enumerate(('◐', '◓', '◑', '◒', '◐')):
            now = index / 8
            with patch.object(tui.time, 'monotonic', return_value=now):
                self.assertEqual(browser.scan_row_marker(row), expected)
                self.assertTrue(row['scan_active'])
            (style, symbol), deadline = grid.render_cell(0, now, False)
            self.assertEqual(symbol, expected)
            self.assertEqual(tui.get_cwidth(symbol), 1)
            self.assertIn('fg:#ffffff bg:#ff0000', style)
            self.assertGreater(deadline, now)
        scanner.stats.active = False
        row['scan_symbol'] = '·'
        self.assertEqual(browser.scan_row_marker(row), '·')
        self.assertFalse(row['scan_active'])
        self.assertIsNone(grid.render_cell(0, 2, False)[1])
        # Actual worker stage takes precedence when multiple modes are enabled.
        scanner.engine = NS(current_mode=3)
        scanner.controls.modes = (True, True, True)
        self.assertEqual(tui.scan_activity_frame(scanner, 0), '◐')
        scanner.engine.current_mode = 2
        self.assertEqual(tui.scan_activity_frame(scanner, 0), '\\')

    def test_summary_boundaries_color_and_manual_snapshot(self):
        browser = object.__new__(tui.DriveBrowser)
        def row(path, name):
            return dict(node=NS(id=path, is_dir=True), name=name, label='● 📁 ' + name, indicator='orange')
        browser.rows = [row('/scan/a', 'a'), row('/scan/ab', 'ab'), row('/scan', '..')]
        entries = {
            'a': NS(path='/scan/a/one', state='unknown', blacklisted=False),
            'b': NS(path='/scan/a/two', state='verified', blacklisted=False),
            'c': NS(path='/scan/ab/three', state='modified', blacklisted=False),
        }
        browser.scanners = [NS(model=NS(entries=entries), closing=False, paused_modes=None,
                               controls=NS(modes=(False, False, False)),
                               stats=NS(active=False, path=''))]
        browser.refresh_scan_symbols()
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '●')
        self.assertEqual(browser.rows[0]['indicator'], 'orange')
        self.assertNotIn('scan_color', browser.rows[0])
        self.assertEqual(browser.scan_row_marker(browser.rows[1]), 'M')
        self.assertEqual(browser.scan_row_marker(browser.rows[2]), '●')
        entries['a'].state = 'verified'
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '●')
        browser.refresh_scan_symbols()
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '●')
        entries['a'].blacklisted = True
        browser.refresh_scan_symbols()
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '!')
        browser.scanners = []
        browser.refresh_scan_symbols()
        self.assertEqual(browser.scan_row_marker(browser.rows[1]), '●')

    def test_closing_scanner_refreshes_symbols_before_return(self):
        browser = Mock()
        scanner = object.__new__(tui.ScannerView)
        scanner.browser = browser
        scanner.close()
        self.assertEqual(browser.method_calls, [
            unittest.mock.call.refresh_scan_symbols(), unittest.mock.call.pop(scanner)])

    def test_rotation_tracks_active_descendants_without_aggregating(self):
        browser = object.__new__(tui.DriveBrowser)
        scanner = NS(closing=False, paused_modes=None, controls=NS(modes=(True, False, False)),
                     stats=NS(active=True, path='/scan/a/nested/file'))
        browser.scanners = [scanner]
        row = dict(node=NS(id='/scan/a', is_dir=True), name='a',
                   label='● 📁 a', scan_symbol='?', indicator='green')
        with patch.object(tui.time, 'monotonic') as clock:
            for index, symbol in enumerate(('\\', '|', '/', '-')):
                clock.return_value = index / 8
                self.assertEqual(browser.scan_row_marker(row), symbol)
                self.assertEqual(len(symbol), 1)
            scanner.stats.path = '/scan/ab/file'
            self.assertEqual(browser.scan_row_marker(row), row['label'][0])
            scanner.stats.path = '/scan/a'
            self.assertEqual(browser.scan_row_marker(row), '-')
            scanner.paused_modes = (True, False, False)
            self.assertEqual(browser.scan_row_marker(row), row['label'][0])
            scanner.paused_modes = None
            scanner.stats.active = False
            self.assertEqual(browser.scan_row_marker(row), row['label'][0])
            scanner.stats.active = True
            scanner.closing = True
            self.assertEqual(browser.scan_row_marker(row), row['label'][0])
            scanner.closing = False
            scanner.controls.modes = (False, False, False)
            self.assertEqual(browser.scan_row_marker(row), row['label'][0])
            scanner.controls.modes = (True, False, False)
            row['name'] = '..'
            self.assertEqual(browser.scan_row_marker(row), '●')
        self.assertEqual(row['indicator'], 'green')

    def test_file_rows_use_exact_scan_state_and_color(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.rows = [dict(node=NS(id=path, is_dir=False), name=path.rsplit('/', 1)[-1],
                             label='● 📄 file', indicator='green')
                        for path in ('/scan/file', '/scan/file-other', '/scan/missing')]
        entry = NS(path='/scan/file', state='unknown', blacklisted=False)
        scanner = NS(model=NS(entries={'/scan/file': entry}), closing=False, paused_modes=None,
                     controls=NS(modes=(False, False, False)), stats=NS(active=False, path=''))
        browser.scanners = [scanner]
        browser.refresh_scan_symbols()
        self.assertEqual([browser.scan_row_marker(row) for row in browser.rows], ['●', '●', '●'])
        for state, symbol in (('modified', 'M'), ('missing', 'U'), ('verified', '●')):
            entry.state = state
            browser.refresh_scan_symbols()
            self.assertEqual(browser.scan_row_marker(browser.rows[0]), symbol)
            self.assertEqual(browser.rows[0]['indicator'],
                             {'modified': 'orange', 'missing': 'red', 'verified': 'green'}[state])
        entry.state = 'unknown'
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '●')
        scanner.close = lambda: tui.ScannerView.close(scanner)
        scanner.browser = browser
        browser.pop = Mock()
        scanner.close()
        self.assertEqual(browser.scan_row_marker(browser.rows[0]), '●')

    def test_live_file_state_and_rotation_without_reload(self):
        browser = object.__new__(tui.DriveBrowser)
        entry = NS(state='unknown', blacklisted=False)
        scanner = NS(model=NS(entries={'/scan/file': entry}), closing=False, paused_modes=None,
                     controls=NS(modes=(True, False, False)),
                     stats=NS(active=False, path='/scan/file'))
        browser.scanners = [scanner]
        row = dict(node=NS(id='/scan/file', is_dir=False), name='file',
                   label='● 📄 file', indicator='orange')
        self.assertEqual(browser.scan_row_marker(row), row['label'][0])
        entry.state = 'modified'
        self.assertEqual(browser.scan_row_marker(row), 'M')
        scanner.stats.active = True
        with patch.object(tui.time, 'monotonic', return_value=0):
            self.assertEqual(browser.scan_row_marker(row), '\\')
            scanner.stats.path = '/scan/file-other'
            self.assertEqual(browser.scan_row_marker(row), 'M')
            scanner.stats.path = '/scan/file'
            scanner.paused_modes = (True, False, False)
            self.assertEqual(browser.scan_row_marker(row), 'M')
        entry.state = 'verified'
        self.assertEqual(browser.scan_row_marker(row), '●')
        self.assertEqual(row['indicator'], 'green')

    def test_row_change_defers_work_and_redraws_immediately(self):
        browser = object.__new__(tui.DriveBrowser)
        browser.rows = [dict(name='one'), dict(name='two')]
        browser.selected = 0
        browser.video_player = None
        browser.auto_quick_view = True
        browser.graphics_mode = False
        calls = Mock()
        browser.note_cursor_motion = calls.defer
        browser.sync_scan_symbols = calls.sync
        browser.show_info = calls.preview
        browser.app = NS(invalidate=calls.redraw)
        browser.select(1)
        self.assertEqual(calls.method_calls, [unittest.mock.call.defer(refresh=True),
                                             unittest.mock.call.redraw()])
        calls.reset_mock()
        browser.select(1)
        calls.sync.assert_not_called()

    def test_sync_drains_events_before_snapshot_and_skips_repacking(self):
        browser = object.__new__(tui.DriveBrowser)
        calls = Mock()
        browser.scanners = [NS(repacking=False, drain_all=calls.drain),
                            NS(repacking=True, drain_all=calls.blocked)]
        browser.refresh_scan_symbols = calls.snapshot
        browser.sync_scan_symbols()
        self.assertEqual(calls.method_calls, [unittest.mock.call.drain(budget=.015),
                                              unittest.mock.call.snapshot()])

    def test_discovery_confirms_empty_and_clears_it_when_child_appears(self):
        import tempfile
        from queue import Queue
        from threading import Event
        from vfs import VirtualFS
        from vfs.scanner import DriveScanner, ScanEntry, ScanStore
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / 'empty'
            empty.mkdir()
            fs = VirtualFS({'files': {}})
            scanner = DriveScanner(fs.db, directory, Queue(), Event())
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[str(empty)].state, 'empty')
            self.assertEqual(scanner.entries[directory].state, 'directory')
            stored = ScanStore(fs.db).get('entry', str(empty))
            self.assertEqual(ScanEntry(**stored).state, 'empty')
            browser = object.__new__(tui.DriveBrowser)
            browser.rows = [dict(node=NS(id=str(empty), is_dir=True), name='empty',
                                 label='● 📁 empty', indicator='orange')]
            browser.scanners = [NS(model=NS(entries=scanner.entries))]
            browser.refresh_scan_symbols()
            self.assertEqual(browser.rows[0]['scan_symbol'], '·')
            self.assertEqual(tui.SCAN_STATES['empty'][:2], ('·', '#98e024'))
            (empty / 'file').write_text('data')
            scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[str(empty)].state, 'directory')
            browser.refresh_scan_symbols()
            self.assertNotEqual(browser.rows[0]['scan_symbol'], '·')
            with patch('vfs.scanner.os.scandir', side_effect=PermissionError('denied')):
                scanner.scan_once(fs.db)
            self.assertEqual(scanner.entries[directory].state, 'directory')
        self.assertEqual(ScanEntry('/f', '/f', False, state='empty').state, 'unknown')
