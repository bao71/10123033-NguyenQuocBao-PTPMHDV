from uuid import UUID

from pydantic import SecretStr

from Core.config import get_settings
from Core.errors import AuthenticationError, PermissionDeniedError
from Core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    password = "A-strong-test-password!9"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)
    assert not verify_password(password, None)


def test_access_token_round_trip_and_wrong_secret() -> None:
    settings = get_settings()
    user_id = UUID("10000000-0000-0000-0000-000000000005")
    token, expires_in = create_access_token(user_id, "Patient", settings)
    claims = decode_access_token(token, settings)

    assert claims.user_id == user_id
    assert claims.role == "Patient"
    assert expires_in == settings.jwt_access_minutes * 60

    wrong_settings = settings.model_copy(
        update={"app_secret_key": SecretStr("f" * 64)}
    )
    try:
        decode_access_token(token, wrong_settings)
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Token signed by another key was accepted")


def test_permission_error_reports_missing_permissions() -> None:
    error = PermissionDeniedError(["users.read"])
    assert error.status_code == 403
    assert error.details == {"missing_permissions": ["users.read"]}
