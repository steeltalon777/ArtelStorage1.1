from PyQt6.QtWidgets import (
    QCheckBox,
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


class UsersTab(QWidget):
    def __init__(self, users_service, parent=None):
        super().__init__(parent)
        self.users_service = users_service

        self.username_input = QLineEdit(self)
        self.full_name_input = QLineEdit(self)
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.is_admin_checkbox = QCheckBox("Администратор", self)

        self.table = QTableWidget(self)

        self._build_ui()
        self.reload_users()

    def _build_ui(self):
        root = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow("Логин:", self.username_input)
        form.addRow("ФИО:", self.full_name_input)
        form.addRow("Пароль:", self.password_input)
        form.addRow("Права:", self.is_admin_checkbox)

        buttons = QHBoxLayout()
        create_button = QPushButton("Создать")
        create_button.clicked.connect(self._create_user)
        update_button = QPushButton("Обновить профиль")
        update_button.clicked.connect(self._update_user)
        change_password_button = QPushButton("Сменить пароль")
        change_password_button.clicked.connect(self._change_password)
        toggle_admin_button = QPushButton("Переключить admin")
        toggle_admin_button.clicked.connect(self._toggle_admin)
        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(self._delete_user)
        refresh_button = QPushButton("Обновить список")
        refresh_button.clicked.connect(self.reload_users)

        buttons.addWidget(create_button)
        buttons.addWidget(update_button)
        buttons.addWidget(change_password_button)
        buttons.addWidget(toggle_admin_button)
        buttons.addWidget(delete_button)
        buttons.addStretch(1)
        buttons.addWidget(refresh_button)

        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Логин", "ФИО", "Admin"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._fill_form)

        root.addLayout(form)
        root.addLayout(buttons)
        root.addWidget(QLabel("Пользователи"))
        root.addWidget(self.table)

    def reload_users(self):
        users = self.users_service.get_all_users()
        self.table.setRowCount(len(users))

        for row, user in enumerate(users):
            self.table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self.table.setItem(row, 1, QTableWidgetItem(user.username))
            self.table.setItem(row, 2, QTableWidgetItem(user.full_name))
            self.table.setItem(row, 3, QTableWidgetItem("Да" if user.is_admin else "Нет"))

        self.table.resizeColumnsToContents()

    def _selected_user_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return int(item.text())

    def _fill_form(self):
        user_id = self._selected_user_id()
        if user_id is None:
            return

        user = self.users_service.get_user_by_id(user_id)
        if user is None:
            return

        self.username_input.setText(user.username)
        self.full_name_input.setText(user.full_name)
        self.password_input.clear()
        self.is_admin_checkbox.setChecked(bool(user.is_admin))

    def _create_user(self):
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text()
        is_admin = self.is_admin_checkbox.isChecked()

        if not username or not full_name or not password:
            QMessageBox.warning(self, "Пользователи", "Заполните логин, ФИО и пароль.")
            return

        try:
            self.users_service.create_user(username, full_name, password, is_admin)
            self.reload_users()
            self.password_input.clear()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _update_user(self):
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователи", "Выберите пользователя.")
            return

        full_name = self.full_name_input.text().strip()
        is_admin = self.is_admin_checkbox.isChecked()
        if not full_name:
            QMessageBox.warning(self, "Пользователи", "Введите ФИО.")
            return

        try:
            self.users_service.update_user(user_id, full_name=full_name, is_admin=is_admin)
            self.reload_users()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _change_password(self):
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователи", "Выберите пользователя.")
            return

        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Пользователи", "Введите новый пароль.")
            return

        try:
            changed = self.users_service.change_password(user_id, password)
            if changed:
                QMessageBox.information(self, "Пользователи", "Пароль изменен.")
            else:
                QMessageBox.warning(self, "Пользователи", "Пароль не изменен.")
            self.password_input.clear()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _toggle_admin(self):
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователи", "Выберите пользователя.")
            return

        try:
            changed = self.users_service.toggle_admin_status(user_id)
            if changed:
                self.reload_users()
            else:
                QMessageBox.warning(self, "Пользователи", "Не удалось изменить права.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _delete_user(self):
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.warning(self, "Пользователи", "Выберите пользователя.")
            return

        if not self.users_service.can_delete_user(user_id):
            QMessageBox.warning(self, "Пользователи", "Пользователь участвует в операциях и не может быть удален.")
            return

        reply = QMessageBox.question(
            self,
            "Удаление",
            "Удалить выбранного пользователя?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.users_service.delete_user(user_id)
            self.reload_users()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
