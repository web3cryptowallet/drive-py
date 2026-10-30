"""Native clipboard delivery and terminal OSC 52 fallback framing."""
# SELECT PLATFORM CLIPBOARD COMMANDS WITHOUT INVOKING A SHELL [
import base64
import os
import shutil
import subprocess
import sys


def copy_native(text):
    """Return whether an available desktop clipboard command accepted the text."""
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'):
        return False  # OSC 52 targets the terminal user's clipboard over SSH.
    encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
    powershell = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                  "Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString("
                  f"[Convert]::FromBase64String('{encoded}')))"]
    if sys.platform == 'darwin':
        commands = [['pbcopy']]
    elif sys.platform == 'win32':
        commands = [powershell]
    else:
        wayland = [['wl-copy']]
        x11 = [['xclip', '-selection', 'clipboard'], ['xsel', '--clipboard', '--input']]
        commands = (wayland + x11 if os.environ.get('WAYLAND_DISPLAY') else x11 + wayland) + [powershell]
    for command in commands:
        if not shutil.which(command[0]):
            continue
        try:
            # Clipboard owners may fork; inherited capture pipes can prevent EOF.
            subprocess.run(command, input='' if command is powershell else text,
                           text=True, encoding='utf-8', stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=3)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    if sys.platform not in ('darwin', 'win32') and os.environ.get('DISPLAY'):
        from .clipboard_x11 import copy_x11
        return copy_x11(text)
    return False
# SELECT PLATFORM CLIPBOARD COMMANDS WITHOUT INVOKING A SHELL ]
# FRAME CLIPBOARD TEXT FOR DIRECT TERMINALS AND TMUX PASSTHROUGH [
def clipboard_escape(text):
    encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
    packet = '\x1b]52;c;' + encoded + '\x07'
    if os.environ.get('TMUX'):
        packet += '\x1bPtmux;' + packet.replace('\x1b', '\x1b\x1b') + '\x1b\\'
    return packet
# FRAME CLIPBOARD TEXT FOR DIRECT TERMINALS AND TMUX PASSTHROUGH ]
