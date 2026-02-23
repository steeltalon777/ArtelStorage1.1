import argparse
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMessageBox

from core.auth import AuthManager
from core.db import init_database
from core.paths import get_default_db_path
from ui.auth_dialog import LoginDialog
from .ui.admin_window import AdminWindow


def _resolve_db_path(cli_db_path: Optional[str]) -> str:
    if cli_db_path:
        return str(Path(cli_db_path).resolve())
    return str(get_default_db_path().resolve())


def _admin_login(auth_manager) -> object:
    while True:
        dialog = LoginDialog(auth_manager)
        if dialog.exec() != LoginDialog.DialogCode.Accepted:
            return None

        result = dialog.auth_result
        if not result or not result.success or not result.user:
            continue

        if not result.user.is_admin:
            QMessageBox.warning(None, "Доступ запрещен", "Требуются права администратора.")
            auth_manager.logout()
            continue

        return result.user


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Административное приложение ArtelStorage")
    parser.add_argument("--db", help="Путь к файлу базы данных SQLite", default=None)
    args = parser.parse_args(argv)

    app = QApplication(sys.argv)

    try:
        db_path = _resolve_db_path(args.db)
        init_database(db_path)

        auth_manager = AuthManager(db_path)
        auth_manager.initialize_admin_user()

        user = _admin_login(auth_manager)
        if user is None:
            return 0

        window = AdminWindow(db_path, user)
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(None, "Ошибка", f"Ошибка запуска админки:\n{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
