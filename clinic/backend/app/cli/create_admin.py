import argparse
import re
from getpass import getpass
from uuid import UUID, uuid4

import pyodbc
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.security import hash_password
from app.db import connect
from app.repositories.auth_repository import AuthRepository

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,50}$")


def create_admin(username: str, email: str, password: str) -> UUID:
    username = username.strip().lower()
    email = str(TypeAdapter(EmailStr).validate_python(email.strip().lower()))
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username phải có 3-50 ký tự: chữ, số, dấu chấm, gạch ngang hoặc _.")
    if len(password) < 10 or len(password) > 128:
        raise ValueError("Mật khẩu phải có từ 10 đến 128 ký tự.")

    repository = AuthRepository()
    connection = connect()
    try:
        duplicate = repository.duplicate_registration_field(connection, username, email, None)
        if duplicate:
            raise ValueError(f"Thông tin {duplicate} đã được sử dụng.")
        row = connection.execute(
            """
            INSERT INTO dbo.users(role_id, username, email, password_hash)
            OUTPUT inserted.user_id
            SELECT role_id, ?, ?, ? FROM dbo.roles WHERE code='Admin';
            """,
            username,
            email,
            hash_password(password),
        ).fetchone()
        if row is None:
            raise RuntimeError("Không tìm thấy vai trò Admin trong database.")
        user_id = UUID(str(row.user_id))
        repository.audit(
            connection,
            action="admin.bootstrap",
            entity_type="users",
            actor_user_id=user_id,
            entity_id=user_id,
            after={"username": username, "role": "Admin"},
            ip_address=None,
            user_agent="create_admin_cli",
            request_id=uuid4(),
        )
        connection.commit()
        return user_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo tài khoản Admin đầu tiên.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass("Mật khẩu Admin: ")
    confirmation = getpass("Nhập lại mật khẩu: ")
    if password != confirmation:
        parser.error("Hai mật khẩu không giống nhau.")
    try:
        user_id = create_admin(args.username, args.email, password)
    except (ValueError, ValidationError, pyodbc.Error) as exc:
        parser.error(str(exc))
    print(f"Đã tạo tài khoản Admin: {user_id}")


if __name__ == "__main__":
    main()
