# Tiếp nhận bệnh nhân (Master Plan 2.5)

## Thử trên web

Mở `http://127.0.0.1:8000/app/`, đăng nhập tài khoản **Lễ tân**, chọn **Tiếp nhận**.
Mặc định hiển thị lịch hôm nay theo giờ Việt Nam (UTC+7). Có thể chọn ngày,
bác sĩ, trạng thái, tìm tên/mã, sắp xếp giờ hẹn và chuyển trang.

- **Đặt lịch tại quầy**: mở form đặt lịch cho bệnh nhân, sử dụng giờ trống của bác sĩ.
- **Hồ sơ bệnh nhân**: mở form tạo thông tin hành chính cho bệnh nhân mới.
- **Xác nhận lịch**: chuyển lịch `booked` trong tương lai thành `confirmed`.
- **Check-in**: chuyển `booked` hoặc `confirmed` thành `checked_in` trong đúng ngày hẹn.
  Cho phép bệnh nhân đến sớm hoặc muộn trong ngày. Sau check-in, bệnh nhân chờ bác sĩ.
- **Vắng hẹn**: chuyển `booked` hoặc `confirmed` thành `no_show` sau khi hết lượt khám.
- **Thông tin bệnh nhân**: mở hồ sơ hành chính. Lễ tân không được đọc tiền sử/dị ứng theo quyền mặc định.
- **Làm mới**: cập nhật danh sách và số lượt chờ khám sau các thao tác của nhân viên khác.

Bệnh nhân mở **Lịch hẹn**, bấm **Làm mới** để xem trạng thái mới. Khi đã check-in,
web hiển thị thông báo chờ bác sĩ và ẩn thao tác đổi/hủy. Bác sĩ thấy lịch của mình;
việc bắt đầu/hoàn tất khám sẽ được triển khai ở giai đoạn Khám bệnh.

## API

Tất cả request cần `Authorization: Bearer <access_token>`.

| Method | URL | Quyền |
| --- | --- | --- |
| GET | `/api/v1/reception` | `appointments.check_in` và `appointments.read` |
| POST | `/api/v1/appointments/{id}/confirm` | `appointments.update` và `appointments.read` |
| POST | `/api/v1/appointments/{id}/check-in` | `appointments.check_in` và `appointments.read` |
| POST | `/api/v1/appointments/{id}/no-show` | `appointments.check_in` và `appointments.read` |

GET hỗ trợ `work_date=YYYY-MM-DD` (mặc định hôm nay), `doctor_id`, `search`, `status`,
`sort_order=asc|desc`, `page` và `page_size` (tối đa 100).
`total` là số lịch sau lọc trạng thái; `summary` là thống kê của ngày/bác sĩ/từ khóa,
không thay đổi theo trang hay bộ lọc trạng thái.

Body của cả ba POST:

```json
{"version": "0000000000000001"}
```

Lấy `version` mới nhất từ GET lịch hẹn hoặc danh sách tiếp nhận; không sử dụng giá trị ví dụ.
POST trả về lịch hẹn với trạng thái và `version` mới. Collection mẫu nằm ở
`docs/postman/Reception.postman_collection.json`.

Không chuyển lại lịch đã check-in, đang khám, đã khám, đã hủy hoặc vắng hẹn.
Nếu lịch đã có `encounter`, các thao tác tiếp nhận bị từ chối để tránh lệch hồ sơ khám.
Xác nhận/check-in cũng kiểm tra bác sĩ và ca làm còn hoạt động.

## Luồng và database

`API/routes/reception.py` → `BLL/reception_service.py` →
`DAL/reception_repository.py` → `DAL/procedures.py` →
`Database/procedures/reception.sql`.

Không thêm bảng. Procedure đọc `appointments`, `patients`, `doctors`, `users`;
kiểm tra `doctor_schedules`, `encounters` khi đổi trạng thái. Mỗi thay đổi và audit log
(người thao tác, trạng thái cũ/mới, thời điểm, request ID) được commit chung transaction.
`row_version` cùng khóa `clinic-appointments-write` ngăn hai request cập nhật trùng nhau.
Không tự tạo bệnh án khi Lễ tân check-in.

Chạy lại `db-init` hoặc `scripts/start.ps1` để áp dụng `CREATE OR ALTER` procedure mới.

## Tiến độ và kiểm thử

2.4 (nhắc lịch email/in-app) và cấu hình Gmail đang **tạm hoãn** theo yêu cầu.
MailHog vẫn dùng cho email kiểm thử. 2.5 cung cấp giao diện Bệnh nhân/Lễ tân
cho đặt lịch và tiếp nhận; không gồm các màn hình khám, đơn thuốc, thu phí của giai đoạn sau.

`Tests/test_reception.py` kiểm tra phân quyền, rollback khi audit lỗi, ánh xạ lỗi SQL,
và payload version. `Tests/test_reception_integration.py` kiểm tra trạng thái trên SQL Server,
giới hạn thời gian, phạm vi Bệnh nhân/Bác sĩ, phân trang, tìm kiếm, múi giờ và hai check-in đồng thời.

## File của bước 2.5

Tạo mới:

- `Model/reception.py`: payload và response tiếp nhận.
- `API/routes/reception.py`: danh sách tiếp nhận và ba API chuyển trạng thái.
- `BLL/reception_service.py`: quyền, transaction và audit.
- `DAL/reception_repository.py`: gọi stored procedure bằng pyodbc.
- `Database/procedures/reception.sql`: danh sách, thống kê và kiểm soát chuyển trạng thái.
- `Tests/test_reception.py`, `Tests/test_reception_integration.py`: unit/integration test.
- `docs/reception.md`, `docs/postman/Reception.postman_collection.json`: hướng dẫn và request mẫu.

Cập nhật `API/router.py`, `BLL/appointment_service.py`, `Frontend/index.html`,
`Frontend/assets/app.js`, `Frontend/assets/app.css`, `README.md`,
`docs/stored-procedures.md` và `docs/master-plan/Master Plan.xlsx`.
Trong Master Plan, mục 2.4 được đánh dấu **Tạm hoãn / 0%**; mục 2.5 giữ **Đã hoàn thành / 100%**.
Các phần định dạng và nội dung khác của workbook được giữ nguyên.
