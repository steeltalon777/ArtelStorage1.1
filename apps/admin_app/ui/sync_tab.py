from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
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

from core.services.sync_orchestrator import SyncOrchestrator
from core.services.sync_outbox_service import SyncOutboxService
from core.services.sync_settings_service import SyncSettingsService


class SyncTab(QWidget):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.settings_service = SyncSettingsService(db_path)
        self.outbox_service = SyncOutboxService(db_path)
        self.orchestrator = SyncOrchestrator(db_path)

        self.server_url_input = QLineEdit(self)
        self.site_uuid_input = QLineEdit(self)
        self.device_uuid_input = QLineEdit(self)
        self.device_token_input = QLineEdit(self)
        self.client_version_input = QLineEdit(self)
        self.enabled_checkbox = QCheckBox("Включить синхронизацию", self)

        self.status_label = QLabel("-", self)
        self.pending_label = QLabel("0", self)
        self.error_label = QLabel("-", self)

        self.queue_table = QTableWidget(self)

        self._build_ui()
        self.reload()

    def _build_ui(self):
        root = QVBoxLayout(self)

        settings_group = QGroupBox("Настройки")
        settings_form = QFormLayout(settings_group)
        self.device_uuid_input.setReadOnly(True)
        settings_form.addRow("Server URL", self.server_url_input)
        settings_form.addRow("Site UUID", self.site_uuid_input)
        settings_form.addRow("Device UUID", self.device_uuid_input)
        settings_form.addRow("Device Token", self.device_token_input)
        settings_form.addRow("Client Version", self.client_version_input)
        settings_form.addRow("", self.enabled_checkbox)

        settings_controls = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self._save)
        sync_now_button = QPushButton("Синхронизировать сейчас")
        sync_now_button.clicked.connect(self._sync_now)
        reset_device_button = QPushButton("Сбросить устройство")
        reset_device_button.clicked.connect(self._reset_device)

        settings_controls.addWidget(save_button)
        settings_controls.addWidget(sync_now_button)
        settings_controls.addWidget(reset_device_button)
        settings_form.addRow("", settings_controls)

        status_group = QGroupBox("Статус")
        status_form = QFormLayout(status_group)
        status_form.addRow("Последний sync", self.status_label)
        status_form.addRow("Pending outbox", self.pending_label)
        status_form.addRow("Последняя ошибка", self.error_label)

        queue_group = QGroupBox("Очередь outbox")
        queue_layout = QVBoxLayout(queue_group)
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels(["UUID", "Type", "Datetime", "Status", "Try", "Error"])
        self.queue_table.horizontalHeader().setStretchLastSection(True)
        queue_layout.addWidget(self.queue_table)

        root.addWidget(settings_group)
        root.addWidget(status_group)
        root.addWidget(queue_group)

    def reload(self):
        settings = self.settings_service.get_settings()
        self.server_url_input.setText(settings["server_url"])
        self.site_uuid_input.setText(settings["site_uuid"])
        self.device_uuid_input.setText(settings["device_uuid"])
        self.device_token_input.setText(settings.get("device_token", ""))
        self.client_version_input.setText(settings.get("client_version", ""))
        self.enabled_checkbox.setChecked(settings["enabled"])

        queue = self.outbox_service.list_queue(limit=200)
        self.pending_label.setText(str(self.outbox_service.pending_count()))
        self.queue_table.setRowCount(len(queue))
        for i, row in enumerate(queue):
            self.queue_table.setItem(i, 0, QTableWidgetItem(str(row["event_uuid"])))
            self.queue_table.setItem(i, 1, QTableWidgetItem(str(row["event_type"])))
            self.queue_table.setItem(i, 2, QTableWidgetItem(str(row["event_datetime"])))
            self.queue_table.setItem(i, 3, QTableWidgetItem(str(row["status"])))
            self.queue_table.setItem(i, 4, QTableWidgetItem(str(row["try_count"])))
            self.queue_table.setItem(i, 5, QTableWidgetItem(str(row.get("last_error") or "")))
        self.queue_table.resizeColumnsToContents()

        self._load_sync_state()

    def _load_sync_state(self):
        with self.settings_service.db.get_connection() as conn:
            row = conn.execute("SELECT last_sync_at FROM sync_state WHERE id = 1").fetchone()
            self.status_label.setText(str(row["last_sync_at"]) if row and row["last_sync_at"] else "-")
            err = conn.execute(
                "SELECT last_error FROM sync_outbox WHERE last_error IS NOT NULL ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            self.error_label.setText(err["last_error"] if err else "-")

    def _save(self):
        try:
            self.settings_service.save_settings(
                server_url=self.server_url_input.text(),
                site_uuid=self.site_uuid_input.text(),
                enabled=self.enabled_checkbox.isChecked(),
                device_token=self.device_token_input.text(),
                client_version=self.client_version_input.text(),
            )
            QMessageBox.information(self, "Синхронизация", "Настройки сохранены")
            self.reload()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _sync_now(self):
        try:
            self.orchestrator.sync_once()
            QMessageBox.information(self, "Синхронизация", "Синхронизация выполнена")
        except Exception as exc:
            QMessageBox.warning(self, "Синхронизация", str(exc))
        self.reload()

    def _reset_device(self):
        reply = QMessageBox.question(self, "Сброс", "Сгенерировать новый device UUID?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.settings_service.reset_device_uuid()
        self.reload()
