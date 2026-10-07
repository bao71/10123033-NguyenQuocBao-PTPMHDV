import smtplib
import ssl
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from Core.config import Settings
from DAL.email import send_email, send_password_reset_email


def settings(**overrides) -> Settings:
    values = {
        "app_secret_key": "a" * 64,
        "DB_PASSWORD": "test-database-password",
        "smtp_host": "mailhog",
        "smtp_port": 1025,
        "smtp_from": "clinic@example.local",
        "smtp_username": None,
        "smtp_password": "",
        "smtp_starttls": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def gmail_settings() -> Settings:
    return settings(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_from="sender@gmail.com",
        smtp_username="sender@gmail.com",
        smtp_password="test-app-secret!",
        smtp_starttls=True,
    )


def test_gmail_encrypts_connection_before_authentication_and_sends_message():
    server = MagicMock()
    with patch("DAL.email.smtplib.SMTP") as connect:
        connect.return_value.__enter__.return_value = server
        send_email(gmail_settings(), "recipient@example.com", "Thử SMTP", "Nội dung thử")
    connect.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
    assert [call[0] for call in server.method_calls] == [
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "send_message",
    ]
    context = server.starttls.call_args.kwargs["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    server.login.assert_called_once_with("sender@gmail.com", "test-app-secret!")
    message = server.send_message.call_args.args[0]
    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "recipient@example.com"
    assert message["Subject"] == "Thử SMTP"
    assert "Nội dung thử" in message.get_content()


def test_mailhog_remains_usable_without_authentication():
    with patch("DAL.email.smtplib.SMTP") as connect:
        server = connect.return_value.__enter__.return_value
        send_password_reset_email(settings(), "recipient@example.com", "reset-code-example")
    server.login.assert_not_called()
    server.starttls.assert_not_called()
    message = server.send_message.call_args.args[0]
    assert "reset-code-example" in message.get_content()


def test_tls_failure_does_not_send_credentials_or_mail():
    with patch("DAL.email.smtplib.SMTP") as connect:
        server = connect.return_value.__enter__.return_value
        server.starttls.side_effect = smtplib.SMTPNotSupportedError("STARTTLS unavailable")
        with pytest.raises(smtplib.SMTPNotSupportedError):
            send_email(gmail_settings(), "recipient@example.com", "Test", "Test")
    server.login.assert_not_called()
    server.send_message.assert_not_called()


def test_reset_failure_does_not_log_token_password_or_server_response(caplog):
    with patch("DAL.email.smtplib.SMTP") as connect:
        server = connect.return_value.__enter__.return_value
        server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"server-response-private test-app-secret!"
        )
        send_password_reset_email(gmail_settings(), "recipient@example.com", "private-reset-code")
    assert "SMTPAuthenticationError" in caplog.text
    for secret in ("test-app-secret!", "private-reset-code", "server-response-private"):
        assert secret not in caplog.text
    server.send_message.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"smtp_username": "sender@gmail.com"},
        {"smtp_password": "must-stay-hidden"},
        {"smtp_username": "sender@gmail.com", "smtp_password": "must-stay-hidden"},
        {"smtp_host": "smtp.gmail.com"},
    ],
)
def test_incomplete_or_unencrypted_smtp_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError) as error:
        settings(**overrides)
    assert "must-stay-hidden" not in str(error.value)
