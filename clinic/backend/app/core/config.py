from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CLINIC_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CLINIC_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Clinic Management API"
    app_env: str = "development"
    app_secret_key: SecretStr
    app_cors_origins: str = "http://localhost:4200,http://127.0.0.1:4200"

    db_server: str = "127.0.0.1"
    db_port: int = 14331
    db_name: str = "ClinicManagement"
    db_user: str = Field(
        default="clinic_app",
        validation_alias=AliasChoices("DB_USER", "MSSQL_APP_USER"),
    )
    db_password: SecretStr = Field(
        validation_alias=AliasChoices("DB_PASSWORD", "MSSQL_APP_PASSWORD")
    )
    db_driver: str = "ODBC Driver 18 for SQL Server"
    db_encrypt: str = "yes"
    db_trust_server_certificate: str = "yes"
    db_connection_timeout_seconds: int = 10

    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "clinic-management-api"
    jwt_audience: str = "clinic-management-client"
    jwt_access_minutes: int = 30
    refresh_token_days: int = 14
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    auth_rate_limit_per_minute: int = 20

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.app_cors_origins.split(",") if item.strip()]

    @staticmethod
    def _odbc_value(value: str) -> str:
        return "{" + value.replace("}", "}}") + "}"

    @property
    def database_connection_string(self) -> str:
        return ";".join(
            (
                f"DRIVER={self._odbc_value(self.db_driver)}",
                f"SERVER={self.db_server},{self.db_port}",
                f"DATABASE={self.db_name}",
                f"UID={self.db_user}",
                f"PWD={self._odbc_value(self.db_password.get_secret_value())}",
                f"Encrypt={self.db_encrypt}",
                f"TrustServerCertificate={self.db_trust_server_certificate}",
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
