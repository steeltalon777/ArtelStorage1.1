from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ImportExportTab(QWidget):
    def __init__(self, db_path, export_service, import_service, on_import_finished=None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.export_service = export_service
        self.import_service = import_service
        self.on_import_finished = on_import_finished

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        export_button = QPushButton("Экспорт всех данных")
        export_button.clicked.connect(self._export_data)
        import_button = QPushButton("Импорт данных")
        import_button.clicked.connect(self._import_data)

        controls.addWidget(export_button)
        controls.addWidget(import_button)
        controls.addStretch(1)

        root.addLayout(controls)
        root.addStretch(1)

    def _export_data(self):
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
            "Подтверждение",
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
            if callable(self.on_import_finished):
                self.on_import_finished()
            QMessageBox.information(self, "Импорт", "Данные успешно импортированы.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка импорта", str(exc))
        finally:
            progress.close()
