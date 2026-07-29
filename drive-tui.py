#!python3

import os
from os.path import isfile, isdir, islink, join
from multiprocessing import Process, Manager, Value, Pool
from threading import Thread
from queue import Queue
from threading import Semaphore
import hashlib
import argparse
from time import perf_counter
import json
from pprint import pprint

from textual.app import App
from textual.widgets import Header, Footer, Button

from livelog import LiveLog
from livelog2 import LiveLog as LiveLog2

from drive import load_log

from vfs import VirtualFS, Node
from vfs import prefixes, disabled_prefixes, aliases # MapDrive
from vfs import format_size
from vfs import DriveActionsList

def load_llogs(files):

    start = perf_counter()

    right = {
        "hashes": {},
        "files": {},
        "file_types": {},
        "modified": {} # deleted, modified
    }
    i = 0
    for file in files:
        print(f'Loading {i}: {file}')
        load_log(right, file)
        i+=1

    elapsed = perf_counter() - start
    print(f"Loaded LLOG DB {len(files)} files in {elapsed:.3f} s")

    return right

# DEMO APP [

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static
from rich.table import Table

# from vfs import VirtualFS

data = {
    "files": {
        "test0/t0/fileA": {"MD5:c6f057b86584942e415435ffb1fa93d4:3"},
        "test0/t0/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
        "test0/t1/fileA": {"MD5:202cb962ac59075b964b07152d234b70:3"},
        "test0/t1/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
        "test0/t1/fileC": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
    }
}
from textual.widgets import ListItem, Label
from textual.containers import Horizontal, VerticalScroll

VFS = None

import pyperclip

def copy_text(text):
    pyperclip.copy(text)

from textual.scroll_view import ScrollView
from textual.strip import Strip
from rich.text import Text
from textual.geometry import Size
from rich.console import Console

from textual.widgets import DataTable

from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.widgets import Button, Label

# DRIVE ACTIONS VIEW [

driveActions = DriveActionsList()

