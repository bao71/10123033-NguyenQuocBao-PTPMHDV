# Use case tổng quát quản lý phòng khám

Sơ đồ tập trung vào nghiệp vụ với 5 tác nhân, 18 use case và 19 quan hệ tham gia. Các nhóm chức năng tổng quát như đặt/đổi/hủy lịch sẽ được tách thành use case riêng khi viết đặc tả chi tiết.

| Vai trò | Phạm vi |
|---|---|
| Bệnh nhân | Đặt/đổi/hủy lịch, nhận nhắc lịch, xem hồ sơ và đơn thuốc của bản thân. |
| Lễ tân | Quản lý thông tin hành chính bệnh nhân, đặt lịch hộ, tiếp nhận, thu phí và xuất hóa đơn. |
| Bác sĩ | Xem lịch khám, xem/cập nhật bệnh án và tiền sử trong phạm vi được giao, ghi nhận cận lâm sàng, chẩn đoán và kê đơn. |
| Dược sĩ | Quản lý danh mục thuốc, nhập thuốc, tra cứu tồn và xuất thuốc theo đơn hợp lệ. |
| Admin | Quản lý tài khoản, phân quyền, tra cứu audit log và xem/xuất báo cáo doanh thu theo bác sĩ. |

## Quy ước và phạm vi

- Tác nhân nằm ngoài khung hệ thống. Hình ellipse biểu diễn use case. Đường liền biểu diễn quan hệ tham gia, không biểu diễn luồng tuần tự hoặc trao quyền truy cập mọi dữ liệu.
- Lễ tân đảm nhiệm thu phí; đây là phân công thiết kế phù hợp danh sách 5 vai trò trong đề, cần ghi thống nhất trong SRS.
- Bác sĩ ghi nhận kết quả cận lâm sàng trong phạm vi bài tập; đề không đưa ra vai trò kỹ thuật viên xét nghiệm riêng.
- Đăng nhập, đặt lại mật khẩu và kiểm tra quyền là chức năng nền tảng chung. Bệnh nhân có thể đăng ký tài khoản; tài khoản nhân viên do Admin quản lý. Các chức năng này chưa tách thành ellipse trong sơ đồ nghiệp vụ tổng quát.
- Bệnh nhân chỉ xem dữ liệu của mình. Lễ tân xử lý thông tin hành chính; bác sĩ truy cập bệnh án theo phân công. Vai trò Admin không mặc nhiên có quyền sửa nội dung bệnh án.
- Nhắc lịch email chạy tự động bằng hàng đợi tác vụ. Bệnh nhân là bên nhận thông báo. SMTP/job là chi tiết tích hợp, không phải một trong 5 vai trò người dùng.
- Đơn thuốc, lô thuốc, tồn kho và trạng thái thanh toán phải được kiểm tra khi cấp thuốc theo quy tắc trong SRS. Xuất thuốc và trừ tồn cần transaction để tránh xuất trùng hoặc tồn âm.
- Chưa dùng quan hệ include/extend trong sơ đồ tổng quát vì cần đặc tả rõ hành vi bắt buộc/tùy chọn trước khi phân rã. Không dùng include để biểu diễn thứ tự đặt lịch–khám–thu phí–xuất thuốc.

## Tệp bàn giao

- `UseCase-PhongKham.png`: ảnh để chèn vào báo cáo.
- `UseCase-PhongKham.svg`: hình vector để phóng to hoặc in.
- `UseCase-PhongKham.puml`: mã nguồn PlantUML, cùng tác nhân/use case/quan hệ; công cụ PlantUML có thể bố trí khác bản SVG.

Nguồn phạm vi: đề bài BTL quản lý phòng khám và phân vai đã trao đổi. Sơ đồ độc lập với lựa chọn backend FastAPI + pyodbc + SQL Server.
