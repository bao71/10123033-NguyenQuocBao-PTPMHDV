# Stored procedure trong project phòng khám

Backend dùng `pyodbc` để gọi các stored procedure của SQL Server. Mã ứng dụng
trong `DAL/` và `CLI/` không chứa câu `SELECT`, `INSERT`, `UPDATE`, `DELETE`
trực tiếp. `DAL/procedures.py` chỉ tạo lời gọi `EXEC dbo.clinic_*` với tham số
được truyền qua placeholder `?` của `pyodbc`.

Định nghĩa procedure nằm trong `Database/procedures/`:

- `auth.sql`: đăng nhập, token, đặt lại mật khẩu và audit log.
- `users_roles.sql`: quản lý nhân viên, phân quyền, tạo Admin đầu tiên và health check.
- `patients.sql`: danh sách, xem chi tiết, tạo, sửa và xóa mềm bệnh nhân.
- `histories.sql`: tiền sử bệnh/dị ứng, lọc danh sách, khóa bản ghi khi sửa, tạo, cập nhật và xóa mềm.
- `reception.sql`: danh sách/thống kê tiếp nhận theo ngày, xác nhận lịch, check-in và vắng hẹn; thay đổi trạng thái và audit được commit chung transaction.
- `encounters.sql`: bệnh án, chẩn đoán, chỉ định/kết quả cận lâm sàng, hoàn tất khám và snapshot phiên bản; SQL kiểm tra phạm vi Bác sĩ/Bệnh nhân.
- `appointments.sql`: danh sách bác sĩ, ca làm, giờ trống, đặt/đổi/hủy lịch. Các lần ghi cùng dùng khóa transaction `clinic-appointments-write` để chống chồng giờ khi nhiều request chạy đồng thời.

Migration `006_procedure_access.sql` cấp quyền `EXECUTE` cho role SQL
`clinic_app_role`. Sau khi chạy các migration, `scripts/migrate.sh` áp dụng lại
các file procedure bằng `CREATE OR ALTER`, nên thay đổi procedure được triển
khai vào database hiện có khi chạy `db-init` hoặc `setup.ps1`. Không sửa các
migration đã áp dụng; thêm migration mới cho thay đổi schema.

Ví dụ luồng gọi: `API/routes/admin.py` -> `BLL/admin_service.py` ->
`DAL/user_repository.py` -> `DAL/procedures.py` ->
`dbo.clinic_user_list` -> các bảng `users`, `roles`.

Các integration test dùng SQL trực tiếp để tạo/xóa dữ liệu kiểm thử. Đây là
fixture của test, không phải đường truy cập database của ứng dụng.
