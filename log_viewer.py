import sys
from collections import Counter
from pathlib import Path

import PyQt6.QtCore as QtCore
import PyQt6.QtWidgets as QtWidgets
import PyQt6.QtGui as QtGui
from PyQt6.QtCore import QDate

from log_parser import LogParser, LogEntry


class LogEntryWithCount:
    def __init__(self, entry: LogEntry, count: int = 1):
        self.entry = entry
        self.count = count


class LogTableModel(QtCore.QAbstractTableModel):
    def __init__(self, entries: list[LogEntry] = None):
        super().__init__()
        self.entries = entries or []

    def update(self, entries: list[LogEntry]):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.entries)

    def columnCount(self, parent=None):
        return 4

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        headers = ['Время', 'Уровень', 'Сообщение']
        return headers[section] if section < 3 else 'Исходная строка'

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        entry = self.entries[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if entry.timestamp else ''
            elif index.column() == 1:
                return entry.level or ''
            elif index.column() == 2:
                return entry.message
            elif index.column() == 3:
                return entry.raw[:120]
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if entry.level == 'ERROR':
                return QtGui.QColor(255, 200, 200)
            elif entry.level == 'WARN':
                return QtGui.QColor(255, 255, 200)
            elif entry.level == 'DEBUG':
                return QtGui.QColor(230, 230, 255)
        return None


class LogTableModelWithCount(QtCore.QAbstractTableModel):
    def __init__(self, entries: list[LogEntryWithCount] = None):
        super().__init__()
        self.entries = entries or []

    def update(self, entries: list[LogEntryWithCount]):
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.entries)

    def columnCount(self, parent=None):
        return 5

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        headers = ['Кол-во', 'Время', 'Уровень', 'Сообщение']
        return headers[section] if section < 4 else 'Исходная строка'

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.entries[index.row()]
        entry = item.entry
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return f'×{item.count}'
            elif index.column() == 1:
                return entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if entry.timestamp else ''
            elif index.column() == 2:
                return entry.level or ''
            elif index.column() == 3:
                return entry.message
            elif index.column() == 4:
                return entry.raw[:120]
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if entry.level == 'ERROR':
                return QtGui.QColor(255, 200, 200)
            elif entry.level == 'WARN':
                return QtGui.QColor(255, 255, 200)
            elif entry.level == 'DEBUG':
                return QtGui.QColor(230, 230, 255)
        elif role == QtCore.Qt.ItemDataRole.FontRole:
            if index.column() == 0 and item.count > 1:
                font = QtGui.QFont()
                font.setBold(True)
                return font
        return None


class LogViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.parser: LogParser | None = None
        self.all_entries: list[LogEntry] = []
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle('Просмотр логов')
        self.setGeometry(100, 100, 1200, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()

        self.btn_open = QtWidgets.QPushButton('Открыть файл')
        self.btn_open.clicked.connect(self.open_file)
        toolbar.addWidget(self.btn_open)

        toolbar.addSpacing(20)

        toolbar.addWidget(QtWidgets.QLabel('Дата с:'))
        self.date_from = QtWidgets.QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.dateChanged.connect(self.apply_filters)
        toolbar.addWidget(self.date_from)

        toolbar.addWidget(QtWidgets.QLabel('по:'))
        self.date_to = QtWidgets.QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self.apply_filters)
        toolbar.addWidget(self.date_to)

        toolbar.addSpacing(20)

        toolbar.addWidget(QtWidgets.QLabel('Уровень:'))
        self.level_widget = QtWidgets.QComboBox()
        self.level_widget.setEditable(True)
        self.level_widget.currentTextChanged.connect(self.apply_filters)
        toolbar.addWidget(self.level_widget)

        toolbar.addSpacing(20)

        toolbar.addWidget(QtWidgets.QLabel('Поиск:'))
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setPlaceholderText('фильтр по тексту...')
        self.search_box.textChanged.connect(self.apply_filters)
        self.search_box.setMinimumWidth(200)
        toolbar.addWidget(self.search_box)

        toolbar.addSpacing(20)

        self.dup_checkbox = QtWidgets.QCheckBox('Группировать дубликаты')
        self.dup_checkbox.stateChanged.connect(self.apply_filters)
        toolbar.addWidget(self.dup_checkbox)

        self.status_label = QtWidgets.QLabel('Файл не загружен')
        toolbar.addStretch()
        toolbar.addWidget(self.status_label)

        layout.addLayout(toolbar)

        # Table
        self.table = QtWidgets.QTableView()
        self.model = LogTableModel()
        self.model_with_count = LogTableModelWithCount()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QTableView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Status bar
        self.statusbar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusbar)

        self.table.doubleClicked.connect(self.show_full_line)
        self.table.horizontalHeader().sectionResized.connect(self._on_section_resized)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_msg_col_index') and self.table.model():
            total = self.table.model().columnCount()
            self.table.setColumnWidth(
                self._msg_col_index,
                self.table.width() - sum(self.table.columnWidth(i) for i in range(total) if i != self._msg_col_index) - 20
            )

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Открыть файл лога', '', 'Лог файлы (*.log *.txt);;Все файлы (*)'
        )
        if not path:
            return
        self.load_file(path)

    def load_file(self, path: str):
        self.parser = LogParser(path)
        self.all_entries = self.parser.entries
        self.status_label.setText(f'Загружен: {Path(path).name}')

        # Populate level filter
        self.level_widget.blockSignals(True)
        self.level_widget.clear()
        levels = sorted(self.parser.available_levels)
        if levels:
            self.level_widget.addItems(['Все'] + levels)
        else:
            self.level_widget.addItem('Все')
        self.level_widget.blockSignals(False)

        # Populate date filters
        dates = sorted(self.parser.available_dates)
        if dates:
            self.date_from.blockSignals(True)
            self.date_to.blockSignals(True)
            self.date_from.setDate(QDate.fromString(dates[0], 'yyyy-MM-dd'))
            self.date_to.setDate(QDate.fromString(dates[-1], 'yyyy-MM-dd'))
            self.date_from.blockSignals(False)
            self.date_to.blockSignals(False)

        self.apply_filters()

    def apply_filters(self):
        if not self.parser:
            return

        date_from = self.date_from.date().toString('yyyy-MM-dd')
        date_to = self.date_to.date().toString('yyyy-MM-dd')

        level_text = self.level_widget.currentText()
        if level_text == 'Все' or not level_text:
            levels = None
        else:
            levels = {level_text.upper()}

        search = self.search_box.text().strip() or None

        filtered = self.parser.filter_entries(
            date_from=date_from,
            date_to=date_to,
            levels=levels,
            search_text=search
        )

        if self.dup_checkbox.isChecked():
            grouped = self._group_by_message(filtered)
            self.model_with_count.update(grouped)
            self.table.setModel(self.model_with_count)
            self._resize_columns(5)
            unique_count = len(grouped)
            total_count = sum(item.count for item in grouped)
            self.statusbar.showMessage(
                f'Показано {unique_count} уникальных из {total_count} записей (всего {len(self.all_entries)})', 3000
            )
        else:
            self.model.update(filtered)
            self.table.setModel(self.model)
            self._resize_columns(4)
            self.statusbar.showMessage(f'Показано {len(filtered)} из {len(self.all_entries)} записей', 3000)

    def _group_by_message(self, entries: list[LogEntry]) -> list[LogEntryWithCount]:
        counts = Counter(e.raw for e in entries)
        seen = set()
        result = []
        for entry in entries:
            if entry.raw in seen:
                continue
            seen.add(entry.raw)
            result.append(LogEntryWithCount(entry, counts[entry.raw]))
        # Sort by count descending
        result.sort(key=lambda x: -x.count)
        return result

    def _resize_columns(self, total_cols: int):
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(total_cols - 1, self.table.width() - sum(
            self.table.columnWidth(i) for i in range(total_cols - 1)
        ) - 20)
        self._msg_col_index = total_cols - 1

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        if hasattr(self, '_msg_col_index') and logicalIndex == self._msg_col_index:
            return
        if hasattr(self, '_msg_col_index'):
            total = self.table.model().columnCount() if self.table.model() else 4
            self.table.setColumnWidth(
                self._msg_col_index,
                self.table.width() - sum(self.table.columnWidth(i) for i in range(total) if i != self._msg_col_index) - 20
            )

    def show_full_line(self, index):
        row = index.row()
        model = self.table.model()
        if hasattr(model, 'entries') and 0 <= row < len(model.entries):
            item = model.entries[row]
            entry = item.entry if hasattr(item, 'entry') else item
            if hasattr(item, 'count') and item.count > 1:
                QtWidgets.QMessageBox.information(
                    self, 'Полная запись лога',
                    f'Повторений: ×{item.count}\n\n{entry.raw}'
                )
            else:
                QtWidgets.QMessageBox.information(self, 'Полная запись лога', entry.raw)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = LogViewer()
    window.show()

    if len(sys.argv) > 1:
        window.load_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
