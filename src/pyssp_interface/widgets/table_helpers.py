from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem


def create_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
    )
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def set_table_headers(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)


def set_table_rows(
    table: QTableWidget,
    rows: list[list[str]],
    *,
    editable_columns: set[int] | None = None,
    editable_rows: set[int] | None = None,
) -> None:
    editable_columns = editable_columns or set()
    editable_rows = editable_rows if editable_rows is not None else set(range(len(rows)))
    blocker = QSignalBlocker(table)
    table.setRowCount(len(rows))
    table.clearContents()
    for row_index, row in enumerate(rows):
        for col_index, value in enumerate(row):
            item = QTableWidgetItem(value)
            if col_index not in editable_columns or row_index not in editable_rows:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, col_index, item)
    table.resizeColumnsToContents()
    del blocker
