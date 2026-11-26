"""Loaded drive configuration is inspectable without changing its mappings."""
import asyncio
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prompt_toolkit.input import create_pipe_input, DummyInput
from prompt_toolkit.output import DummyOutput
from vfs import VirtualFS

spec = importlib.util.spec_from_file_location('mapping_tui', Path(__file__).resolve().parents[1] / 'drive-tui.py')
tui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tui)


class DriveMappingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_o_opens_loaded_mappings_and_closes(self):
        with tempfile.TemporaryDirectory() as directory, create_pipe_input() as pipe, \
                patch.dict(tui.aliases, {'disk': directory, 'offline': '0'}, clear=True), \
                patch.dict(tui.prefixes, {'/source': {'alias': 'disk', 'local': directory}}, clear=True), \
                patch.dict(tui.disabled_prefixes, {'/disabled': '/disabled'}, clear=True), \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=pipe, output=DummyOutput())
            before = dict(tui.aliases), dict(tui.prefixes), dict(tui.disabled_prefixes)
            task = asyncio.create_task(browser.app.run_async(set_exception_handler=False))
            try:
                await asyncio.sleep(.04)
                pipe.send_text('o')
                await asyncio.sleep(.04)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.DriveMappingsView)
                text = '\n'.join(''.join(value for _, value in row) for row in view.lines)
                self.assertIn('disk · /source → ' + directory, text)
                self.assertIn('offline · — → 0 · disabled', text)
                self.assertIn('Disabled source prefix: /disabled', text)
                self.assertIn(browser.startup_path, text)
                self.assertEqual((dict(tui.aliases), dict(tui.prefixes), dict(tui.disabled_prefixes)), before)
                pipe.send_text('o')
                await asyncio.sleep(.04)
                self.assertFalse(browser.screen_stack)
            finally:
                browser.app.exit()
                await task

    def test_empty_mappings(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(tui.aliases, {}, clear=True), patch.dict(tui.prefixes, {}, clear=True), \
                patch.dict(tui.disabled_prefixes, {}, clear=True), \
                patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
            browser = tui.DriveBrowser(VirtualFS({'files': {}}), path=directory,
                                       input=DummyInput(), output=DummyOutput())
            view = tui.DriveMappingsView(browser)
            self.assertTrue(any('No drive mappings' in value for row in view.lines for _, value in row))
