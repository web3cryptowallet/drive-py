"""Terminal color capabilities and explicit overrides reach the application."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import ColorDepth, DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('color_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class TerminalColorTests(unittest.TestCase):
    def test_application_uses_terminal_capabilities(self):
        cases = [
            ({'TERM_PROGRAM': 'Apple_Terminal'}, ColorDepth.DEPTH_8_BIT),
            ({'TERM_PROGRAM': 'Apple_Terminal', 'COLORTERM': 'truecolor'}, ColorDepth.DEPTH_8_BIT),
            ({'TERM_PROGRAM': 'iTerm.app', 'COLORTERM': 'truecolor'}, ColorDepth.DEPTH_24_BIT),
            ({'COLORTERM': '24bit'}, ColorDepth.DEPTH_24_BIT),
            ({}, None),
            ({'TERM_PROGRAM': 'Apple_Terminal', 'PROMPT_TOOLKIT_COLOR_DEPTH': 'DEPTH_24_BIT'}, ColorDepth.DEPTH_24_BIT),
            ({'COLORTERM': 'truecolor', 'NO_COLOR': '1'}, ColorDepth.DEPTH_1_BIT),
        ]
        for environment, expected in cases:
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True), create_pipe_input() as pipe:
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), input=pipe, output=DummyOutput())
                self.assertEqual(browser.app._color_depth, expected)

    def test_white_theme_cycle_and_readable_rows(self):
        with create_pipe_input() as pipe:
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), input=pipe, output=DummyOutput())
            for _ in range(3):
                browser.cycle_theme()
            style = browser.style()
            for name in ('', 'class:files-pane', 'class:info-pane'):
                attrs = style.get_attrs_for_style_str(name)
                self.assertEqual(attrs.bgcolor, 'ffffff')
                self.assertEqual(attrs.color, '202020')
            self.assertEqual(style.get_attrs_for_style_str('class:white').color, '202020')
            self.assertEqual(style.get_attrs_for_style_str('class:scan-input').color, '202020')
            browser.cycle_theme()
            self.assertEqual(browser.theme, 0)
