"""Loaded drive configuration is inspectable without changing its mappings."""
import asyncio
import os
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
    async def test_f7_opens_loaded_mappings_and_closes(self):
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
                pipe.send_text('\x1b[18~')
                await asyncio.sleep(.04)
                view = browser.screen_stack[-1][0]
                self.assertIsInstance(view, tui.DriveMappingsView)
                text = '\n'.join(''.join(value for _, value in row) for row in view.lines)
                self.assertIn('disk · /source → ' + directory, text)
                self.assertIn('offline · — → 0 · disabled', text)
                self.assertIn('Disabled source prefix: /disabled', text)
                self.assertIn(browser.startup_path, text)
                self.assertIn('~0:/ → ' + os.path.expanduser('~'), text)
                self.assertIn(':/ → /', text)
                self.assertIn(('class:green class:literal', directory), [part for row in view.lines for part in row])
                for prefix in ('@:', '~0:/', ':/'):
                    self.assertIn(('ansicyan bold class:literal', prefix), [part for row in view.lines for part in row])
                self.assertEqual((dict(tui.aliases), dict(tui.prefixes), dict(tui.disabled_prefixes)), before)
                pipe.send_text('\x1b[18~')
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

    def test_home_namespace_storage_and_resolution(self):
        from vfs.paths import catalog_source_path, catalog_identity_path, get_real_path
        with patch.dict(tui.aliases, {}, clear=True), patch.dict(tui.prefixes, {}, clear=True):
            self.assertEqual(catalog_source_path('~/media'), '/~0:/media')
            self.assertEqual(catalog_identity_path('~/media'), '/~0:/media')
            self.assertEqual(get_real_path('/~0:/media'), os.path.expanduser('~/media'))
            self.assertEqual(tui.normalize_bookmark_path('~/media'), '/~0:/media')
            with tempfile.TemporaryDirectory() as directory, patch.object(tui, 'HISTORY_PATH', Path(directory) / 'history.llog'):
                browser = tui.DriveBrowser(VirtualFS({'files': {}}), input=DummyInput(), output=DummyOutput())
                self.assertEqual(browser.parse_display_path('@:media'), '/~:/media')
                self.assertEqual(get_real_path('@:media'), os.path.join(os.getcwd(), 'media'))
                browser.startup_path = directory
                browser.show_path_prefixes = True
                self.assertEqual(browser.display_path('~/media'), '~0:/media')
                self.assertEqual(browser.parse_display_path('~0:/media'), '/~0:/media')

    def test_home_alias_and_disk_routes_share_catalog_identity(self):
        from vfs.paths import get_real_path
        with tempfile.TemporaryDirectory() as directory, patch.dict(tui.aliases, {'root': directory}, clear=True), patch.object(tui.os.path, 'expanduser', wraps=tui.os.path.expanduser) as expand:
            original = expand._mock_wraps
            expand.side_effect = lambda value: directory if value == '~' else original(value)
            Path(directory, 'media').mkdir()
            Path(directory, 'media/file').write_text('hello')
            fs = VirtualFS({'files': {'/root/media/file': {'hash:5'}}})
            routes = ['/root/media/file', '/~0:/media/file', '/:' + directory + '/media/file', directory + '/media/file']
            nodes = [fs.get_from_path(path) for path in routes]
            self.assertEqual({node.id for node in nodes}, {'/root/media/file'})
            self.assertTrue(all(node.info.get('hashinfo') == 'hash:5' for node in nodes))
            disk_parent = fs.get_from_path('/:' + str(Path(directory).parent))
            home = next(node for node in fs.list_nodes(disk_parent) if node.name == Path(directory).name)
            self.assertEqual(home.id, '/root')
            self.assertEqual(get_real_path(home.id), directory)
            fs.cwd = home
            fs.enter('..')
            self.assertEqual(get_real_path(fs.pwd()), str(Path(directory).parent))
            for route in ('/root', '/~0:'):
                fs.cwd = fs.get_from_path(route)
                fs.enter('..')
                self.assertEqual(fs.pwd(), '/')
            for route in ('/:' + directory, directory):
                fs.cwd = fs.get_from_path(route)
                fs.enter('media')
                fs.enter('..')
                self.assertEqual(fs.cwd.id, '/root')
                fs.enter('..')
                self.assertEqual(get_real_path(fs.pwd()), str(Path(directory).parent))
            with patch.dict(tui.aliases, {}, clear=True):
                for route in ('/:' + directory, directory):
                    fs.cwd = fs.get_from_path(route)
                    fs.enter('media')
                    fs.enter('..')
                    fs.enter('..')
                    self.assertEqual(get_real_path(fs.pwd()), str(Path(directory).parent))
            top = fs.list_nodes(fs.db.get_root())
            self.assertNotIn('tmp', [node.name for node in top])
