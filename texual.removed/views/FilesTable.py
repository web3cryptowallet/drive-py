"""Fit main-file metadata columns beside a clipped, variable-width name."""
from textual.widgets import DataTable


class FilesTable(DataTable):
    def on_resize(self):
        self.call_after_refresh(self.fit_columns)

    def watch_show_vertical_scrollbar(self, visible):
        if self.is_mounted:
            self.call_after_refresh(self.fit_columns)

    def fit_columns(self):
        columns = self.ordered_columns
        if len(columns) != 3:
            return
        budget = max(3, self.scrollable_content_region.width - 6 * self.cell_padding)
        size_width, dups_width = 4, 4
        for row in self.ordered_rows:
            _, size, dups = self.get_row(row.key)
            size_width = max(size_width, size.cell_len)
            dups_width = max(dups_width, dups.cell_len)
        size_width = min(size_width, budget - 2)
        dups_width = min(dups_width, budget - size_width - 1)
        widths = (budget - size_width - dups_width, size_width, dups_width)
        if all(not column.auto_width and column.width == width
               for column, width in zip(columns, widths)):
            return
        for column, width in zip(columns, widths):
            column.auto_width = False
            column.width = width
        # Match DataTable's column-change invalidation/dimension update.
        self._clear_caches()
        self._require_update_dimensions = True
        self.check_idle()
        self.refresh()
