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

# VIRTUAL FS [

from dataclasses import dataclass, field


@dataclass
class Node:
    name: str
    is_dir: bool
    parent: "Node | None" = None
    children: dict[str, "Node"] = field(default_factory=dict)
    info: dict | None = None
    size: int = 0

def check_disabled_prefixes(prefix):
    for prefix in disabled_prefixes:
        if path.startswith(prefix):
            return True
    return False

def normalize_path(path):
    parts = path.replace("//", "/").lstrip("/").rstrip("/").split("/")

    path = "/".join(parts)

    return (path, parts) 

# UPDATE PREFIX [

def path_update_prefix(path):
    for prefix in prefixes:
        new_prefix = prefixes[prefix]['local']
        new_prefix = prefixes[prefix]['alias']
        if path.startswith(prefix):
            path = new_prefix + path[len(prefix):]
            break
    return path

aliases = {}

def get_real_path(path):
    _, parts = normalize_path(path)
    alias = aliases.get(parts[0])
    if alias:
        parts[0] = alias
        path = '/'.join(parts)

    return path

# UPDATE PREFIX ]

import os
import stat

def get_stat_info(dup):
    try:
        p = get_real_path(dup)
        st = os.stat(p)
        return {
            "exists": True,
            "is_dir": stat.S_ISDIR(st.st_mode),
            "is_file": stat.S_ISREG(st.st_mode),
            "created": st.st_ctime,
            "modified": st.st_mtime,
            "size": st.st_size,
        }
    except FileNotFoundError:
        return {
            "exists": False,
        }

class VirtualFS:
    def __init__(self, data):
        self.root = Node("", True)
        self.data = data
        self.cwd = self.root
        self._build(data["files"])

    def _build(self, files):
        print("VFS: Building..")

        total_dirs = 0
        total_files = 0
        total_size = 0

        for path, hashes in files.items():

#            # CHECK DISABLED [
#
#            if (check_disabled_prefixes(prefix)):
#                continue
#
#            # CHECK DISABLED ]

            path = path_update_prefix(path)

            path, parts = normalize_path(path)
            
            total_files += 1

            if total_files % 100000 == 0:
                print(f'{total_files}/{len(files)} files')

            hashinfo = next(iter(hashes))
            md5, size = hashinfo.rsplit(":", 1)

            size = int(size)

            cur = self.root

            for part in parts[:-1]:
                if part not in cur.children:
                    cur.children[part] = Node(part, True, parent=cur)
                    total_dirs += 1
                cur.children[part].size += size
                cur = cur.children[part]

            total_size += size

            cur.children[parts[-1]] = Node(
                name=parts[-1],
                is_dir=False,
                parent=cur,
                info={
                    "path": path,
                    "hashinfo": hashinfo, 
                    "hash": md5,
                },
                size = size,
            )
        print(f"VFS: built {total_dirs} dirs and {total_files} files {format_size(total_size, 0)}")

    def pwd(self):
        node = self.cwd
        parts = []
        while node.parent:
            parts.append(node.name)
            node = node.parent
        return "/" + "/".join(reversed(parts))

    def listdir(self):
        result = []

        if self.cwd.parent:
            result.append(("..", True))

        dirs = []
        files = []

        for node in self.cwd.children.values():
            if node.is_dir:
                dirs.append(node)
            else:
                files.append(node)

        dirs.sort(key=lambda n: n.name)
        files.sort(key=lambda n: n.name)

        for n in dirs:
            result.append((n.name, True))

        for n in files:
            result.append((n.name, False))

        return result

    def enter(self, name):
        if name == "..":
            if self.cwd.parent:
                self.cwd = self.cwd.parent
            return

        node = self.cwd.children[name]

        if node.is_dir:
            self.cwd = node

    def get_cwd(self):
        return self.cwd

    def get(self, name):
        if name == "..":
            return self.cwd.parent
        return self.cwd.children[name]


    def get_full_info(self, node):
        # 1. Get all paths sharing this hash (defaults to empty set if not found)
        file_hash = node.info['hashinfo']
        all_dups = self.data['hashes'].get(file_hash, set())
        
        # 2. Filter out the current file's path
        current_path = node.info['path']

        dups = [p for p in map(lambda x: path_update_prefix('/' + normalize_path(x)[0]), all_dups) if p != current_path]

        dups_states = []

        for dup in dups:
            dups_states.append(get_stat_info(dup))

        info = get_stat_info(current_path)
        info["dups"] = dups
        info["dups_states"] = dups_states

        return info

# VIRTUAL FS ]
# VIRTUAL FS TEST [

def test_vfs():
    data = {
        "files": {
            "test0/t0/fileA": {"MD5:c6f057b86584942e415435ffb1fa93d4:3"},
            "test0/t0/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileA": {"MD5:202cb962ac59075b964b07152d234b70:3"},
            "test0/t1/fileB": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
            "test0/t1/fileC": {"MD5:d41d8cd98f00b204e9800998ecf8427e:0"},
        }
    }

    vfs = VirtualFS(data)

    print(vfs.pwd())
    print(vfs.listdir())

    vfs.enter("test0")
    print(vfs.listdir())

    vfs.enter("t1")
    print(vfs.listdir())

    file = vfs.get("fileC")
    print(file.info)

# VIRTUAL FS TEST ]
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

def format_size(size, type):
    if size is None:
        return "N/A"

    if type == 0:
        units = ["bytes", "KB", "MB", "GB", "TB"]
    else:
        units = ["", "KB", "MB", "GB", "TB"]

    size = float(size)

    for unit in units:
        if size < 1024:
            return f"{round(size)} {unit}"
        size /= 1024

    return f"{round(size)} PB"

from textual.scroll_view import ScrollView
from textual.strip import Strip
from rich.text import Text
from textual.geometry import Size
from rich.console import Console

from textual.widgets import DataTable

class DemoApp(App):
    TITLE = "DriveDB"
    SUB_TITLE = "File Manager"

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
        ("ctrl+x", "copy_text", "Copy"),
        ("escape", "back", "Parent"),
        ("q", "quit", "Quit"),
    ]


#    def action_test(self):
#        self.notify("CTRL-X WORKS")

    def action_copy_text(self):
        text = self.query_one("#quick", Static).render()
        copy_text(str(text))

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            yield ListView(id="files")
            yield DataTable(id="quick")

        yield Footer()

    def on_mount(self):
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

                dup_count = len(self.vfs.data['hashes'].get(file_hash, []))

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

            rows = [
                f"{current_path}",
                f"{indicator} {is_dir_s}{is_file_s}",
                f"Name: {node.name}",
                f"Size: {format_size(node.size, 0)} {size_suffix}",
                f"Created: {info.get("created", "")}",
                f"Modified: {info.get("modified", "")}",
                file_hash,
                "",
                f"Other Duplicates ({len(other_dups)}):",
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

disabled_prefixes = {}
prefixes = {}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description=('''Compare directories. Usage examples:
    drive-tui.py -d <path> # scan dirs for llog data files''')
    )
    parser.add_argument('-d', '--db', action='append', help='LLOG DB data path')

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

        for node in llog2._tree._items_index:
            print("#", node.name, "count", len(node._ss))
    #        print(node.text)
            for line in node._ss:
                pass
    except:
        print("Can't read SETTINGS JSON from config.sh")
        pass

    # READ CONFIG ]
    # LOAD LLOG DB [

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

    data = db

    VFS = VirtualFS(data)

    # cleanup
    del data["files"]
#    del data["hashes"]


    DemoApp().run()

