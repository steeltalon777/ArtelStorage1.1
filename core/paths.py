import os
import sys
from pathlib import Path


def get_documents_dir() -> Path:
    """Best-effort resolve of Windows 'Documents' folder."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            _FOLDERID_Documents = ctypes.c_wchar_p("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")

            shell32 = ctypes.WinDLL("shell32", use_last_error=True)
            ole32 = ctypes.WinDLL("ole32", use_last_error=True)

            ppsz_path = wintypes.LPWSTR()
            hr = shell32.SHGetKnownFolderPath(_FOLDERID_Documents, 0, 0, ctypes.byref(ppsz_path))
            if hr == 0 and ppsz_path.value:
                try:
                    return Path(ppsz_path.value)
                finally:
                    ole32.CoTaskMemFree(ppsz_path)
        except Exception:
            pass

    # Fallbacks
    home = Path.home()
    for candidate in (home / "Documents", home / "Документы", Path(os.environ.get("USERPROFILE", str(home))) / "Documents"):
        if candidate.exists():
            return candidate
    return home


def get_app_data_dir(app_name: str = "ArtelStorage") -> Path:
    base = get_documents_dir() / app_name
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_default_db_path(app_name: str = "ArtelStorage") -> Path:
    return get_app_data_dir(app_name) / "storage.db"


def get_pdf_dir(app_name: str = "ArtelStorage") -> Path:
    pdf_dir = get_app_data_dir(app_name) / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir
