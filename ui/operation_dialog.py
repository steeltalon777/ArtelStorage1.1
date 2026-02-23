from uuid import UUID

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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


TYPE_LABELS = {
    "incoming": "Приход",
    "issue": "Расход (выдача)",
    "writeoff": "Списание",
    "move": "Перемещение",
}


class OperationDialog(QDialog):
    def __init__(self, operations_service, user, parent=None):
        super().__init__(parent)
        self.operations_service = operations_service
        self.user = user
        self.lines = []

        self.setWindowTitle("Создание операции")
        self.setMinimumSize(920, 680)

        self.type_combo = QComboBox(self)
        self.type_combo.addItem(TYPE_LABELS["incoming"], "incoming")
        self.type_combo.addItem(TYPE_LABELS["issue"], "issue")
        self.type_combo.addItem(TYPE_LABELS["writeoff"], "writeoff")
        self.type_combo.addItem(TYPE_LABELS["move"], "move")
        self.type_combo.currentIndexChanged.connect(self._update_type_fields)

        self.recipient_input = QLineEdit(self)
        self.recipient_input.setPlaceholderText("ФИО получателя")
        self.vehicle_input = QLineEdit(self)
        self.vehicle_input.setPlaceholderText("Номер машины")
        self.target_site_input = QLineEdit(self)
        self.target_site_input.setPlaceholderText("Объект-получатель")
        self.comment_input = QLineEdit(self)

        self.item_combo = QComboBox(self)
        self.qty_spin = QDoubleSpinBox(self)
        self.qty_spin.setDecimals(3)
        self.qty_spin.setMaximum(1_000_000)
        self.qty_spin.setMinimum(0.001)

        self.lines_table = QTableWidget(self)
        self.recent_table = QTableWidget(self)

        self._build_ui()
        self._load_items()
        self._load_recent_operations()
        self._update_type_fields()

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow("Тип:", self.type_combo)
        form.addRow("Получатель:", self.recipient_input)
        form.addRow("Транспорт:", self.vehicle_input)
        form.addRow("Объект назначения:", self.target_site_input)
        form.addRow("Комментарий:", self.comment_input)

        lines_group = QGroupBox("Позиции ТМЦ")
        lines_layout = QVBoxLayout(lines_group)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("ТМЦ:"))
        add_row.addWidget(self.item_combo, 1)
        add_row.addWidget(QLabel("Кол-во:"))
        add_row.addWidget(self.qty_spin)

        add_button = QPushButton("Добавить позицию")
        add_button.clicked.connect(self._add_line)
        remove_button = QPushButton("Удалить выбранную")
        remove_button.clicked.connect(self._remove_line)

        self.lines_table.setColumnCount(4)
        self.lines_table.setHorizontalHeaderLabels(["Инв. номер", "ТМЦ", "Ед.", "Кол-во"])
        self.lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lines_table.horizontalHeader().setStretchLastSection(True)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch(1)

        lines_layout.addLayout(add_row)
        lines_layout.addLayout(buttons_row)
        lines_layout.addWidget(self.lines_table)

        recent_group = QGroupBox("Последние операции (до 15)")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_table.setColumnCount(5)
        self.recent_table.setHorizontalHeaderLabels(["Дата", "Операция", "Получатель", "Транспорт", "Строк"])
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        recent_layout.addWidget(self.recent_table)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        dialog_buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Провести")
        dialog_buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        dialog_buttons.accepted.connect(self._submit)
        dialog_buttons.rejected.connect(self.reject)

        root.addLayout(form)
        root.addWidget(lines_group)
        root.addWidget(recent_group)
        root.addWidget(dialog_buttons)

    def _load_items(self):
        self.item_combo.clear()
        for item in self.operations_service.get_item_catalog():
            label = f"{item['name']} ({item['unit']})"
            self.item_combo.addItem(label, item)

    def _load_recent_operations(self):
        ops = self.operations_service.list_recent_operations(limit=15)
        self.recent_table.setRowCount(len(ops))

        for row, op in enumerate(ops):
            self.recent_table.setItem(row, 0, QTableWidgetItem(str(op["created_at"])))
            self.recent_table.setItem(row, 1, QTableWidgetItem(TYPE_LABELS.get(op["type"], op["type"])))
            self.recent_table.setItem(row, 2, QTableWidgetItem(op.get("recipient_name") or "-"))
            self.recent_table.setItem(row, 3, QTableWidgetItem(op.get("vehicle") or "-"))
            self.recent_table.setItem(row, 4, QTableWidgetItem(str(op.get("lines_count") or 0)))

        self.recent_table.resizeColumnsToContents()

    def _update_type_fields(self):
        op_type = self.type_combo.currentData()

        is_issue = op_type == "issue"
        is_move = op_type == "move"

        self.recipient_input.setEnabled(is_issue)
        self.vehicle_input.setEnabled(is_issue or is_move)
        self.target_site_input.setEnabled(is_move)

        if not is_issue:
            self.recipient_input.clear()
        if not (is_issue or is_move):
            self.vehicle_input.clear()
        if not is_move:
            self.target_site_input.clear()

    def _add_line(self):
        item_data = self.item_combo.currentData()
        if not item_data:
            QMessageBox.warning(self, "Операция", "Справочник ТМЦ пуст.")
            return

        qty = float(self.qty_spin.value())
        if qty <= 0:
            QMessageBox.warning(self, "Операция", "Количество должно быть больше 0.")
            return

        line = {
            "item_id": item_data["id"],
            "item_name": item_data["name"],
            "unit": item_data["unit"],
            "qty": qty,
        }
        self.lines.append(line)
        self._render_lines()

    def _remove_line(self):
        row = self.lines_table.currentRow()
        if row < 0:
            return
        del self.lines[row]
        self._render_lines()

    def _render_lines(self):
        self.lines_table.setRowCount(len(self.lines))
        for row, line in enumerate(self.lines):
            self.lines_table.setItem(row, 0, QTableWidgetItem(str(line["item_id"])))
            self.lines_table.setItem(row, 1, QTableWidgetItem(line["item_name"]))
            self.lines_table.setItem(row, 2, QTableWidgetItem(line["unit"]))
            self.lines_table.setItem(row, 3, QTableWidgetItem(f"{line['qty']:g}"))
        self.lines_table.resizeColumnsToContents()

    def _submit(self):
        if not self.lines:
            QMessageBox.warning(self, "Операция", "Добавьте хотя бы одну позицию ТМЦ.")
            return

        op_type = self.type_combo.currentData()
        recipient = self.recipient_input.text().strip() or None
        vehicle = self.vehicle_input.text().strip() or None
        target_site = self.target_site_input.text().strip() or None
        comment = self.comment_input.text().strip() or None

        try:
            operation_id = self.operations_service.create_operation(
                operation_type=op_type,
                created_by=self.user.id,
                lines=[{"item_id": UUID(str(line["item_id"])), "qty": line["qty"]} for line in self.lines],
                recipient_name=recipient,
                vehicle=vehicle,
                target_site_name=target_site,
                comment=comment,
            )
            QMessageBox.information(self, "Операция", f"Операция проведена: {operation_id}")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка операции", str(exc))
