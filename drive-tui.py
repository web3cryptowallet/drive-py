#!/usr/bin/env python3

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
from pathlib import Path
import shlex

from textual.app import App
from textual.theme import Theme
from textual.widgets import Header, Footer, Button

from livelog import LiveLog
from livelog2 import LiveLog as LiveLog2

from drive import load_log

from vfs import VirtualFS, Node
from vfs import prefixes, disabled_prefixes, aliases # MapDrive
from vfs import format_size, normalize_path, get_stat_info

from views import ActionsScreen, driveActions

from datetime import datetime

# DRIVE DB [
# LOAD ALL LOGS INTO MEMORY [

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

# LOAD ALL LOGS INTO MEMORY ]
# STREAM LOGS INTO SQLITE ONE AT A TIME [

def load_lite(files, rebuild_db=False, **db_kwargs):
    """Load logs into SQLite with at most one parsed log held in memory."""
    start = perf_counter()
    fs = VirtualFS(None, 'sqlite', **db_kwargs)
    try:
        if rebuild_db:
            fs.db.rebuild_db()
            fs.cwd = fs.db.get_root()
            
        for index, file in enumerate(files):
            # PARSE COMMIT AND RELEASE A SINGLE LOG [

            print(f'Loading {index}: {file}')
            right = {'hashes': {}, 'files': {}, 'file_types': {}, 'modified': {}}
            load_log(right, file)
            fs.update(right)
            del right

            # PARSE COMMIT AND RELEASE A SINGLE LOG ]

        print(f"Loaded SQLite logs in {perf_counter() - start:.3f} s")
        return fs
    except BaseException:
        fs.db.conn.close()
        raise


# STREAM LOGS INTO SQLITE ONE AT A TIME ]
# DRIVE DB ]
# DEMO APP [

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Label, Static

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
from textual.widgets import Label
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


