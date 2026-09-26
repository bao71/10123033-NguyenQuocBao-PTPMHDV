import logging
import smtplib
from email.message import EmailMessage

from Core.config import Settings

logger = logging.getLogger("clinic.email")


def send_password_reset_email(
    settings: Settings, recipient: str, token: str
) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = "Đặt lại mật khẩu phòng khám"
    message.set_content(
        "Bạn đã yêu cầu đặt lại mật khẩu.\n\n"
        f"Mã đặt lại: {token}\n\n"
        f"Mã có hiệu lực trong {settings.password_reset_minutes} phút và chỉ dùng một lần. "
        "Trên giao diện, chọn Quên mật khẩu rồi Tôi đã có mã đặt lại, "
        "sau đó nhập mã và mật khẩu mới. "
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("password_reset_email_failed")
