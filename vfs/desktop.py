"""Reveal a selected local file using platform file-manager integration."""
# HIGHLIGHT THE FILE IN ITS PARENT WINDOW WHEN SUPPORTED [
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def raise_x11_file_manager(directory=None):
    """Request activation of an existing matching X11 manager window."""
    connection = None
    try:
        from Xlib import X, Xatom, display, protocol
        connection = display.Display()
        root = connection.screen().root
        clients = root.get_full_property(connection.intern_atom('_NET_CLIENT_LIST_STACKING'), Xatom.WINDOW)
        if clients is None:
            clients = root.get_full_property(connection.intern_atom('_NET_CLIENT_LIST'), Xatom.WINDOW)
        if clients is None:
            return
        candidates = []
        folder = Path(directory).name.casefold() if directory else ''
        for xid in reversed(clients.value):
            window = connection.create_resource_object('window', int(xid))
            try:
                classes = [name.casefold() for name in (window.get_wm_class() or ())]
                if not any(name in ('org.gnome.nautilus', 'nautilus', 'nemo', 'dolphin', 'thunar', 'pcmanfm') for name in classes):
                    continue
                name = window.get_full_property(connection.intern_atom('_NET_WM_NAME'), X.AnyPropertyType)
                title = bytes(name.value).decode('utf-8', errors='replace') if name else (window.get_wm_name() or '')
                candidates.append((bool(folder and folder in title.casefold()), window))
            except Exception:
                continue  # A desktop window may close between listing and lookup.
        if candidates:
            target = max(candidates, key=lambda item: item[0])[1]
            root.send_event(protocol.event.ClientMessage(window=target,
                client_type=connection.intern_atom('_NET_ACTIVE_WINDOW'), data=(32, [2, X.CurrentTime, 0, 0, 0])),
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            connection.sync()
    except Exception:
        pass  # Wayland/non-EWMH desktops may not expose an activatable X11 window.
    finally:
        if connection is not None:
            connection.close()


def activate_file_manager(directory=None):
    try:
        if sys.platform == 'darwin':
            subprocess.run(['open', '-a', 'Finder'], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, check=True, timeout=5)
        elif sys.platform != 'win32' and os.environ.get('DISPLAY'):
            raise_x11_file_manager(directory)
    except (OSError, subprocess.SubprocessError):
        pass


def reveal_file(path):
    if sys.platform == 'darwin':
        subprocess.run(['open', '-R', path], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, check=True)
        activate_file_manager(str(Path(path).parent))
        return
    if sys.platform == 'win32':
        subprocess.Popen(['explorer.exe', '/select,' + path], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if shutil.which('gdbus'):
        try:
            subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.FileManager1',
                            '--object-path', '/org/freedesktop/FileManager1', '--method',
                            'org.freedesktop.FileManager1.ShowItems', json.dumps([Path(path).as_uri()]), os.environ.get('DESKTOP_STARTUP_ID', '')],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=5)
            activate_file_manager(str(Path(path).parent))
            return
        except (OSError, subprocess.SubprocessError):
            pass
    for executable in ('nautilus', 'nemo', 'dolphin'):
        if shutil.which(executable):
            try:
                subprocess.Popen([executable, '--select', path], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
    # Generic openers can open a folder but cannot request a selected child.
    subprocess.run(['xdg-open', str(Path(path).parent)], stdin=subprocess.DEVNULL,
                   capture_output=True, text=True, check=True)
# HIGHLIGHT THE FILE IN ITS PARENT WINDOW WHEN SUPPORTED ]
