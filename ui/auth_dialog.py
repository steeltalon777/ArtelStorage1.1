from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class LoginDialog(QDialog):
    """Modal authentication dialog for username/password login."""

    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.auth_result = None

        self.setWindowTitle("Вход в систему")
        self.setModal(True)
        self.setMinimumWidth(380)

        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("Логин")
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Пароль")

        form = QFormLayout()
        form.addRow("Пользователь:", self.username_input)
        form.addRow("Пароль:", self.password_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c0392b;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Войти")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

        self.username_input.setFocus()

    def _try_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("Введите логин и пароль.")
            return

        result = self.auth_manager.authenticate(username, password)
        if not result.success:
            self.error_label.setText(result.error or "Ошибка аутентификации")
            self.password_input.selectAll()
            self.password_input.setFocus()
            return

        self.auth_result = result
        self.accept()
