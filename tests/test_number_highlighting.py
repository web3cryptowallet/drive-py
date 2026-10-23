"""Final-cell highlighting preserves layout, backgrounds and widget contents."""
# IMPORT TEST NUMBER HIGHLIGHTING DEPENDENCIES [
import importlib.util
from pathlib import Path
import unittest

from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Char, Screen, WritePosition
from prompt_toolkit.widgets import TextArea
# IMPORT TEST NUMBER HIGHLIGHTING DEPENDENCIES ]
# PREPARE TEST NUMBER HIGHLIGHTING SHARED STATE [
spec = importlib.util.spec_from_file_location('number_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)
# PREPARE TEST NUMBER HIGHLIGHTING SHARED STATE ]
# VERIFY NUMBER HIGHLIGHT BEHAVIOR [
class NumberHighlightTests(unittest.IsolatedAsyncioTestCase):
    # VERIFY NUMBERS UNITS AND ORIGINAL STYLES [
    def test_numbers_units_and_original_styles(self):
        text = '界 file42: 40 MB · 1.25 GiB/s · 99% · 2026-10-17 · 01:23 · abc'
        screen = Screen()
        for column, char in enumerate(text):
            screen.data_buffer[0][column] = Char(char, 'bg:#123456 bold')
        tui.NumberHighlight.highlight(screen)
        self.assertEqual(''.join(cell.char for cell in screen.data_buffer[0].values()), text)
        for part in ['42', '40 MB', '1.25 GiB/s', '99%', '2026-10-17', '01:23']:
            start = text.index(part)
            for column in range(start, start + len(part)):
                if text[column].isdigit():
                    self.assertIn('fg:#ffd700', screen.data_buffer[0][column].style)
        for unit in ['MB', 'GiB/s', '%']:
            start = text.index(unit)
            for column in range(start, start + len(unit)):
                self.assertNotIn('fg:#ffd700', screen.data_buffer[0][column].style)
        self.assertEqual(screen.data_buffer[0][0].style, 'bg:#123456 bold')
        self.assertTrue(all(cell.style.startswith('bg:#123456 bold')
                            for cell in screen.data_buffer[0].values()))
        self.assertNotIn('fg:#ffd700', screen.data_buffer[0][text.index('abc')].style)
    # VERIFY NUMBERS UNITS AND ORIGINAL STYLES ]
    # VERIFY FINAL RENDER INCLUDES WIDGETS AND DEFERRED WINDOWS [
    async def test_final_render_includes_widgets_and_deferred_windows(self):
        field = TextArea(text='40 MB', height=1)
        wrapped = tui.NumberHighlight(HSplit([
            Window(FormattedTextControl([('fg:red', '123 files')]), height=1, z_index=5),
            field,
        ]))
        layout = Layout(wrapped, focused_element=field)
        self.assertIn(field.window, list(layout.find_all_windows()))
        screen = Screen()
        wrapped.write_to_screen(screen, MouseHandlers(), WritePosition(0, 0, 40, 2), '', True, None)
        screen.draw_all_floats()
        for row, length in [(0, 3), (1, 2)]:
            for column in range(length):
                self.assertIn('fg:#ffd700', screen.data_buffer[row][column].style)
        self.assertEqual(field.text, '40 MB')
    # VERIFY FINAL RENDER INCLUDES WIDGETS AND DEFERRED WINDOWS ]
    # VERIFY LITERAL NAMES AND COMPLETE HASH [
    def test_literal_names_and_complete_hash(self):
        from prompt_toolkit.document import Document
        screen = Screen()
        text = 'photo40 MB.png 40 MB abcdef0123456789'
        for column, char in enumerate(text):
            style = ('class:literal' if column < 14 else
                     'class:hash' if column >= 21 else '')
            screen.data_buffer[0][column] = Char(char, style)
        tui.NumberHighlight.highlight(screen)
        self.assertTrue(all('fg:#ffd700' not in screen.data_buffer[0][i].style for i in range(14)))
        self.assertTrue(all('fg:#ffd700' in screen.data_buffer[0][i].style for i in range(15, 17)))
        self.assertTrue(all('fg:#ffd700' in screen.data_buffer[0][i].style for i in range(21, len(text))))
        lexer = tui.InfoLexer()
        lexer.hash_lines = {3}
        lexer.colors = {4: 'green'}
        line = lexer.lex_document(Document('/disk42/file9\nName: file9\nSize: 40 MB\nMD5:abcdef1234:40\n● /disk42/file9'))
        self.assertIn('class:literal', line(0)[0][0])
        self.assertIn('class:literal', line(1)[0][0])
        self.assertNotIn('class:literal', line(2)[0][0])
        self.assertIn('class:hash', line(3)[0][0])
        self.assertIn('class:literal', line(4)[1][0])
    # VERIFY LITERAL NAMES AND COMPLETE HASH ]
# VERIFY NUMBER HIGHLIGHT BEHAVIOR ]
