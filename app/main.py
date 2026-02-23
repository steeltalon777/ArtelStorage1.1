import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtWidgets import QApplication, QMessageBox

from core.auth import AuthManager
from core.db import init_database
from core.paths import get_default_db_path
from ui.auth_dialog import LoginDialog
from ui.main_window import MainWindow


class AppController:
    def __init__(self, qt_app: QApplication, db_path: str):
        self.qt_app = qt_app
        self.db_path = db_path
        self.auth_manager = AuthManager(db_path)
        self.main_window = None

    def start(self):
        if not self._show_login():
            self.qt_app.quit()

    def _show_login(self) -> bool:
        while True:
            dialog = LoginDialog(self.auth_manager)
            if dialog.exec() != LoginDialog.DialogCode.Accepted:
                return False

            result = dialog.auth_result
            if result and result.success and result.user:
                self._show_main_window(result.user)
                return True

    def _show_main_window(self, user):
        self.main_window = MainWindow(self.db_path, self.auth_manager, user)
        self.main_window.logout_requested.connect(self._on_logout_requested)
        self.main_window.show()

    def _on_logout_requested(self):
        self.auth_manager.logout()
        if self.main_window is not None:
            self.main_window.close()
            self.main_window = None

        if not self._show_login():
            self.qt_app.quit()


def main() -> int:
    app = QApplication(sys.argv)

    try:
        db_path = get_default_db_path()
        init_database(str(db_path))

        auth_manager = AuthManager(str(db_path))
        auth_manager.initialize_admin_user()

        controller = AppController(app, str(db_path))
        controller.auth_manager = auth_manager
        controller.start()

        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, "Ошибка", f"Ошибка запуска:\n{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
