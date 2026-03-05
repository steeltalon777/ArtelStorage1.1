from uuid import UUID

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ItemsTab(QWidget):
    def __init__(self, items_service, categories_service, parent=None):
        super().__init__(parent)
        self.items_service = items_service
        self.categories_service = categories_service

        self.name_input = QLineEdit(self)
        self.unit_input = QLineEdit(self)
        self.category_combo = QComboBox(self)
        self.items_table = QTableWidget(self)

        self._build_ui()
        self.reload_categories()
        self.reload_items()

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow("Наименование:", self.name_input)
        form.addRow("Ед. измерения:", self.unit_input)
        form.addRow("Категория:", self.category_combo)

        controls = QHBoxLayout()
        add_button = QPushButton("Создать")
        add_button.clicked.connect(self._create_item)
        update_button = QPushButton("Сохранить")
        update_button.clicked.connect(self._update_item)
        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self._delete_item)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.reload_items)

        controls.addWidget(add_button)
        controls.addWidget(update_button)
        controls.addWidget(delete_button)
        controls.addStretch(1)
        controls.addWidget(refresh_button)

        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["ID", "Наименование", "Ед.", "Категория", "Источник"])
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.itemSelectionChanged.connect(self._fill_form_from_selection)

        root.addLayout(form)
        root.addLayout(controls)
        root.addWidget(QLabel("ТМЦ"))
        root.addWidget(self.items_table)

    def reload_categories(self):
        current_data = self.category_combo.currentData()
        self.category_combo.clear()
        self.category_combo.addItem("(Без категории)", None)
        for category in self.categories_service.get_all_categories():
            self.category_combo.addItem(category.name, category.id)

        if current_data is not None:
            idx = self.category_combo.findData(current_data)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)

    def reload_items(self):
        items = self.items_service.get_all_items()
        self.items_table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.items_table.setItem(row, 0, QTableWidgetItem(str(item.id)))
            self.items_table.setItem(row, 1, QTableWidgetItem(item.name))
            self.items_table.setItem(row, 2, QTableWidgetItem(item.unit))
            self.items_table.setItem(row, 3, QTableWidgetItem(item.category_name or "-"))
            self.items_table.setItem(row, 4, QTableWidgetItem("local" if item.created_locally else "server"))

        self.items_table.resizeColumnsToContents()

    def _selected_item_id(self):
        row = self.items_table.currentRow()
        if row < 0:
            return None
        value = self.items_table.item(row, 0)
        if value is None:
            return None
        return UUID(value.text())

    def _fill_form_from_selection(self):
        item_id = self._selected_item_id()
        if item_id is None:
            return

        item = self.items_service.get_item_by_id(item_id)
        if item is None:
            return

        self.name_input.setText(item.name)
        self.unit_input.setText(item.unit)
        idx = self.category_combo.findData(item.category_id)
        self.category_combo.setCurrentIndex(max(idx, 0))

    def _create_item(self):
        name = self.name_input.text().strip()
        unit = self.unit_input.text().strip()
        category_id = self.category_combo.currentData()

        if not name or not unit:
            QMessageBox.warning(self, "Валидация", "Заполните наименование и единицу измерения.")
            return

        try:
            self.items_service.create_item(name, unit, category_id)
            self.reload_items()
            self._clear_form()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _update_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            QMessageBox.warning(self, "ТМЦ", "Выберите запись для редактирования.")
            return

        name = self.name_input.text().strip()
        unit = self.unit_input.text().strip()
        category_id = self.category_combo.currentData()

        if not name or not unit:
            QMessageBox.warning(self, "Валидация", "Заполните наименование и единицу измерения.")
            return

        try:
            updated = self.items_service.update_item(item_id, name=name, unit=unit, category_id=category_id)
            if not updated:
                QMessageBox.warning(self, "ТМЦ", "Запись не была обновлена.")
            self.reload_items()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _delete_item(self):
        item_id = self._selected_item_id()
        if item_id is None:
            QMessageBox.warning(self, "ТМЦ", "Выберите запись для удаления.")
            return

        if not self.items_service.can_delete_item(item_id):
            QMessageBox.warning(self, "ТМЦ", "ТМЦ используется в операциях и не может быть удалена.")
            return

        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить выбранную ТМЦ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.items_service.delete_item(item_id)
            self.reload_items()
            self._clear_form()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _clear_form(self):
        self.name_input.clear()
        self.unit_input.clear()
        self.category_combo.setCurrentIndex(0)
