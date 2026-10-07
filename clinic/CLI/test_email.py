import argparse
import smtplib

from pydantic import EmailStr, TypeAdapter

from Core.config import get_settings
from DAL.email import send_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a SMTP test email with local settings")
    parser.add_argument("--recipient", required=True, help="Email address receiving the test")
    args = parser.parse_args()
    recipient = str(TypeAdapter(EmailStr).validate_python(args.recipient))
    try:
        send_email(
            get_settings(),
            recipient,
            "ClinicFlow - Kiểm tra gửi email",
            "Đây là thư kiểm tra cấu hình SMTP của ứng dụng phòng khám. "
            "Nếu bạn nhận được thư này, cấu hình gửi email đã hoạt động.",
        )
    except (OSError, smtplib.SMTPException) as exc:
        parser.exit(1, f"SMTP test failed ({type(exc).__name__}). Check SMTP settings.\n")
    print("SMTP server accepted the test email. Check the recipient inbox and Spam folder.")


if __name__ == "__main__":
    main()
