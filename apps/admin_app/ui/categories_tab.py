from PyQt6.QtWidgets import (
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


class CategoriesTab(QWidget):
    def __init__(self, categories_service, parent=None):
        super().__init__(parent)
        self.categories_service = categories_service

        self.name_input = QLineEdit(self)
        self.table = QTableWidget(self)

        self._build_ui()
        self.reload_categories()

    def _build_ui(self):
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.name_input.setPlaceholderText("Название категории")
        create_button = QPushButton("Создать")
        create_button.clicked.connect(self._create)
        update_button = QPushButton("Сохранить")
        update_button.clicked.connect(self._update)
        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self._delete)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.reload_categories)

        controls.addWidget(QLabel("Категория:"))
        controls.addWidget(self.name_input, 1)
        controls.addWidget(create_button)
        controls.addWidget(update_button)
        controls.addWidget(delete_button)
        controls.addWidget(refresh_button)

        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "ТМЦ"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._fill_form)

        root.addLayout(controls)
        root.addWidget(self.table)

    def reload_categories(self):
        stats = self.categories_service.get_category_stats()
        self.table.setRowCount(len(stats))

        for row, category in enumerate(stats):
            self.table.setItem(row, 0, QTableWidgetItem(str(category["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(category["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(category["item_count"])))

        self.table.resizeColumnsToContents()

    def _selected_category_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return int(item.text())

    def _fill_form(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name_item = self.table.item(row, 1)
        if name_item is not None:
            self.name_input.setText(name_item.text())

    def _create(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Категории", "Введите название категории.")
            return

        try:
            self.categories_service.create_category(name)
            self.reload_categories()
            self.name_input.clear()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _update(self):
        category_id = self._selected_category_id()
        if category_id is None:
            QMessageBox.warning(self, "Категории", "Выберите категорию для изменения.")
            return

        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Категории", "Введите название категории.")
            return

        try:
            updated = self.categories_service.update_category(category_id, name)
            if not updated:
                QMessageBox.warning(self, "Категории", "Категория не была обновлена.")
            self.reload_categories()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _delete(self):
        category_id = self._selected_category_id()
        if category_id is None:
            QMessageBox.warning(self, "Категории", "Выберите категорию для удаления.")
            return

        if not self.categories_service.can_delete_category(category_id):
            QMessageBox.warning(self, "Категории", "Категория используется в ТМЦ и не может быть удалена.")
            return

        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить выбранную категорию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.categories_service.delete_category(category_id)
            self.reload_categories()
            self.name_input.clear()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