class DemoApp(App):
    TITLE = "drive.py"
    SUB_TITLE = "file manager"

    CSS = """
    Horizontal {
        height: 1fr;
    }

    #files {
        height: 100%;
        width: 50%;
        border: solid green;
    }

    #quick_scroll {
        width: 50%;
        border: solid blue;
    }

    #quick {
        height: 100%;
        width: 50%;
        border: solid blue;
        padding: 1;
    }

    .-theme-mc-blue #files, .-theme-mc-blue #quick {
        border: solid #55ffff;
    }

    .-theme-mc-blue DataTable > .datatable--header {
        background: #0000aa;
        color: #ffff55;
        text-style: bold;
    }

    .-theme-mc-default #files, .-theme-mc-default #quick {
        border: solid #d0cfcc;
    }

    .-theme-mc-default Header {
        background: #06989a;
        color: #2e3436;
    }

    .-theme-mc-default DataTable > .datatable--header {
        background: #3465a4;
        color: #ffff55;
        text-style: bold;
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
        ("t", "switch_theme", "Theme"),
        ("q", "quit", "Quit"),
    ]


#    def action_test(self):
#        self.notify("CTRL-X WORKS")

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            yield DataTable(id="files", cursor_type="row", show_row_labels=False,
                            cursor_foreground_priority="renderable")
            yield DataTable(id="quick", cursor_foreground_priority="renderable")

#        from textual.app import App, ComposeResult
#        from textual_image.widget import Image
#        yield Image("assets/console-1.png")


        yield Footer()

    def show_image(self, filename):
        from PIL import Image

#        img = Image.open("assets/console-1.png")
        img = Image.open(filename)
        img.show()


    # ACTIONS [

    def action_switch_theme(self):
        themes = ("mc-default", "mc-blue", "textual-dark")
        labels = ("MC Default", "MC Blue", "Textual Dark")
        index = (themes.index(self.theme) + 1) % len(themes) if self.theme in themes else 0
        self.theme = themes[index]
        self.notify(f"Theme: {labels[index]}", timeout=1)

    def action_copy_text(self):
        text = self.query_one("#quick", Static).render()
        copy_text(str(text))

    # DIVE ACTIONS

    # ACTION REMOVE FILE [

    def action_remove_file(self):
        file = self.get_current_file()
        if file is None:
            return
        driveActions.append(["remove", file])
        self.notify(f"Remove {file}", timeout=0.5)

    # ACTION REMOVE FILE ]
    # ACTION REMOVE ALL FILES [

    total_removed_files = 0
    total_removed_dirs = 0

    def action_remove_all(self):
        file = self.get_current_file()

        if file is None:
            return

        if os.path.basename(file) == '..':
            return

        self.total_removed_files = 0
        self.total_removed_dirs = 0

        self.remove_all_files(file)

        self.notify(f"Remove {self.total_removed_dirs} dirs {self.total_removed_files} files {file}")

    # Remove 100,000 files max
    def remove_all_files(self, file):
        if self.total_removed_files >= 100_000:
            return
        
        driveActions.append(["remove", file])

        node = self.vfs.get_from_path(file)

        if node.is_dir:
            self.total_removed_dirs += 1

            files = self.vfs.listdir(node)

            for name, is_dir in files:
                if name == '..':
                    continue
                path = file + '/' + name
                self.remove_all_files(path)
        else:
            self.total_removed_files += 1

            info = self.vfs.get_full_info(node)

            for dup in info["dups"]:
                driveActions.append(["remove", dup])
                self.total_removed_files += 1

    # ACTION REMOVE ALL FILES ]

    def action_show_actions(self):
        self.push_screen(ActionsScreen())

    # ACTIONS ]

    def get_current_file(self):
        focused = self.focused

        try:
            if focused and focused.id == "files":
                filesView = focused  # DataTable
                if not filesView.row_count:
                    return None
                row_key = filesView.coordinate_to_cell_key(filesView.cursor_coordinate).row_key
                f = self.vfs.pwd() + '/' + row_key.value
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
        self.register_theme(Theme(
            name="mc-default",
            primary="#06989a",
            secondary="#06989a",
            accent="#ffff55",
            foreground="#eeeeec",
            background="#3465a4",
            surface="#12488b", # panel colors
            panel="#3465a4",
            dark=True,
            variables={
                "block-cursor-background": "#06989a",
                "block-cursor-foreground": "#2e3436",
                "block-cursor-text-style": "bold",
                "block-cursor-blurred-background": "#06989a",
                "block-cursor-blurred-foreground": "#2e3436",
                "footer-background": "#06989a",
                "footer-key-background": "#2e3436",
                "footer-description-background": "#06989a",
                "footer-key-foreground": "#eeeeec",
                "footer-description-foreground": "#2e3436",
            },
        ))
        self.register_theme(Theme(
            name="mc-blue",
            primary="#00aaaa",
            secondary="#00aaaa",
            accent="#ffff55",
            foreground="#ffffff",
            background="#0000aa",
            surface="#0000aa",
            panel="#0000aa",
            dark=True,
            variables={
                "block-cursor-background": "#00aaaa",
                "block-cursor-foreground": "#000000",
                "block-cursor-text-style": "bold",
                "block-cursor-blurred-background": "#008080",
                "block-cursor-blurred-foreground": "#ffffff",
                "footer-background": "#0000aa",
                "footer-key-foreground": "#ffff55",
                "footer-description-foreground": "#ffffff",
            },
        ))
        self.theme = "mc-default"

        self.vfs = VFS
        self.nav_stack = []  # Track directory history for mc-style restoration

        files = self.query_one("#files", DataTable)
        files.add_columns("Name", "Size", "Files / Dups")

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
        files = self.query_one("#files", DataTable)
        files.clear()

        target_index = 0
        for index, (name, is_dir) in enumerate(self.vfs.listdir()):

            if is_dir:
                if name == '..':
                    node = self.vfs.get_cwd()
                else:
                    node = self.vfs.get(name)
                size = format_size(node.size, 0)

                info = self.vfs.get_full_info(node, True)

                indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red]"

                total_files = f"({node.total_files})"

                label = Text.from_markup(f"{indicator} 📁 ")
                label.append(name)
                files.add_row(label, Text(size, justify="right"),
                              Text(total_files, justify="right"), key=name)
            else:
                node = self.vfs.get(name)

                info = self.vfs.get_full_info(node, True)

                file_hash = node.info['hashinfo']
                if isinstance(file_hash, set):
                    file_hash = next(iter(file_hash))

                size = format_size(node.size, 1)

                dup_count = len(self.vfs.get_hash_dups(file_hash))

                indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red]"

                label = Text.from_markup(f"{indicator} 📄 ")
                label.append(name)
                files.add_row(label, Text(size, justify="right"),
                              Text(f"({dup_count})", justify="right"), key=name)

            if target_name and name == target_name:
                target_index = index

        def apply_selection():
            files.focus()
            if files.row_count:
                files.move_cursor(row=target_index, column=0, animate=False)

        self.call_after_refresh(apply_selection)
        #self.query_one("#quick_scroll", VerticalScroll).scroll_home(animate=False)

        # UPDATE QUICK VIEW [
        
        dir = self.vfs.pwd()

        if dir != '/':
            # DEFAULT
            self.set_quick_text(dir)

            node = self.vfs.get_cwd()
            info = self.vfs.get_full_info(node)

            indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red]"

            #t = info['created']

            rows = [
                f"{dir}",                                           # line 1
                f"{indicator} ",                                    # line 2
                f"Size: {format_size(node.size, 0)}",               # line 3
#                f"Created: {info.get("created", "")}",              # line 4
#                f"Modified: {info.get("modified", "")}",            # line 5
                f"Created:  {datetime.fromtimestamp(info['created']).strftime('%Y-%m-%d %H:%M:%S') if info.get('created') else ''}",
                f"Modified: {datetime.fromtimestamp(info['modified']).strftime('%Y-%m-%d %H:%M:%S') if info.get('modified') else ''}",            
            ]
            
            self.set_quick_rows(rows)

        else:
            # ADD LEGEND

            rows = [
                f"{dir}",                                           # line 0
                "[bold cyan]╭────────╮  drive.py v0.98[/bold cyan]",
                "[bold cyan]│ ━━━━ ● │[/bold cyan]  [bold]File Manager[/bold]",
                "[bold cyan]╰────────╯[/bold cyan]  [dim]Explore • Compare • Keep[/dim]",
                f"",                                                # line 1
                f"Legend:",                                         # line 2
                f"[green]●[/green] Avaible",
                f"[red]●[/red] Not found",
                f"[yellow]●[/yellow] Maybe it's available. It was available last time",
                f"[red]R[/red] In remove queue",
                f"[red]D[/red] Deleted",
                f"",
                f"Help / Shortcuts:",
                f"[yellow]Enter[/yellow]: Open directory or view file info",
                f"[yellow]Esc[/yellow]: Go back up to the parent directory",
                f"[yellow]Ctrl + X[/yellow]: Copy info panel text to clipboard",
                f"[yellow]t[/yellow]: Cycle MC Default, MC Blue, and Textual Dark themes",
                f"[yellow]q[/yellow]: Quit the application",
                f"",
                f"File Removal (Queue):",
                f"[yellow]Del[/yellow]: Queue the selected file for removal",
                f"[yellow]Shift + Del[/yellow]: Queue file and all duplicates for removal",
                f"",
                f"Action Queue:",
                f"[yellow]a[/yellow]: Open the Actions screen to review operations",
                f"[yellow]x[/yellow]: Clear the entire queue (inside Actions)",
                f"[yellow]e[/yellow]: export to apply/drive*.sh",
                f"[yellow]Ctrl+Enter[/yellow]: Apply",
            ]

            self.set_quick_rows(rows)



        # UPDATE QUICK VIEW ]

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id != "files":
            return

        name = event.row_key.value

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
            #dups_states = info["dups_states"]
            
            current_path = node.info['path']

            indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red]"

            if info["exists"]:
                pass

            # other_dups = [
            #     f"{'[green]●[/green]' if state['exists'] else '[red]●[/red]'} {dup}"
            #     for dup, state in zip(info["dups"], dups_states)
            # ]

            size_now = info.get("size", -1)
            size_suffix = ""
            if size_now > 0:
                if node.size != size_now:
                    size_suffix = f'[red]{size_now}[/red]'

            is_dir_s = "DIR" if info.get("is_dir", False) else ""
            is_file_s = "FILE" if info.get("is_file", False) else ""

            # DUPS [

            other_dups = [
                f"{'[green]●[/green]' if state['exists'] else '[red]●[/red]'} {dup}"
                for dup, state in zip(info["dups"], info["dups_states"])
            ]

            # DUPS ]

            self.quickData["info"] = info
            self.quickData["line_dups"] = 9

            rows = [
                f"{current_path}",                                  # line 0
                f"{indicator} {is_dir_s}{is_file_s}",               # line 1
                f"Name: {node.name}",                               # line 2
                f"Size: {format_size(node.size, 0)} {size_suffix}", # line 3
                f"Created:  {datetime.fromtimestamp(info['created']).strftime('%Y-%m-%d %H:%M:%S') if info.get('created') is not None else ''}", # line 4
                f"Modified: {datetime.fromtimestamp(info['modified']).strftime('%Y-%m-%d %H:%M:%S') if info.get('modified') is not None else ''}", # line 5
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

#    processing = False

    def action_back(self):
#        if self.processing:
#            self.processing = 0
#            return

        self.go_back()




# DEMO APP ]
# FIND LLOG FILES [

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



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=('''Compare directories. Usage examples:
    drive-tui.py -d <path> # scan dirs for llog data files''')
    )
    parser.add_argument('-d', '--db', action='append', help='LLOG DB data path')
    parser.add_argument('-c', '--cache', help='Cache DB type: sqlite or redis')
    cache_mode = parser.add_mutually_exclusive_group()
    cache_mode.add_argument('-b', '--build', '--rebuild', action="store_true",
                            help='Rebuild cache from LLOG DB')
    cache_mode.add_argument('-u', '--update', action="store_true",
                            help='Update SQLite cache one log at a time without rebuilding (requires -c sqlite)')

    args = parser.parse_args()
    if args.update and args.cache != 'sqlite':
        parser.error('-u/--update requires -c sqlite')
    
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
    # LOAD LOGS USING STREAMING SQLITE OR IN MEMORY STORAGE [

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

    if db_type == "memory" or rebuild_db or args.update:
        scan_dirs = ['.']

        if args.db:
            scan_dirs = args.db

        files = load_db(scan_dirs)

        if db_type == 'sqlite':
            VFS = load_lite(files, rebuild_db=rebuild_db)
            if not VFS.db.get_root() or not VFS.db.get_children(VFS.db.get_root()):
                VFS.db.conn.close()
                print("NO FILES FOUND!")
                exit(1)
        else:
            db = load_llogs(files)


    #    pprint(db)
    #    print(json.dumps(db["hashes"], indent=4))

        if db is not None:
            print(f"Total loaded {len(db['hashes'])} hashes and {len(db['files'])} files")
            print("DONE!")
            if len(db['files']) == 0:
                print("NO FILES FOUND!")
                exit(1)

    if VFS is None:
        VFS = VirtualFS(db, db_type, rebuild_db)

    # cleanup
    if db:
        del db["files"]
        del db["hashes"]

    # LOAD LOGS USING STREAMING SQLITE OR IN MEMORY STORAGE ]

    DemoApp().run()
