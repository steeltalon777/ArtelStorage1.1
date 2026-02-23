from pathlib import Path
from uuid import UUID

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QComboBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.services.categories_service import CategoriesService
from core.services.export_service import ExportService
from core.services.import_service import ImportService
from core.services.operations_service import OperationsService
from core.services.stock_service import StockService
from ui.operation_dialog import OperationDialog, TYPE_LABELS


class MainWindow(QMainWindow):
    """Main application window with stock/operations UI and role-aware settings."""

    logout_requested = pyqtSignal()

    def __init__(self, db_path, auth_manager, current_user):
        super().__init__()
        self.db_path = db_path
        self.auth_manager = auth_manager
        self.current_user = current_user

        self.categories_service = CategoriesService(db_path)
        self.export_service = ExportService(db_path)
        self.import_service = ImportService(db_path)
        self.operations_service = OperationsService(db_path)
        self.stock_service = StockService(db_path)

        self.setWindowTitle("ArtelStorage v1.1")
        self.resize(1200, 780)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.stock_search_input = QLineEdit(self)
        self.stock_category_combo = QComboBox(self)
        self.stock_table = QTableWidget(self)

        self.operations_search_input = QLineEdit(self)
        self.operations_table = QTableWidget(self)

        self._build_stock_tab()
        self._build_operations_tab()
        self._build_settings_tab_if_admin()
        self._build_menu()
        self._build_statusbar()

        self._load_categories_filter()
        self._refresh_stock()
        self._refresh_operations()

    def _build_menu(self):
        menu = self.menuBar()

        session_menu = menu.addMenu("Сессия")
        logout_action = session_menu.addAction("Выход")
        logout_action.triggered.connect(self._on_logout)

        operations_menu = menu.addMenu("Операции")
        create_operation_action = operations_menu.addAction("Создать операцию")
        create_operation_action.triggered.connect(self._open_create_operation_dialog)

        if self.current_user and self.current_user.is_admin:
            settings_menu = menu.addMenu("Настройки")
            open_settings_action = settings_menu.addAction("Данные")
            open_settings_action.triggered.connect(self._open_data_settings)

    def _build_statusbar(self):
        status = QStatusBar(self)
        self.setStatusBar(status)
        role = "Администратор" if self.current_user and self.current_user.is_admin else "Пользователь"
        username = self.current_user.username if self.current_user else "-"
        full_name = self.current_user.full_name if self.current_user else "-"
        status.showMessage(f"Пользователь: {full_name} ({username}) | Роль: {role}")

    def _build_stock_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        controls = QHBoxLayout()
        self.stock_search_input.setPlaceholderText("Поиск: ТМЦ, категория, инв. номер")
        self.stock_search_input.textChanged.connect(self._refresh_stock)

        self.stock_category_combo.currentIndexChanged.connect(self._refresh_stock)

        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self._refresh_stock)

        controls.addWidget(QLabel("Поиск:"))
        controls.addWidget(self.stock_search_input, 1)
        controls.addWidget(QLabel("Категория:"))
        controls.addWidget(self.stock_category_combo)
        controls.addWidget(refresh_button)

        self.stock_table.setColumnCount(5)
        self.stock_table.setHorizontalHeaderLabels(["Инв. номер", "ТМЦ", "Категория", "Ед.", "Остаток"])
        self.stock_table.setSortingEnabled(True)
        self.stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stock_table.horizontalHeader().setStretchLastSection(True)

        layout.addLayout(controls)
        layout.addWidget(self.stock_table)

        self.tabs.addTab(tab, "Остатки")

    def _build_operations_tab(self):
        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        controls = QHBoxLayout()
        self.operations_search_input.setPlaceholderText("Поиск по операциям")
        self.operations_search_input.textChanged.connect(self._refresh_operations)

        create_button = QPushButton("Новая операция")
        create_button.clicked.connect(self._open_create_operation_dialog)

        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self._refresh_operations)

        open_pdf_button = QPushButton("Открыть накладную")
        open_pdf_button.clicked.connect(self._open_selected_pdf)

        controls.addWidget(QLabel("Поиск:"))
        controls.addWidget(self.operations_search_input, 1)
        controls.addWidget(create_button)
        controls.addWidget(refresh_button)
        controls.addWidget(open_pdf_button)

        self.operations_table.setColumnCount(9)
        self.operations_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Дата",
                "Операция",
                "Источник",
                "Получатель/Объект",
                "Транспорт",
                "Строк",
                "Накладная",
                "Комментарий",
            ]
        )
        self.operations_table.setSortingEnabled(True)
        self.operations_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.operations_table.horizontalHeader().setStretchLastSection(True)

        layout.addLayout(controls)
        layout.addWidget(self.operations_table)

        self.tabs.addTab(tab, "Операции")

    def _build_settings_tab_if_admin(self):
        if not (self.current_user and self.current_user.is_admin):
            return

        tab = QWidget(self)
        layout = QVBoxLayout(tab)

        data_group = QGroupBox("Данные")
        data_layout = QHBoxLayout(data_group)

        export_button = QPushButton("Экспорт всех данных")
        export_button.clicked.connect(self._export_data)
        import_button = QPushButton("Импорт данных")
        import_button.clicked.connect(self._import_data)

        data_layout.addWidget(export_button)
        data_layout.addWidget(import_button)

        layout.addWidget(data_group)
        layout.addStretch(1)

        self.tabs.addTab(tab, "Настройки")

    def _load_categories_filter(self):
        current = self.stock_category_combo.currentData()
        self.stock_category_combo.blockSignals(True)
        self.stock_category_combo.clear()
        self.stock_category_combo.addItem("Все", None)
        for category in self.categories_service.get_all_categories():
            self.stock_category_combo.addItem(category.name, category.id)

        if current is not None:
            idx = self.stock_category_combo.findData(current)
            if idx >= 0:
                self.stock_category_combo.setCurrentIndex(idx)
        self.stock_category_combo.blockSignals(False)

    def _refresh_stock(self):
        rows = self.stock_service.get_stock_rows(
            site_id=self.stock_service.get_local_site_id(),
            search=self.stock_search_input.text().strip(),
            category_id=self.stock_category_combo.currentData(),
        )

        self.stock_table.setSortingEnabled(False)
        self.stock_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            self.stock_table.setItem(row_idx, 0, QTableWidgetItem(str(row["item_id"])))
            self.stock_table.setItem(row_idx, 1, QTableWidgetItem(row["name"]))
            self.stock_table.setItem(row_idx, 2, QTableWidgetItem(row.get("category_name") or "-"))
            self.stock_table.setItem(row_idx, 3, QTableWidgetItem(row["unit"]))
            self.stock_table.setItem(row_idx, 4, QTableWidgetItem(f"{row['qty']:g}"))

        self.stock_table.resizeColumnsToContents()
        self.stock_table.setSortingEnabled(True)

    def _refresh_operations(self):
        operations = self.operations_service.list_operations(
            limit=300,
            search=self.operations_search_input.text().strip(),
        )

        self.operations_table.setSortingEnabled(False)
        self.operations_table.setRowCount(len(operations))

        for row_idx, op in enumerate(operations):
            self.operations_table.setItem(row_idx, 0, QTableWidgetItem(str(op["id"])))
            self.operations_table.setItem(row_idx, 1, QTableWidgetItem(str(op["created_at"])))
            self.operations_table.setItem(row_idx, 2, QTableWidgetItem(TYPE_LABELS.get(op["type"], op["type"])))
            self.operations_table.setItem(row_idx, 3, QTableWidgetItem(op.get("source_site_name") or "-"))
            receiver = op.get("recipient_name") or op.get("target_site_name") or "-"
            self.operations_table.setItem(row_idx, 4, QTableWidgetItem(receiver))
            self.operations_table.setItem(row_idx, 5, QTableWidgetItem(op.get("vehicle") or "-"))
            self.operations_table.setItem(row_idx, 6, QTableWidgetItem(str(op.get("lines_count") or 0)))
            self.operations_table.setItem(
                row_idx,
                7,
                QTableWidgetItem("Да" if op.get("pdf_path") else "-"),
            )
            self.operations_table.setItem(row_idx, 8, QTableWidgetItem(op.get("comment") or ""))

        self.operations_table.resizeColumnsToContents()
        self.operations_table.setSortingEnabled(True)

    def _open_create_operation_dialog(self):
        dialog = OperationDialog(self.operations_service, self.current_user, self)
        if dialog.exec() == OperationDialog.DialogCode.Accepted:
            self._load_categories_filter()
            self._refresh_stock()
            self._refresh_operations()

    def _selected_operation_id(self):
        row = self.operations_table.currentRow()
        if row < 0:
            return None
        item = self.operations_table.item(row, 0)
        return item.text() if item else None

    def _open_selected_pdf(self):
        operation_id = self._selected_operation_id()
        if not operation_id:
            QMessageBox.warning(self, "Операции", "Выберите операцию в таблице.")
            return

        try:
            record = self.operations_service.get_operation_by_id(UUID(operation_id))
        except ValueError:
            record = None

        pdf_path = record.get("pdf_path") if record else None
        if not pdf_path:
            QMessageBox.information(self, "Накладная", "Для этой операции накладная не сгенерирована.")
            return

        path = Path(pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Накладная", f"Файл не найден:\n{path}")
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        if not opened:
            QMessageBox.warning(self, "Накладная", "Не удалось открыть файл накладной в системе.")

    def _open_data_settings(self):
        if not self._ensure_admin():
            return

        for idx in range(self.tabs.count()):
            if self.tabs.tabText(idx) == "Настройки":
                self.tabs.setCurrentIndex(idx)
                return

    def _ensure_admin(self):
        if self.current_user and self.current_user.is_admin:
            return True
        QMessageBox.warning(self, "Доступ запрещен", "Раздел доступен только администраторам.")
        return False

    def _export_data(self):
        if not self._ensure_admin():
            return

        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить экспорт",
            str(Path(self.db_path).parent / "snapshot.json"),
            "JSON (*.json)",
        )
        if not target_path:
            return

        progress = QProgressDialog("Экспорт данных...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.show()
        try:
            self.export_service.export_to_file(target_path)
            QMessageBox.information(self, "Экспорт", f"Данные экспортированы в:\n{target_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка экспорта", str(exc))
        finally:
            progress.close()

    def _import_data(self):
        if not self._ensure_admin():
            return

        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл импорта",
            str(Path(self.db_path).parent),
            "JSON (*.json)",
        )
        if not source_path:
            return

        reply = QMessageBox.warning(
            self,
            "Подтверждение импорта",
            "Импорт заменит текущие данные в базе. Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        progress = QProgressDialog("Импорт данных...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setCancelButton(None)
        progress.show()
        try:
            self.import_service.import_from_file(source_path)
            self._load_categories_filter()
            self._refresh_stock()
            self._refresh_operations()
            QMessageBox.information(self, "Импорт", "Данные успешно импортированы.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка импорта", str(exc))
        finally:
            progress.close()

    def _on_logout(self):
        self.logout_requested.emit()
