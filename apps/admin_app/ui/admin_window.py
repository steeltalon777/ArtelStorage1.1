from PyQt6.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from core.services.categories_service import CategoriesService
from core.services.export_service import ExportService
from core.services.import_service import ImportService
from core.services.items_service import ItemsService
from core.services.users_service import UsersService

from .categories_tab import CategoriesTab
from .import_export_tab import ImportExportTab
from .items_tab import ItemsTab
from .sync_tab import SyncTab
from .users_tab import UsersTab


class AdminWindow(QMainWindow):
    def __init__(self, db_path, current_user, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.current_user = current_user

        self.items_service = ItemsService(db_path)
        self.categories_service = CategoriesService(db_path)
        self.users_service = UsersService(db_path)
        self.export_service = ExportService(db_path)
        self.import_service = ImportService(db_path)

        self.setWindowTitle("ArtelStorage Admin")
        self.resize(1200, 780)

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.items_tab = ItemsTab(self.items_service, self.categories_service, self)
        self.categories_tab = CategoriesTab(self.categories_service, self)
        self.users_tab = UsersTab(self.users_service, self)
        self.import_export_tab = ImportExportTab(
            db_path,
            self.export_service,
            self.import_service,
            on_import_finished=self._reload_all,
            parent=self,
        )
        self.sync_tab = SyncTab(db_path, self)

        self.tabs.addTab(self.items_tab, "ТМЦ")
        self.tabs.addTab(self.categories_tab, "Категории")
        self.tabs.addTab(self.users_tab, "Пользователи")
        self.tabs.addTab(self.import_export_tab, "Экспорт/Импорт")
        self.tabs.addTab(self.sync_tab, "Синхронизация")

        status = QStatusBar(self)
        self.setStatusBar(status)
        status.showMessage(
            f"Администратор: {self.current_user.full_name} ({self.current_user.username})"
        )

    def _reload_all(self):
        self.categories_tab.reload_categories()
        self.items_tab.reload_categories()
        self.items_tab.reload_items()
        self.users_tab.reload_users()
        self.sync_tab.reload()
