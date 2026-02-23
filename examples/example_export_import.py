"""Пример экспорта/импорта через сервисы ядра."""

from pathlib import Path

from core.db import init_database
from core.services.export_service import ExportService
from core.services.import_service import ImportService


def main():
    db_path = Path("db/storage.db")
    snapshot_path = Path("db/example_snapshot.json")

    init_database(str(db_path))

    exporter = ExportService(str(db_path))
    exporter.export_to_file(str(snapshot_path))
    print(f"Exported: {snapshot_path}")

    importer = ImportService(str(db_path))
    importer.import_from_file(str(snapshot_path))
    print("Imported snapshot back to database")


if __name__ == "__main__":
    main()
