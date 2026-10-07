# Gửi email bằng Gmail SMTP

SMTP (Simple Mail Transfer Protocol) là giao thức gửi email. Gmail cung cấp máy chủ SMTP; backend phòng khám kết nối máy chủ này để gửi thư từ tài khoản Google bạn cấu hình.

Luồng gửi: FastAPI → `DAL/email.py` → kết nối TLS tới `smtp.gmail.com:587` → đăng nhập bằng địa chỉ Gmail và App Password → gửi đến hộp thư người nhận. Gmail được dùng chung cho email đặt lại mật khẩu hiện tại và phần xác nhận/nhắc lịch sẽ triển khai ở bước 2.4.

## Chuẩn bị tài khoản Google

1. Bật [Xác minh hai bước](https://myaccount.google.com/security) cho tài khoản Gmail gửi thư.
2. Mở [Mật khẩu ứng dụng](https://myaccount.google.com/apppasswords), đặt tên `ClinicFlow` và tạo mật khẩu riêng cho ứng dụng.
3. Dùng mã 16 ký tự Google cấp để cấu hình SMTP. Mật khẩu đăng nhập Google thường ngày không dùng ở trường này. Không gửi mã vào chat, Git hay Postman.

Nếu không thấy mục Mật khẩu ứng dụng, tài khoản có thể bị giới hạn bởi chính sách công ty/trường học, Advanced Protection hoặc cấu hình xác minh chỉ bằng security key. Khi đó cần kiểm tra chính sách Google hoặc dùng OAuth của Google; JWT đăng nhập phòng khám là cơ chế độc lập. [Hướng dẫn App Password của Google](https://support.google.com/accounts/answer/185833).

## Cấu hình tại máy của bạn

Chạy từ gốc `BTL_PTPMHDV`:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\configure-gmail.ps1
```

Nhập địa chỉ Gmail gửi thư rồi nhập App Password ở lời nhắc ẩn. Script loại bỏ khoảng trắng khi dán mã và chỉ cập nhật các dòng SMTP trong `clinic/.env`. `.env` đã được loại khỏi Git. Script không in mật khẩu ra màn hình.

Cấu hình được ghi:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM=your-address@gmail.com
SMTP_USERNAME=your-address@gmail.com
SMTP_PASSWORD=<App Password của bạn>
SMTP_STARTTLS=true
SMTP_TIMEOUT_SECONDS=30
```

Thông số host, cổng và TLS theo [hướng dẫn cấu hình SMTP của Google](https://support.google.com/mail/answer/7104828). `SMTP_FROM` dùng cùng địa chỉ đăng nhập; không giả địa chỉ gửi tùy ý.

## Khởi động và thử gửi

```powershell
cd clinic
docker compose up -d --build api
docker compose exec -T api python -m CLI.test_email --recipient your-address@gmail.com
```

Thay địa chỉ nhận bằng hộp thư của bạn. Lệnh này gửi một email thử, không chứa dữ liệu bệnh nhân. Nếu SMTP chấp nhận thư, kiểm tra Inbox và Spam để xác nhận nhận được thực tế.

Sau đó thử **Quên mật khẩu** bằng email của một tài khoản đã đăng ký trong ứng dụng. Mã sẽ được gửi đến hộp thư thật của tài khoản đó. Phản hồi API vẫn giống nhau cho email có hoặc không có tài khoản, nên phản hồi thành công không đồng nghĩa thư đã được giao.

Nếu gặp `SMTPAuthenticationError`, kiểm tra App Password, xác minh hai bước và chính sách tài khoản. Google có thể thu hồi App Password khi đổi mật khẩu tài khoản; cần tạo lại mã và chạy lại script. Nếu gặp lỗi kết nối, kiểm tra kết nối Internet/cổng 587. Chi tiết lỗi gửi được ghi với tên loại lỗi, không ghi mã đặt lại hoặc mật khẩu SMTP.

## Kiểm thử và các file

`scripts/test.ps1` ép cấu hình SMTP của tiến trình pytest sang MailHog để các email của tài khoản giả không gửi ra Gmail. Cấu hình API đang chạy vẫn dùng nhà cung cấp bạn đã chọn. Unit test kiểm tra TLS trước đăng nhập, xác minh chứng chỉ, lỗi TLS và che thông tin nhạy cảm.

- `Core/config.py`: đọc host, cổng, tài khoản, mật khẩu và TLS; kiểm tra cấu hình.
- `DAL/email.py`: gửi SMTP, dùng STARTTLS và đăng nhập khi có cấu hình.
- `compose.yaml`: truyền cấu hình SMTP từ `.env` vào container.
- `scripts/configure-gmail.ps1`: nhập và lưu thông tin Gmail tại máy.
- `CLI/test_email.py`: gửi một thư kiểm tra theo địa chỉ bạn chỉ định.

Phần xác nhận/nhắc lịch và thông báo in-app của bước 2.4 chưa được triển khai trong thay đổi cấu hình SMTP này.
