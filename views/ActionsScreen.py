import os
from os.path import isfile, isdir, islink, join
#from multiprocessing import Process, Manager, Value, Pool
#from threading import Thread
#from queue import Queue
#from threading import Semaphore
#import hashlib
#import argparse
from time import perf_counter
#import json
from pprint import pprint
from pathlib import Path
import shlex

from textual.app import App
from textual.widgets import Header, Footer, Button

from textual.scroll_view import ScrollView
from textual.strip import Strip
from rich.text import Text
from textual.geometry import Size
from rich.console import Console

from textual.widgets import DataTable

from textual.screen import ModalScreen
from textual.containers import Vertical
from textual.widgets import Button, Label

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static
from rich.table import Table

from drive import load_log

#from vfs import VirtualFS, Node
from vfs import prefixes, disabled_prefixes, aliases # MapDrive
from vfs import format_size, normalize_path, get_stat_info
from vfs import DriveActionsList


driveActions = DriveActionsList()

# DRIVE ACTIONS VIEW [

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
        ("e", "export", "export"),
    ]

    def compose(self):
        with Vertical():
            yield Label("Actions", id="title")
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

        self.query_one("#title", Label).update(f"Actions {len(driveActions.actions)}")

        #for action in driveActions.actions:
        #    table.add_row(str(action))

        for op, *args in driveActions.actions:
            current_path = args[0]

            info = get_stat_info(current_path)

            indicator = f"[green]●[/green]" if info["exists"] else "[red]●[/red]"
            table.add_row(op, f"{indicator} "  + " ".join(map(str, args)))

    def action_close(self):
        self.dismiss()

    def action_clear(self):
        driveActions.clear()
        self.refresh_actions()

    def action_export(self):
        filename = export_sh()
        self.app.notify(f"Export to {filename}")

    def action_apply(self):
        applied = apply_actions()
        self.app.notify(f"Applied {applied} actions")
        self.action_clear()
        self.action_close()


    def on_button_pressed(self, event: Button.Pressed):
        match event.button.id:
            case "close":
                self.dismiss()

            case "clear":
                self.action_clear()

            case "export":
                self.action_export()

            case "apply":
                self.app.notify("Apply")


# DRIVE ACTIONS VIEW ]
# FILE UTIL [

from pathlib import Path
import stat

def unique_filename(filename: str) -> str:
    path = Path(filename)

    if not path.exists():
        return str(path)

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    i = 1
    while True:
        new_path = parent / f"{stem}{i:04d}{suffix}"
        if not new_path.exists():
            return str(new_path)
        i += 1

def get_local_path(vfspath):
    p, parts = normalize_path(vfspath)
    local = aliases.get(parts[0])
    if local:
        parts[0] = local
        p = '/'.join(parts) 
    return p

# FILE UTIL ]
# EXPORT SH [

def export_sh():
    # create actions dir
    actionsdir = 'actions'
    if not isdir(actionsdir):
        os.makedirs(actionsdir)

    # generate new filename
    filename = actionsdir + '/action.sh'
    filename = unique_filename(filename)
    file = open(filename, "w")

    # write functions
    file.write("""
    file_exists() {
        [ -e "$1" ]
    }

    remove () {
        if file_exists "$1"; then
            echo "found $1"
            if [ "$REMOVE" -eq 1 ]; then
                echo "remove $1"
                rm -rf "$1"
            fi
        fi
    }
    REMOVE=0
    if [ "$1" = "-r" ]; then
        REMOVE=1
    fi
    echo Run with -r to remove 
""")


    # flush actions
    for action in driveActions.actions:
        p = get_local_path(action[1])
        file.write(f"{action[0]} {shlex.quote(p)}")
        file.write("\n")

    file.close()

    st = os.stat(filename)
    os.chmod(filename, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return filename

# EXPORT SH ]
# APPLY ACTIONS [

import shutil

def apply_actions():
    removed = {}

    for action in driveActions.actions:
        op = action[0]
        file = action[1]
        p = get_local_path(file)

        info = get_stat_info(p)

        if info["exists"]:
            if op == 'remove':
                removed[p] = file
                shutil.rmtree(file)
#                if info["is_file"]:
#                    # remove file
#                    pass
#                if info["is_dir"]:
#                    # remove dir
#                    pass

    return removed

# APPLY ACTIONS ]

