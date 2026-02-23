"""Пример управления пользователями через сервис."""

from pathlib import Path

from core.db import init_database
from core.services.users_service import UsersService


def main():
    db_path = Path("db/storage.db")
    init_database(str(db_path))

    users_service = UsersService(str(db_path))

    try:
        user = users_service.create_user("demo_user", "Demo User", "demo123", False)
        print(f"Created user id={user.id}")
    except ValueError as exc:
        print(f"Skip create: {exc}")

    users = users_service.get_all_users()
    print(f"Total users: {len(users)}")


if __name__ == "__main__":
    main()
