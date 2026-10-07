# Lịch hẹn — bước 2.3

## Luồng thử trên web

1. Admin tạo Bác sĩ và Lễ tân ở trang Tài khoản nếu chưa có.
2. Admin hoặc Lễ tân mở Lịch hẹn → Ca làm: chọn bác sĩ, ngày trong tương lai, ví dụ 08:00–11:00, 30 phút/lượt. Giờ nhập/hiển thị là giờ Việt Nam.
3. Bệnh nhân đăng nhập → Lịch hẹn → Đặt lịch: chọn bác sĩ/ngày, chọn giờ còn trống, nhập lý do và xác nhận.
4. Lễ tân có thể đặt giúp bằng cách tìm hồ sơ bệnh nhân theo tên/mã/điện thoại. Hồ sơ chưa có tài khoản vẫn đặt được.
5. Bác sĩ xem lịch được giao rồi mở trang Bệnh nhân để xem tiền sử/dị ứng của bệnh nhân đó.
6. Bệnh nhân/Lễ tân đổi sang giờ còn trống hoặc hủy và nhập lý do. Lịch hủy được giữ để tra cứu; slot được mở lại.

## Quyền mặc định

| Vai trò | Xem lịch | Đặt/đổi/hủy | Ca làm |
| --- | --- | --- | --- |
| Admin | Toàn bộ | Không | Xem, tạo, hủy |
| Lễ tân | Toàn bộ | Toàn bộ | Xem, tạo, hủy |
| Bác sĩ | Được phân công | Không | Xem |
| Bệnh nhân | Của mình | Của mình | Xem |
| Dược sĩ | Không | Không | Không |

Quyền được kiểm tra lại ở API, phạm vi bản ghi cũng được kiểm tra trong procedure. Không thể đổi `patient_id` của một lịch; đổi bác sĩ vẫn phải qua kiểm tra ca và giờ trống.

## Payload Postman/Swagger

Dùng `Authorization: Bearer <access_token>`. Lấy ID bác sĩ từ `GET /api/v1/doctors`. Tạo ca bằng tài khoản Admin/Lễ tân:

Có thể import [Postman collection bước 2.3](postman/Appointments.postman_collection.json), điền `access_token` của Lễ tân, `patient_id`, `doctor_id` và ngày/giờ cần thử. Collection tự lưu ID/version sau các request thành công.

```json
{
  "doctor_id": "<doctor_id>",
  "start_at": "2030-01-02T08:00:00+07:00",
  "end_at": "2030-01-02T11:00:00+07:00",
  "slot_minutes": 30
}
```

Giờ ca phải chia hết thành các lượt, không có giây lẻ, không trùng ca đang hoạt động và nằm trong cùng một ngày UTC do cấu trúc `doctor_schedules`. Chọn ca ban ngày Việt Nam; ca qua đêm cần chia thành các ca riêng. Ca đã hủy với cùng khoảng giờ có thể được mở lại khi tạo lại.

Gọi `GET /api/v1/doctors/{doctor_id}/slots?work_date=2030-01-02`, chọn mục `available=true`. `work_date` và các bộ lọc `date_from/date_to` là ngày Việt Nam; timestamp trả về có `Z` (UTC). Dùng thời gian của slot và `schedule_id` để đặt:

```json
{
  "doctor_id": "<doctor_id>",
  "schedule_id": "<schedule_id>",
  "appointment_at": "2030-01-02T08:00:00+07:00",
  "reason": "Khám định kỳ"
}
```

Bệnh nhân có thể bỏ `patient_id`; server lấy từ tài khoản. Lễ tân phải thêm `patient_id` của hồ sơ cần đặt. API không nhận `duration_minutes` tùy ý: thời lượng được lấy từ ca làm.

Đổi lịch bằng `PUT /api/v1/appointments/{appointment_id}` với cùng các trường đặt lịch và thêm `version` vừa đọc, bỏ `patient_id`. Để chọn lại cả slot hiện tại khi sửa, gọi endpoint slots với `exclude_appointment_id` của lịch mình có quyền sửa. Server vẫn kiểm tra lại slot tại thời điểm lưu.

Hủy bằng `POST /api/v1/appointments/{appointment_id}/cancel`:

```json
{"version":"<16 ký tự hex>","cancellation_reason":"Bận công việc"}
```

Hủy ca bằng `POST /api/v1/doctor-schedules/{schedule_id}/cancel` với `{"version":"..."}`. Nếu ca còn lịch booked/confirmed/checked_in/in_progress, phải xử lý các lịch trước.

## Quy tắc và kiểm thử

- Chỉ lịch booked/confirmed, chưa đến giờ và chưa có lượt khám được đổi/hủy.
- So sánh cả khoảng thời gian của bác sĩ và bệnh nhân; hai lượt liền nhau được phép. Lịch cancelled/no_show không chiếm slot.
- SQL Server cấp khóa độc quyền theo transaction cho các lần ghi ca/lịch. Với một phòng khám, cách này ưu tiên sự đơn giản và đúng đắn; khi tải lớn có thể chia khóa theo bác sĩ/bệnh nhân với thứ tự khóa thống nhất.
- Audit được ghi cùng transaction với thay đổi; lỗi slot/phiên bản sẽ rollback toàn bộ.
- `409`: trùng giờ, phiên bản cũ, trạng thái không cho sửa/hủy hoặc ca không khả dụng. `404`: hồ sơ không tồn tại/ngoài quyền. `422`: dữ liệu hoặc thời gian sai. `503`: không lấy được khóa trong thời gian chờ.
- Bộ test kiểm tra RBAC, múi giờ, slot, ca trùng, đổi/hủy, rollback, audit và đặt đồng thời cùng bác sĩ/cùng bệnh nhân.

Luồng mã: `API/routes/appointments.py` → `BLL/appointment_service.py` → `DAL/appointment_repository.py` → `Database/procedures/appointments.sql`. Dùng các bảng `doctors`, `doctor_schedules`, `appointments`, `patients`, `users`, `audit_logs` hiện có.

Nhắc lịch email/in-app thực hiện ở bước 2.4. Check-in và cập nhật trạng thái tiếp nhận ở bước 2.5.