class ActionsScreen(ModalScreen):
#    CSS = open("theme.css").read()

    CSS = """
    ActionsScreen Vertical {
        width: 80;
        height: 80%;
    }

    #actions {
        height: 1fr;
    }

    ActionsScreen Horizontal {
        height: auto;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("x", "clear", "clear"),
    ]

    def compose(self):
        with Vertical():
            yield Label("Queued actions")
            yield DataTable(id="actions")

            with Horizontal():
                yield Button("Close", id="close")
                yield Button("Clear", id="clear")
                yield Button("Export .sh", id="export")
                yield Button("Apply", id="apply")

    def on_mount(self):
        table = self.query_one("#actions", DataTable)
        #table.add_columns("Action")
        table.add_columns("Operation", "Path")
        table.cursor_type = "row"
        self.refresh_actions()

    def refresh_actions(self):
        table = self.query_one("#actions", DataTable)
        table.clear()

        #for action in driveActions.actions:
        #    table.add_row(str(action))

        for op, *args in driveActions.actions:
            table.add_row(op, " ".join(map(str, args)))

    def action_close(self):
        self.dismiss()

    def action_clear(self):
        driveActions.clear()
        self.refresh_actions()

    def on_button_pressed(self, event: Button.Pressed):
        match event.button.id:
            case "close":
                self.dismiss()

            case "clear":
                self.action_clear()

            case "export":
                self.app.notify("Export .sh")

            case "apply":
                self.app.notify("Apply")

# DRIVE ACTIONS VIEW ]

class DemoApp(App):
    TITLE = "DriveDB"
    SUB_TITLE = "File Manager"

#    CSS = open("theme.css").read()

    CSS = """
    Horizontal {
        height: 1fr;
    }

    #files {
        width: 45%;
        border: solid green;
    }

    #quick_scroll {
        width: 55%;
        border: solid blue;
    }

    #quick {
        height: 100%;
        width: 55%;
        border: solid blue;
        padding: 1;
    }
    """

    BINDINGS = [
#        ("ctrl+x", "test", "Test"),
        ("delete", "remove_file", "Remove file"),
        ("shift+delete", "remove_all", "Remove file and all clones"),
        ("a", "show_actions", "View Actions"),
#    ("delete", "remove_file", "Remove file"),
#    ("shift+delete", "remove_all", "Remove file and all clones"),
#    ("a", "actions", "Actions"),
#        ("ctrl+z", "undo", "Undo"),
        ("ctrl+x", "copy_text", "Copy"),
        ("escape", "back", "Parent"),
        ("q", "quit", "Quit"),
    ]


#    def action_test(self):
#        self.notify("CTRL-X WORKS")

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            yield ListView(id="files")
            yield DataTable(id="quick")

        yield Footer()

    # ACTIONS [

    def action_copy_text(self):
        text = self.query_one("#quick", Static).render()
        copy_text(str(text))

    # DIVE ACTIONS

    def action_remove_file(self):
        file = self.get_current_file()
        if file is None:
            return
        driveActions.append(["remove", file])
        self.notify(f"Remove {file}", timeout=0.5)

    def action_remove_all(self):
        file = self.get_current_file()

        if file is None:
            return

#        file.get
        driveActions.append(["remove", file])

        node = self.vfs.get_from_path(file)

        info = self.vfs.get_full_info(node)

        for dup in info["dups"]:
            driveActions.append(["remove", dup])

        self.notify(f"Remove all {file}")

    def action_show_actions(self):
        self.push_screen(ActionsScreen())

    # ACTIONS ]

    def get_current_file(self):
        focused = self.focused

        try:
            if focused and focused.id == "files":
                filesView = focused  # ListView
                index = filesView.index
                files = self.vfs.listdir()
                file = files[index] # need vfs.get_full_path(index)
                f = self.vfs.pwd() + '/' + file[0]
                return f
            elif focused and focused.id == "quick":
                quickView = focused  # DataTable
                index = quickView.cursor_row - self.quickData["line_dups"]
                info = self.quickData["info"]
                if index >= 0:
                    dups = info["dups"]
#                    dups_states = info["dups_states"]
                    return dups[index]
            else:
                index = None

        except:
            self.notify(f"BUG!")

        return None


    def on_mount(self):
#        self.add_class("theme-blue")

        self.vfs = VFS
        self.nav_stack = []  # Track directory history for mc-style restoration

#        files = self.query_one("#files", DataTable)
#        files.add_columns("Name", "Size", "Dup")

        quick = self.query_one("#quick", DataTable)
        quick.add_column("Info")
        self.refresh_list()


    def go_back(self):
        """Restores previous selection and scroll position like mc."""
        # Pop the name of the directory we are leaving
        target_name = self.nav_stack.pop() if self.nav_stack else None
        self.vfs.enter("..")
        self.refresh_list(target_name=target_name)

    def refresh_list(self, target_name: str | None = None):
        lv = self.query_one("#files", ListView)
        lv.clear()

        target_index = 0
        items = []

        for index, (name, is_dir) in enumerate(self.vfs.listdir()):
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(ratio=1, overflow="ellipsis", no_wrap=True)
            grid.add_column(justify="right")
            grid.add_column(justify="right")

            if is_dir:
                if name == '..':
                    node = self.vfs.get_cwd()
                else:
                    node = self.vfs.get(name)
                size = format_size(node.size, 0)
                grid.add_row(f"📁 {name}", "", size)
            else:
                node = self.vfs.get(name)

                file_hash = node.info['hashinfo']
                if isinstance(file_hash, set):
                    file_hash = next(iter(file_hash))

                size = format_size(node.size, 1)

                dup_count = len(self.vfs.get_hash_dups(file_hash))

                grid.add_row(
                    f"📄 {name}",
                    size,
                    f"({dup_count})"
                )

            item = ListItem(Static(grid))
            item.file_name = name
            items.append(item)

            if target_name and name == target_name:
                target_index = index

        lv.extend(items)

#        self.query_one("#quick").update(self.vfs.pwd())
        self.set_quick_text(self.vfs.pwd())

        def apply_selection():
            lv.focus()
            lv.index = target_index
            lv.scroll_to_widget(lv.children[target_index], animate=False)

        self.call_after_refresh(apply_selection)
        #self.query_one("#quick_scroll", VerticalScroll).scroll_home(animate=False)

    def on_list_view_selected(self, event: ListView.Selected):
        if event.list_view.id == "quick":
#            path = getattr(event.item, "file_path", None)
            return

        name = event.item.file_name

        if name == "..":
#            self.query_one("#quick").update(self.vfs.pwd())
            self.set_quick_text(self.vfs.pwd())
            self.go_back()
            return

        def apply_selection():

            self.go_back()
            return


        node = self.vfs.get(name)

        self.quickData = { # common for files and quick - need review
            "name": name,
            "node": node,
            "info": None,
            "line_dups": 0,
        }

        if node.is_dir:
            self.nav_stack.append(name)
            self.vfs.enter(name)
            self.refresh_list()
        else:
            file_hash = node.info['hashinfo']
            if isinstance(file_hash, set):
                file_hash = next(iter(file_hash))

            info = self.vfs.get_full_info(node)

            other_dups = info["dups"]
            dups_states = info["dups_states"]
            
            current_path = node.info['path']

            indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red] "

            if info["exists"]:
                pass

            other_dups = [
                f"{'[green]●[/green]' if state['exists'] else '[red]●[/red]'} {dup}"
                for dup, state in zip(info["dups"], dups_states)
            ]

            size_now = info.get("size", -1)
            size_suffix = ""
            if size_now > 0:
                if node.size != size_now:
                    size_suffix = f'[red]{size_now}[/red]'

            is_dir_s = "DIR" if info.get("is_dir", False) else ""
            is_file_s = "FILE" if info.get("is_file", False) else ""

            self.quickData["info"] = info
            self.quickData["line_dups"] = 9

#            rows.extend((path, path) for path in other_dups)

            rows = [
                f"{current_path}",                                  # line 0
                f"{indicator} {is_dir_s}{is_file_s}",               # line 1
                f"Name: {node.name}",                               # line 2
                f"Size: {format_size(node.size, 0)} {size_suffix}", # line 3
                f"Created: {info.get("created", "")}",              # line 4
                f"Modified: {info.get("modified", "")}",            # line 5
                file_hash,                                          # line 6
                "",                                                 # line 7
                f"Other Duplicates ({len(other_dups)}):",           # line 8
            ]
            # "is_dir": stat.S_ISDIR(st.st_mode),
            # "is_file": stat.S_ISREG(st.st_mode),
            # "created": st.st_ctime,
            # "modified": st.st_mtime,
            # "size": st.st_size,

            rows.extend((path, path) for path in other_dups)

            self.set_quick_rows(rows)

    def set_quick_text(self, text: str):
        self.set_quick_rows([text])

    def set_quick_rows(self, rows):
        quick = self.query_one("#quick", DataTable)

        quick.clear()

        for row in rows:
            if isinstance(row, tuple):
                quick.add_row(row[0])
            elif isinstance(row, dict):
                quick.add_row(row["text"])
            else:
                quick.add_row(str(row))

    def action_back(self):
        self.go_back()




# DEMO APP ]
# FIND LLOG FILES [

from pathlib import Path

def find_llog_files(root: str) -> list[Path]:
    """Return all llog-files.sh files under root."""
    return list(Path(root).rglob("llog-llogfiles.sh"))

# FIND LLOG FILES ]
# LOAD DB [

def load_db(scan_dirs):
    files = []
    for dir in scan_dirs:
        files.extend(find_llog_files(dir))

    return files

# LOAD DB ]

import shlex


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=('''Compare directories. Usage examples:
    drive-tui.py -d <path> # scan dirs for llog data files''')
    )
    parser.add_argument('-d', '--db', action='append', help='LLOG DB data path')
    parser.add_argument('-c', '--cache', help='Cache DB type: sqlite or redis')
    parser.add_argument('-b', '--build', action="store_true", help='Build cache from LLOG DB')

    try:
        args = parser.parse_args()
    except SystemExit as e:
        print(f"Error: Missing required arguments. Use `-h` for help.")
        exit(e.code)  # Exit with the same error code
    
#    if not args.file:
#        if not args.src:
#            parser.error('Need source path (-s)')
    
    # READ CONFIG [
    
    log2 = LiveLog2("config.sh")
    log2.load()

    # CONFIG MAP DRIVES

    try:
        map_drives = log2._tree._items["MAP DRIVES"]

        for line in map_drives._ss:
            parts  = shlex.split(line)

            if len(parts) < 2:
                continue

            alias = None

            if len(parts) >= 2:
                prefix = parts[0]
                local = os.path.expanduser(parts[1])
                alias = parts[0]
            if len(parts) >= 3:
                alias = parts[2]

            aliases[alias] = local

            if local == '0':
                disabled_prefixes[prefix] = prefix
            else:
                prefixes[prefix] = {'local': local, 'alias': alias}

            print(prefix, local, alias)
            #print(line)
    except:
        print("Can't read MAP DRIVE from config.sh")
        pass

    try:
        # CONFIG SETTINGS JSON
        settings_json = log2._tree._items["SETTINGS JSON"]

        settings = json.loads(settings_json.text)

        DB=settings["db"]

        print(f"Config DB: {DB}")

    except:
        print("Can't read SETTINGS JSON from config.sh")
        pass

    # READ CONFIG ]
    # LOAD LLOG DB [

    rebuild_db = False
    db_type="memory"
#    db_type="sqlite"
#    db_type="redis"
#    rebuild_db = True

    if args.cache:
        db_type = args.cache

    if args.build:
        rebuild_db = True

    db = None

    if db_type == "memory" or rebuild_db:
        scan_dirs = ['.']

        if args.db:
            scan_dirs = args.db

        files = load_db(scan_dirs)

        db = load_llogs(files)


    #    pprint(db)
    #    print(json.dumps(db["hashes"], indent=4))

        print(f"Total loaded {len(db['hashes'])} hashes and {len(db['files'])} files")
        print("DONE!")

    # LOAD LLOG DB ]

    VFS = VirtualFS(db, db_type, rebuild_db)

    # cleanup
    del db["files"]
    del db["hashes"]


    DemoApp().run()

