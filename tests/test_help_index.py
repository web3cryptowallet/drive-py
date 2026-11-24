"""Three-column help search, selection, highlights and context lifecycle."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from prompt_toolkit.data_structures import Size, Point
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType, MouseButton
from vfs import VirtualFS
from vfs.help_index import help_entries

spec = importlib.util.spec_from_file_location('help_index_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class ShortOutput(DummyOutput):
    def get_size(self):
        return Size(rows=18, columns=90)


class HelpIndexTests(unittest.IsolatedAsyncioTestCase):
    def test_trash_section_describes_current_controls(self):
        entries = help_entries(tui.main_help(0), tui.plain_markup)
        trash = [entry for entry in entries if entry.section == 'Trash']
        self.assertEqual({entry.key for entry in trash}, {'Ctrl+D', 'd'})
        description = next(entry.description for entry in trash if entry.key == 'd')
        for detail in ('yyyy-mm-dd hh:mm:ss', 'last six hash', 'case-insensitive',
                       'bold black on yellow', 'expands/collapses', 'jumps', 'Esc'):
            self.assertIn(detail, description)
        self.assertEqual(sum(entry.key == 'd' for entry in entries), 1)

    async def test_enter_runs_main_search_scanner_and_local_help_actions(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=ShortOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))

            async def until(predicate):
                for _ in range(100):
                    if predicate():
                        return
                    await asyncio.sleep(.01)
                self.fail('Help action did not complete')

            def choose(view, key, local=False):
                view.select(next(index for index, entry in enumerate(view.filtered)
                                 if entry.key == key and entry.local == local))

            try:
                await asyncio.sleep(.04)
                pipe.send_text('h')
                await until(lambda: bool(browser.screen_stack))
                view = browser.screen_stack[-1][0]
                view.search_focus()
                view.search.text = 'prefix'
                choose(view, 'x')
                selected = view.filtered[view.index]
                previous = browser.show_path_prefixes
                pipe.send_text('\r')
                await until(lambda: not browser.screen_stack)
                self.assertNotEqual(browser.show_path_prefixes, previous)
                await until(lambda: browser.clipboard_notice == f'Applied key x: {selected.short}')

                pipe.send_text('h')
                await until(lambda: bool(browser.screen_stack))
                view = browser.screen_stack[-1][0]
                choose(view, 'Tab', local=True)
                selected = view.filtered[view.index]
                _, positions = view.grid.layout_rows()
                column = positions[view.index][1]
                column_ids = [index for index, (_, col) in positions.items() if col == column]
                pipe.send_text('\r')
                await until(lambda: browser.clipboard_notice == f'Applied key Tab: {selected.short}')
                self.assertIs(browser.screen_stack[-1][0], view)
                self.assertFalse(any(entry.key in {'Up', 'Down', 'Left', 'Right', 'PageUp', 'PageDown', 'Home', 'End'} for entry in view.entries))
                view.search_focus()
                pipe.send_text('\x1b[5~')
                await until(lambda: view.index == column_ids[0])
                pipe.send_text('\x1b[6~')
                await until(lambda: view.index == column_ids[-1])
                view.search.text = 'no-match-at-all-12345'
                notice_epoch = browser.clipboard_notice_epoch
                pipe.send_text('\r')
                await asyncio.sleep(.03)
                self.assertIs(browser.screen_stack[-1][0], view)
                self.assertEqual(browser.clipboard_notice_epoch, notice_epoch)
                view.close()

                scanner = tui.ScannerView(browser, startup=False)
                with patch.object(scanner, 'start'):
                    browser.push(scanner)
                browser.app.layout.focus(scanner.limit)
                view = tui.HelpView(browser, 'Drive map help', tui.SCANNER_HELP)
                browser.push(view)
                choose(view, 'r')
                selected = view.filtered[view.index]
                previous = scanner.controls.read_known
                pipe.send_text('\r')
                await until(lambda: browser.screen_stack[-1][0] is scanner)
                self.assertNotEqual(scanner.controls.read_known, previous)
                self.assertTrue(browser.app.layout.has_focus(scanner.grid))
                await until(lambda: browser.clipboard_notice == f'Applied key r: {selected.short}')
                scanner.close()

                view = tui.HelpView(browser, 'Files help', tui.main_help(0))
                browser.push(view)
                choose(view, '/')
                pipe.send_text('\r')
                await until(lambda: isinstance(browser.screen_stack[-1][0], tui.PathCommandView))
            finally:
                browser.app.exit()
                await task

    async def test_search_typing_highlights_three_columns_and_navigation(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=ShortOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                pipe.send_text('h')
                await asyncio.sleep(.05)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.HelpView)
                self.assertTrue(view.entries)
                content = view.grid.create_content(90, 8)
                self.assertEqual(''.join(text for _, text in content.get_line(1)).count('│'), 4)
                _, positions = view.grid.layout_rows()
                first, second = next((left, right) for left, (row, column) in positions.items()
                                     if column == 0 for right, position in positions.items()
                                     if position == (row, 1))
                view.select(first)
                pipe.send_text('\x1b[C')
                await asyncio.sleep(.04)
                self.assertEqual(view.index, second)
                pipe.send_text('\x1b[D')
                await asyncio.sleep(.04)
                self.assertEqual(view.index, first)
                pipe.send_text('\x1b[F')  # End
                await asyncio.sleep(.04)
                self.assertEqual(view.index, len(view.filtered) - 1)
                self.assertGreater(view.window.vertical_scroll, 0)
                pipe.send_text('\x1b[B')  # Down wraps last -> first
                await asyncio.sleep(.04)
                self.assertEqual(view.index, 0)
                self.assertEqual(view.window.vertical_scroll, 0)
                pipe.send_text('\x1b[A')  # Up wraps first -> last
                await asyncio.sleep(.04)
                self.assertEqual(view.index, len(view.filtered) - 1)
                self.assertGreater(view.window.vertical_scroll, 0)
                pipe.send_text('\x1b[H')  # Home
                await asyncio.sleep(.04)
                self.assertEqual(view.index, 0)
                self.assertEqual(view.window.vertical_scroll, 0)
                pipe.send_text('\x1b[6~')  # PageDown
                await asyncio.sleep(.04)
                _, positions = view.grid.layout_rows()
                first_column = [index for index, (_, col) in positions.items() if col == 0]
                self.assertEqual(view.index, first_column[-1])
                pipe.send_text('\x1b[F')  # End still jumps across all columns.
                await asyncio.sleep(.04)
                self.assertEqual(view.index, len(view.filtered) - 1)
                pipe.send_text('\x1b[H')
                await asyncio.sleep(.04)
                view.column_endpoint(True)
                pipe.send_text('\x1b[5~')  # PageUp
                await asyncio.sleep(.04)
                self.assertEqual(view.index, 0)
                view.select(5)
                self.assertEqual(view.index, 5)
                view.grid.mouse_handler(MouseEvent(Point(1, 1), MouseEventType.SCROLL_DOWN,
                                                   MouseButton.NONE, frozenset()))
                self.assertEqual(view.index, 6)
                view.grid.mouse_handler(MouseEvent(Point(1, 1), MouseEventType.SCROLL_UP,
                                                   MouseButton.NONE, frozenset()))
                self.assertEqual(view.index, 5)
                rows, positions = view.grid.layout_rows()
                first_column = [index for index, (_, column) in positions.items() if column == 0]
                second_column = [index for index, (_, column) in positions.items() if column == 1]
                view.select(first_column[-1])
                await asyncio.sleep(.04)
                self.assertGreater(view.window.vertical_scroll, 0)
                view.move(3)
                await asyncio.sleep(.04)
                self.assertEqual(view.index, second_column[0])
                self.assertEqual(view.window.vertical_scroll, 0)
                view.move(-3)
                await asyncio.sleep(.04)
                self.assertEqual(view.index, first_column[-1])
                self.assertGreater(view.window.vertical_scroll, 0)
                pipe.send_text('/black')  # b/h must be text, not bookmark/help actions.
                await asyncio.sleep(.06)
                self.assertEqual(view.search.text, 'black')
                self.assertIs(browser.screen_stack[-1][0], view)
                self.assertTrue(view.filtered)
                self.assertEqual(view.index, 0)
                self.assertIn('black', view.text.text.lower())
                fragments = [fragment for y in range(view.grid.create_content(90, 8).line_count)
                             for fragment in view.grid.create_content(90, 8).get_line(y)]
                self.assertTrue(any('bg:#ffff00' in style for style, text in fragments))
                view.search.text = 'cache'
                self.assertTrue({'k', 'K', 'G'}.issubset({entry.key for entry in view.filtered}))
                self.assertTrue(all(entry.section == 'Cache' or 'cache' in entry.description.lower()
                                    for entry in view.filtered))
                view.search.text = ''
                pipe.send_text('qjx')
                await asyncio.sleep(.03)
                self.assertEqual(view.search.text, 'qjx')
                self.assertFalse(view.filtered)
                self.assertIn('No shortcuts', view.text.text)
                view.escape()
                self.assertTrue(browser.app.layout.has_focus(view.grid))
                self.assertEqual(view.search.text, 'qjx')
                view.search_focus()
                view.search.text = ''
                pipe.send_text('\x1b[B')
                await asyncio.sleep(.03)
                self.assertEqual(view.index, 1)
                view.select(next(index for index, entry in enumerate(view.filtered)
                                 if entry.local and entry.key == 'Enter'))
                pipe.send_text('\r')
                await asyncio.sleep(.03)
                self.assertTrue(browser.app.layout.has_focus(view.grid))
                view.grid.create_content(90, 8)
                rows, positions = view.grid.layout_rows()
                y, column = positions[1]
                x = 1 + sum(view.grid.widths[:column]) + column
                view.grid.mouse_handler(MouseEvent(Point(x, y),
                    MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
                self.assertEqual(view.index, 1)
                self.assertEqual(view.text.text, view.filtered[1].description)
                pipe.send_text('h')
                await asyncio.sleep(.04)
                self.assertFalse(browser.screen_stack)
                self.assertEqual(browser.vfs.pwd(), directory)
            finally:
                browser.app.exit()
                await task

    async def test_scanner_help_preserves_context_and_plain_errors(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=ShortOutput())
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                scanner = tui.ScannerView(browser, startup=False)
                with patch.object(scanner, 'start'):
                    browser.push(scanner)
                view = tui.HelpView(browser, 'Drive map help', tui.SCANNER_HELP)
                browser.push(view)
                view.search.text = 'checksum'
                self.assertTrue(view.filtered)
                self.assertFalse(scanner.stop.is_set())
                view.close()
                self.assertIs(browser.screen_stack[-1][0], scanner)
                scanner.close()
                error = tui.HelpView(browser, 'Open error', ['File could not be opened'])
                self.assertFalse(error.entries)
                self.assertIn('File could not', error.text.text)
            finally:
                browser.app.exit()
                await task


class HelpShortcutLabelTests(unittest.TestCase):
    def test_displayed_shortcuts_normalize_and_keep_local_context(self):
        from prompt_toolkit.keys import Keys
        from vfs.help_index import shortcut_key
        for label, key in [('Enter', Keys.ControlM), ('Space', ' '), ('Ctrl+S', Keys.ControlS),
                           ('Shift+Tab', Keys.BackTab), ('Shift+1', '!'), ('Shift+R', 'R'),
                           ('PageDown', Keys.PageDown), ('Shift+Left', Keys.ShiftLeft), ('F4', Keys.F4)]:
            self.assertEqual(shortcut_key(label), key)
        self.assertIsNone(shortcut_key('Info'))
        entries = help_entries(tui.main_help(0), tui.plain_markup)
        self.assertEqual({entry.local for entry in entries if entry.key == '/'}, {False, True})

    def test_filename_endpoints_are_complete_keys_without_parentheses(self):
        entries = help_entries(tui.main_help(0), tui.plain_markup)
        endpoints = [entry for entry in entries
                     if entry.short == 'Beginning / end of longest filename']
        self.assertEqual([entry.key for entry in endpoints],
                         ['Shift+Home', 'Shift+End', 'Shift+PageUp', 'Shift+PageDown'])
        self.assertTrue(all('Beginning / end' in entry.description for entry in endpoints))
        self.assertFalse(any('(' in entry.key or ')' in entry.key for entry in entries))
        keys = [entry.key for entry in entries]
        self.assertIn('Shift+Right', keys)
        shifted = [entry.key for entry in entries if entry.short.startswith('Pan filenames')]
        self.assertNotIn('Right', shifted)


    def test_sections_are_yellow_and_shortcut_coordinates_skip_headers(self):
        from types import SimpleNamespace
        from vfs.help_index import HelpIndexControl
        entries = help_entries(tui.main_help(0), tui.plain_markup)
        self.assertTrue({'Files', 'Scan view', 'Cache', 'Media'}.issubset(
            {entry.section for entry in entries}))
        selected = []
        view = SimpleNamespace(filtered=entries, index=0, query='', select=selected.append)
        control = HelpIndexControl(view)
        control.create_content(90, 8)
        rows, positions = control.layout_rows()
        for width in (45, 90):
            content = control.create_content(width, 8)
            for y, row in enumerate(rows, 1):
                fragments = content.get_line(y)
                self.assertEqual(''.join(text for _, text in fragments).count('│'), 4)
                for column, cell in enumerate(row):
                    if isinstance(cell, str):
                        self.assertTrue(any('fg:#ffff00' in style and text.strip()
                                            for style, text in fragments))
                        x = 2 + sum(control.widths[:column]) + column
                        control.mouse_handler(MouseEvent(Point(x, y), MouseEventType.MOUSE_UP,
                                                         MouseButton.LEFT, frozenset()))
            self.assertEqual(selected, [])
        for index in range(len(entries)):
            view.index = index
            content = control.create_content(90, 8)
            y, column = positions[index]
            self.assertEqual(content.cursor_position.y, y)
            self.assertEqual(rows[y - 1][column], index)
        view.grid = control
        view.select = lambda index: setattr(view, 'index', max(0, min(index, len(entries) - 1)))
        for index in positions:
            view.index = index
            tui.HelpView.move(view, 3)
            self.assertEqual(view.index, (index + 1) % len(entries))
        scanner = help_entries(tui.SCANNER_HELP, tui.plain_markup)
        self.assertTrue({'Scanning', 'Map and settings', 'File list and pages'}.issubset(
            {entry.section for entry in scanner}))


class HelpColumnFlowTests(unittest.TestCase):
    def test_page_endpoints_stay_in_current_column_after_resize_and_filter(self):
        from types import SimpleNamespace
        from vfs.help_index import HelpEntry, HelpIndexControl
        entries = [HelpEntry(str(i), str(i), str(i), 'Files' if i < 6 else 'Cache')
                   for i in range(10)]
        view = SimpleNamespace(filtered=entries, index=0, query='')
        view.grid = HelpIndexControl(view)
        view.select = lambda index: setattr(view, 'index', index)
        for height in (7, 5, 12):
            view.grid.create_content(90, height)
            _, positions = view.grid.layout_rows()
            for column in {col for _, col in positions.values()}:
                ids = [index for index, (_, col) in positions.items() if col == column]
                view.index = ids[len(ids) // 2]
                tui.HelpView.column_endpoint(view, True)
                self.assertEqual(view.index, ids[-1])
                tui.HelpView.column_endpoint(view, False)
                self.assertEqual(view.index, ids[0])
        view.filtered = entries[:1]
        view.index = 0
        for last in (True, False):
            tui.HelpView.column_endpoint(view, last)
            self.assertEqual(view.index, 0)
        view.filtered = []
        tui.HelpView.column_endpoint(view, True)
        self.assertEqual(view.index, 0)

    def test_downward_flow_height_limit_sections_and_resize(self):
        from types import SimpleNamespace
        from vfs.help_index import HelpEntry, HelpIndexControl
        entries = [HelpEntry(str(i), str(i), str(i), 'Files' if i < 6 else 'Cache')
                   for i in range(10)]
        view = SimpleNamespace(filtered=entries, index=0, query='')
        control = HelpIndexControl(view)
        control.create_content(90, 7)  # five content rows per column
        rows, positions = control.layout_rows()
        self.assertEqual([row[0] for row in rows], ['Files', 0, 1, 2, 3])
        self.assertEqual([row[1] for row in rows], [4, 5, 'Cache', 6, 7])
        self.assertEqual([row[2] for row in rows], [8, 9, -1, -1, -1])
        self.assertEqual(positions[4], (1, 1))
        view.select = lambda index: self.fail('Blank help cells must not select an entry')
        x = 1 + sum(control.widths[:2]) + 2
        control.mouse_handler(MouseEvent(Point(x, 3), MouseEventType.MOUSE_UP,
                                        MouseButton.LEFT, frozenset()))
        control.create_content(90, 5)  # resize to three content rows
        rows, positions = control.layout_rows()
        self.assertEqual([row[0] for row in rows], ['Files', 0, 1, 2])
        self.assertEqual(positions[3], (1, 1))
        self.assertGreater(len(rows), 3)  # one shared scroll through longer columns
        self.assertEqual({column for _, column in positions.values()}, {0, 1, 2})

    def test_vertical_arrows_follow_reading_order_across_columns_and_pages(self):
        from types import SimpleNamespace
        from vfs.help_index import HelpEntry, HelpIndexControl
        entries = [HelpEntry(str(i), str(i), str(i), 'Files' if i < 4 else 'Cache')
                   for i in range(15)]
        view = SimpleNamespace(filtered=entries, index=0, query='')
        control = HelpIndexControl(view)
        view.grid = control
        view.select = lambda index: setattr(view, 'index', max(0, min(index, len(entries) - 1)))
        control.create_content(90, 6)
        _, positions = control.layout_rows()
        for forward, backward in ((3, -3),):
            view.index = 0
            for expected in range(1, len(entries)):
                tui.HelpView.move(view, forward)
                self.assertEqual(view.index, expected)
                self.assertEqual(control.create_content(90, 6).cursor_position.y,
                                 positions[expected][0])
            tui.HelpView.move(view, forward)
            self.assertEqual(view.index, 0)
            tui.HelpView.move(view, backward)
            self.assertEqual(view.index, len(entries) - 1)
            for expected in reversed(range(len(entries) - 1)):
                tui.HelpView.move(view, backward)
                self.assertEqual(view.index, expected)
            tui.HelpView.move(view, backward)
            self.assertEqual(view.index, len(entries) - 1)

    def test_horizontal_moves_preserve_rows_skip_headings_blanks_and_wrap(self):
        from types import SimpleNamespace
        from vfs.help_index import HelpEntry, HelpIndexControl
        entries = [HelpEntry(str(i), str(i), str(i), 'Files' if i < 6 else 'Cache')
                   for i in range(10)]
        view = SimpleNamespace(filtered=entries, index=0, query='')
        view.grid = HelpIndexControl(view)
        view.select = lambda index: setattr(view, 'index', index)
        view.grid.create_content(90, 7)
        # Column 2 has a heading at row 3; column 3 ends at row 2.
        view.index = 1
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 5)
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 9)
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 0)
        tui.HelpView.move_column(view, -1)
        self.assertEqual(view.index, 9)
        view.index = 3
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 7)
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 9)
        view.filtered = entries[:1]
        view.index = 0
        tui.HelpView.move_column(view, 1)
        self.assertEqual(view.index, 0)
        view.filtered = []
        tui.HelpView.move_column(view, -1)
        self.assertEqual(view.index, 0)

    def test_large_moves_wrap_and_empty_results_are_safe(self):
        from types import SimpleNamespace
        view = SimpleNamespace(filtered=list(range(8)), index=7)
        view.select = lambda index: setattr(view, 'index', index)
        tui.HelpView.move(view, 15)
        self.assertEqual(view.index, 0)
        tui.HelpView.move(view, -15)
        self.assertEqual(view.index, 7)
        view.filtered = [0]
        view.index = 0
        for delta in (-15, -3, -1, 1, 3, 15):
            tui.HelpView.move(view, delta)
            self.assertEqual(view.index, 0)
        view.filtered = []
        tui.HelpView.move(view, 3)
        self.assertEqual(view.index, 0)


class HelpBindingCoverageTests(unittest.TestCase):
    def test_files_scanner_and_help_registered_bindings_are_indexed(self):
        from prompt_toolkit.input import DummyInput
        def normalized(label):
            aliases = {'Space': ' ', 'Esc': 'escape', 'Enter': 'c-m', 'Tab': 'c-i',
                       'Backspace': 'c-h'}
            if label in aliases:
                return aliases[label]
            if label.startswith('Ctrl+'):
                return 'c-' + label[5:].lower()
            if label.startswith('Shift+'):
                key = label[6:]
                return key.upper() if len(key) == 1 and key.isalpha() else 's-' + key.lower()
            return label.lower() if len(label) > 1 else label
        def bound_keys(bindings):
            return {key.value if hasattr(key, 'value') else key
                    for binding in bindings.bindings
                    if binding.handler.__name__ != 'unknown_key'
                    for key in binding.keys
                    if (key.value if hasattr(key, 'value') else key) not in
                    {'up', 'down', 'left', 'right', 'pageup', 'pagedown', 'home', 'end'}}
        def documented(lines):
            return {normalized(entry.key) for entry in help_entries(lines, tui.plain_markup)}
        with tempfile.TemporaryDirectory() as directory:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            main_keys = documented(tui.main_help(0))
            self.assertEqual(bound_keys(browser.app.key_bindings) - main_keys, set())
            scanner = tui.ScannerView(browser, startup=False)
            scan_keys = documented(tui.SCANNER_HELP)
            self.assertEqual(bound_keys(scanner.keys) - scan_keys, set())
            shared = {'b', 'j', 'q', 'c-c', 'c-p', 'c-k', 'c-s',
                      's-left', 's-right', 's-home', 's-end', 's-pageup', 's-pagedown'}
            self.assertEqual(shared - scan_keys, set())
            for lines in (tui.main_help(0), tui.SCANNER_HELP):
                view = tui.HelpView(browser, 'Help', lines)
                self.assertEqual(bound_keys(view.keys) - documented(lines), set())
