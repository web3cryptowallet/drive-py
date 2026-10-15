# Archived Textual UI

Textual was archived on 2026-10-15. The main application is now the repository
root's prompt_toolkit `drive-tui.py`; use `./run.sh` or `./run-megadisks.sh`.

This directory preserves the previous app, `views/`, `theme.css`, launchers and
Textual-dependent tests, including mixed scanner/UI tests and the legacy
`load_lite` regression. Shared `drive.py`, LiveLog and `vfs/` remain at the root.
The archive is excluded from normal `tests/` discovery.

To run archived code, provide Textual/Rich/pyperclip in the root `.venv`, then use
`./texual.removed/run.sh` (or another archived launcher). These launchers retain
the repository root as their working directory and import shared modules there.
Archived dependencies are not part of the active pyproject.

Run archived tests from the repository root, with legacy imports first:

```sh
PYTHONPATH=texual.removed:. .venv/bin/python -m unittest discover -s texual.removed/tests -v
```

The archived UI is retained for reference; no Textual regression suite or Rust
parity validation was performed during this move.
