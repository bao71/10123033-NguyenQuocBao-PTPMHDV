import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.errors import AuthenticationError

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("invalid-password-used-only-for-timing-protection")


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: UUID
    role: str
    token_id: UUID


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    target = stored_hash or DUMMY_PASSWORD_HASH
    valid = password_hash.verify(password, target)
    return bool(stored_hash) and valid


def create_access_token(user_id: UUID, role: str, settings: Settings) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.jwt_access_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid4()),
        "iat": now,
        "nbf": now,
        "exp": expires,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(
        payload,
        settings.app_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, settings.jwt_access_minutes * 60


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.app_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "role", "type", "jti", "iat", "nbf", "exp"]},
        )
        if payload["type"] != "access":
            raise AuthenticationError()
        return AccessTokenClaims(
            user_id=UUID(payload["sub"]),
            role=str(payload["role"]),
            token_id=UUID(payload["jti"]),
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise AuthenticationError("Access token không hợp lệ hoặc đã hết hạn.") from exc


def create_refresh_token() -> tuple[str, str]:
    plain_token = secrets.token_urlsafe(48)
    return plain_token, hash_refresh_token(plain_token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
