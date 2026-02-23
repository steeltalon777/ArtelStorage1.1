# INSTALLER

## Цель
Один установщик Windows, внутри которого 2 приложения:
- `ArtelStorage` (основное)
- `ArtelStorage Admin` (админка)

Данные (БД и PDF) по умолчанию хранятся в “Мои документы\\ArtelStorage” и не зависят от папки установки.

## Шаг 1: собрать 2 exe (PyInstaller)
В PowerShell из корня проекта:
```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --clean --windowed --name ArtelStorage main_app.py
pyinstaller --noconfirm --clean --windowed --name ArtelStorageAdmin admin_app.py
```

Либо скриптом:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\\build_exe.ps1 -Clean
```

После этого должны появиться:
- `dist\\ArtelStorage\\ArtelStorage.exe`
- `dist\\ArtelStorageAdmin\\ArtelStorageAdmin.exe`

## Шаг 2: собрать инсталлятор (Inno Setup)
1. Установить Inno Setup.
2. Открыть `installer\\ArtelStorage.iss`.
3. Compile.

Результат: `dist_installer\\ArtelStorage_1.1_Setup.exe`.

## Ярлыки
Инсталлятор создаёт 2 ярлыка в меню Пуск и (опционально) на рабочем столе:
- `ArtelStorage`
- `ArtelStorage Admin`

## Примечания
- По умолчанию `installer\\ArtelStorage.iss` настроен на установку в `Program Files` (нужны права администратора).
- Если нужен per-user install, поменяйте `DefaultDirName` и `PrivilegesRequired` в `installer\\ArtelStorage.iss`.
