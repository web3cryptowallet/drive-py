"""Scrollable help shared by the main file manager and scanner popup."""
from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class HelpScreen(ModalScreen):
    CSS = """
    HelpScreen { align: center middle; }
    #help-dialog { width: 90%; height: 90%; border: thick $accent; background: $surface; }
    #help-title { height: 1; text-style: bold; }
    #help-scroll { height: 1fr; width: 100%; }
    #help-content { height: auto; }
    #help-close { height: 1; min-width: 8; width: auto; border: none; }
    """
    BINDINGS = [Binding('h', 'close', 'Close help', priority=True),
                Binding('escape', 'close', 'Close help', priority=True)]

    def __init__(self, title, lines):
        super().__init__()
        self.title_text = title
        self.lines = lines

    def compose(self):
        with Vertical(id='help-dialog'):
            yield Static(self.title_text, id='help-title')
            with VerticalScroll(id='help-scroll', can_focus=True):
                yield Static(Text.from_markup('\n'.join(self.lines)), id='help-content')
            yield Button('Close', id='help-close')

    def on_mount(self):
        self.query_one('#help-scroll').focus()

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event):
        if event.button.id == 'help-close':
            self.action_close()


def main_help(display_mode):
    legend = ([
        '[white]Files in database and on disk[/white]',
        '[white]* New: on disk only[/white]',
        '[white]! Deleted: in database only[/white]',
    ] if display_mode == 3 else [
        '[green]●[/green] Available in database and on disk',
        '[red]●[/red] Not found on disk',
        '[dark_orange]●[/dark_orange] New file or directory: not in database',
    ] if display_mode == 1 else [
        '[green]●[/green] Available',
        '[red]●[/red] Not found',
        '[yellow]Yellow names[/yellow]: new paths; red names: missing paths',
    ])
    return [
        '[bold]Legend — current display mode[/bold]', *legend,
        '[dark_orange]?[/dark_orange] Maybe available; available last time',
        '[red]R[/red] In remove queue',
        '[red]D[/red] Deleted',
        '', '[bold]Shortcuts[/bold]',
        '[#ff8800]h / Esc[/#ff8800] (in help): Close help',
        '[#ff8800]Enter[/#ff8800]: Open directory or view file info',
        '[#ff8800]Esc[/#ff8800] (main view): Go to parent directory',
        '[#ff8800]Arrows / Page Up / Page Down[/#ff8800]: Navigate the focused table',
        '[#ff8800]Ctrl+X[/#ff8800]: Copy info panel text to clipboard',
        '[#ff8800]t[/#ff8800]: Cycle MC Default, MC Blue and Textual Dark themes',
        '[#ff8800]n[/#ff8800]: Cycle circles, colored names and monochrome display',
        '[#ff8800]s[/#ff8800]: Open scanner/map for the current directory',
        '[#ff8800]q[/#ff8800]: Quit',
        '', '[bold]Removal queue[/bold]',
        '[#ff8800]Delete[/#ff8800]: Queue selected file for removal',
        '[#ff8800]Shift+Delete[/#ff8800]: Queue file and all duplicates for removal',
        '[#ff8800]a[/#ff8800]: Open Actions to review operations',
        'In Actions: [#ff8800]x[/#ff8800] clears the queue; [#ff8800]e[/#ff8800] exports apply/drive*.sh',
        'Use the Apply button to apply queued operations',
        '', '[bold]File table[/bold]',
        'Size and Dups remain visible beside clipped long names',
        'Directory Dups values retain their total-file counts',
        'The vertical scrollbar is always visible',
    ]


SCANNER_HELP = [
    '[bold]Scanning[/bold]',
    'On open: lite → medium → heavy once, then all modes stop',
    'Changing a scan mode cancels the automatic startup sequence',
    '[#ff8800]1 / 2 / 3[/#ff8800]: Independently run/stop lite, medium, heavy',
    '[green]RUN[/green] / [red]STOP[/red]: enabled/paused mode',
    'Lite: discover paths and build buckets; directories have D state',
    'Medium: discover new paths and verify file presence/type/size without checksums',
    'Heavy: compare checksums; verified new files enter VFS and show green in main',
    'Heavy scanning keeps your map cursor and file page in place',
    'Directories are skipped by medium/heavy verification',
    'Start/stop resumes each mode at its saved pending path',
    '[#ff8800]Shift+1 / Shift+2 / Shift+3[/#ff8800] (also [#ff8800]! / @ / #[/#ff8800]): start from cursor bucket',
    '[#ff8800]r[/#ff8800]: Toggle known-file disk metadata reads in lite',
    '[#ff8800]t[/#ff8800]: Toggle heavy new-first/all priority within buckets',
    '[#ff8800]j[/#ff8800]: Heavy normal (sequential) / expert (selector queue)',
    'Expert tick: pick one random starting bucket, then mark 1–20 following buckets blue',
    '? buckets first; skip blocked/occupied buckets, wrap at end; 1–20 added per tick',
    'Skip fully green buckets until all file buckets are green; mixed ?/green still count',
    'Background additions: random 0.2–1s; empty work queue refills immediately',
    'Add new ranges while earlier ranges scan; total blue can exceed 20',
    'Completed buckets restore their normal background; pause keeps pending work',
    'Changing j also cancels startup; startup heavy is a finite normal pass',
    '', '[bold]Symbols[/bold]',
    '[white]D[/white] Directory',
    '[white]?[/white] Unverified/new file',
    '[green]?[/green] Bucket has both unverified and verified files',
    '[white]U[/white] Legacy new state',
    '[red]U[/red] Missing file',
    '[green]●[/green] Verified by the latest metadata/checksum check',
    '[#ff8800]M[/#ff8800] Modified file',
    '[white on red]\\ | / -[/white on red] Recent map update (normal); expert uses queue blue/base background; S n% is file progress',
    '', '[bold]Map and settings[/bold]',
    '[#ff8800]m[/#ff8800]: Count/size bucket packing',
    '[#ff8800]v[/#ff8800]: Fixed/scroll packing',
    '[#ff8800]Arrows / Page Up / Page Down[/#ff8800]: Move map cursor',
    '[#ff8800]Right[/#ff8800] at last bucket: follow new buckets at >',
    '[#ff8800]Right[/#ff8800] keeps follow mode; other arrows, Page Up/Down or real-bucket click exit',
    'Paths/bucket and MiB/bucket: edit limits; [#ff8800]Enter[/#ff8800] applies',
    '', '[bold]File list and pages[/bold]',
    'Click a status count to filter; click it again or All to remove filter',
    '[#ff8800]][/#ff8800] in map or file list: select /a, then /a/b for selected file /a/b/c',
    '[#ff8800][[/#ff8800] moves back through parent directories',
    'Matching buckets get a random background; symbol foregrounds stay unchanged',
    '[#ff8800]f[/#ff8800]: Fix matching bucket colors; [#ff8800]d[/#ff8800]: Clear all colors',
    'Fixed colors persist through scope changes and saved-map reopening',
    '[#ff8800]Left / Right[/#ff8800] in the file list: horizontal pan; scrollbar also pans',
    '[#ff8800]Up[/#ff8800] at first row: previous page, last file',
    '[#ff8800]Down[/#ff8800] at last row: next page, first file',
    'Page buttons/jumps or slider: seek; horizontal position is preserved',
    'Slider: [#ff8800]Left/Right[/#ff8800] step; [#ff8800]Home/End[/#ff8800] select first/last page',
    '', '[bold]Info and saved state[/bold]',
    'Paths/s and MB/s–PB/s use completed visits/sizes from the last 5 seconds',
    'Rates sum all modes and decay to zero after idle; totals stay cumulative',
    'Total paths/size count repeat visits; bucket N/total tracks the viewport',
    'Map settings, selection, filter and per-mode positions save per path',
    '[#ff8800]s / Esc[/#ff8800] (scanner): Close scanner; [#ff8800]h[/#ff8800]: Help',
    '[#ff8800]h / Esc[/#ff8800] (help) or Close button: Return to scanner',
]
