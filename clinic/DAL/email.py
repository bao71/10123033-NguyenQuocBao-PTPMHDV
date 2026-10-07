import logging
import smtplib
import ssl
from email.message import EmailMessage

from Core.config import Settings

logger = logging.getLogger("clinic.email")


def send_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    """Send through SMTP; errors propagate so background workers can retry."""
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as server:
        server.ehlo()
        if settings.smtp_starttls:
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        server.send_message(message)


def send_password_reset_email(
    settings: Settings, recipient: str, token: str
) -> None:
    body = (
        "Bạn đã yêu cầu đặt lại mật khẩu.\n\n"
        f"Mã đặt lại: {token}\n\n"
        f"Mã có hiệu lực trong {settings.password_reset_minutes} phút và chỉ dùng một lần. "
        "Trên giao diện, chọn Quên mật khẩu rồi Tôi đã có mã đặt lại, "
        "sau đó nhập mã và mật khẩu mới. "
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )
    try:
        send_email(settings, recipient, "Đặt lại mật khẩu phòng khám", body)
    except (OSError, smtplib.SMTPException) as exc:
        # SMTP error responses can contain addresses or server details. Do not
        # log the reset token, message body, password or raw server response.
        logger.error("password_reset_email_failed: %s", type(exc).__name__)
