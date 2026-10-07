# Khám bệnh, chẩn đoán và cận lâm sàng (Master Plan 3.1)

## Thử trên web

Mở `http://127.0.0.1:8000/app/`.

1. Lễ tân đặt lịch cho bệnh nhân và check-in trong đúng ngày hẹn.
2. Bác sĩ được giao đăng nhập, chọn **Khám bệnh**, chọn **Bắt đầu khám** ở danh sách chờ.
3. Xem tiền sử/dị ứng đang hoạt động. Ghi lý do khám, nội dung khám và chỉ số sinh tồn.
4. Thêm chẩn đoán, chọn một chẩn đoán **Chính**, ghi kết luận và hướng xử trí.
5. Bấm **Lưu bệnh án**, rồi thêm chỉ định xét nghiệm/chẩn đoán hình ảnh nếu cần.
6. Nhập nội dung kết quả hoặc giá trị số, đơn vị, khoảng tham chiếu. Có thể sửa/xóa kết quả
   khi lượt khám còn đang diễn ra. Chỉ định chưa có kết quả có thể sửa, hủy hoặc xóa mềm.
7. Bấm **Lưu và hoàn tất khám**. Cần kết luận, một chẩn đoán chính và không còn chỉ định chờ.
8. Bệnh nhân đăng nhập, chọn **Bệnh án của tôi**, mở lượt khám đã hoàn tất để xem chẩn đoán,
   lời dặn và kết quả. Có thể mở bệnh án từ lịch hẹn đã khám.

Lễ tân thấy trạng thái lịch đổi thành **Đang khám** rồi **Đã khám** sau khi làm mới danh sách.
Lễ tân, Admin và Dược sĩ không có quyền xem nội dung bệnh án theo quyền mặc định.
Bác sĩ khác không được đọc/sửa bệnh án của bác sĩ được giao. Bệnh nhân không thấy bản nháp.

Lưu thay đổi bệnh án trước khi thao tác chỉ định/kết quả. **Lưu và hoàn tất khám** lưu bản nháp
trước rồi yêu cầu hoàn tất: nếu còn thiếu dữ liệu, bản nháp vẫn được giữ và web báo lý do.
Bệnh án đã hoàn tất khóa cả nội dung khám, chẩn đoán, chỉ định và kết quả. Chức năng đính chính
sau hoàn tất chưa thuộc bước này; không sửa/xóa trực tiếp để mở khóa.

Kê đơn và nhà thuốc thuộc 3.2. Bước này nhập kết quả thủ công bởi Bác sĩ, chưa tích hợp máy
xét nghiệm hoặc tải tệp đính kèm. Chỉ số sinh tồn là dữ liệu bác sĩ nhập, không tự đưa ra chẩn đoán.

## API

Tất cả request cần `Authorization: Bearer <access_token>`.

| Method | `/api/v1` + URL | Mục đích |
| --- | --- | --- |
| GET | `/encounters` | Tìm/lọc/sắp xếp/phân trang bệnh án trong phạm vi được đọc |
| POST | `/encounters` | Bắt đầu khám từ lịch đã check-in |
| GET | `/encounters/{id}` | Chi tiết bệnh án, chẩn đoán, chỉ định và kết quả |
| PUT | `/encounters/{id}` | Lưu nội dung khám, chỉ số và danh sách chẩn đoán |
| POST | `/encounters/{id}/complete` | Hoàn tất, đồng bộ trạng thái lịch hẹn |
| GET | `/encounters/{id}/versions` | Lịch sử bệnh án của Bác sĩ được giao |
| POST | `/encounters/{id}/clinical-orders` | Thêm chỉ định |
| PUT | `/encounters/{id}/clinical-orders/{order_id}` | Sửa chỉ định chưa có kết quả |
| POST | `/encounters/{id}/clinical-orders/{order_id}/cancel` | Hủy chỉ định chưa có kết quả |
| DELETE | `/encounters/{id}/clinical-orders/{order_id}` | Xóa mềm chỉ định chưa có kết quả |
| POST | `/encounters/{id}/clinical-orders/{order_id}/results` | Thêm kết quả |
| PUT | `/encounters/{id}/clinical-orders/{order_id}/results/{result_id}` | Sửa kết quả |
| DELETE | `/encounters/{id}/clinical-orders/{order_id}/results/{result_id}` | Xóa mềm kết quả |

GET danh sách hỗ trợ `page`, `page_size` (tối đa 100), `search` (tên/mã bệnh nhân hoặc kết luận),
`patient_id`, `appointment_id`, `status`, `date_from`, `date_to` (ngày Việt Nam),
`sort_by=started_at|updated_at|status`, `sort_order=asc|desc`.

Bắt đầu khám cần `encounters.create_assigned`; lưu cần `encounters.update_assigned`;
hoàn tất cần `encounters.complete_assigned`; chỉ định/kết quả cần quyền
`clinical_orders.write_assigned` / `clinical_results.write_assigned`.
Mọi thao tác ghi cũng yêu cầu `encounters.read_assigned` và SQL kiểm tra Bác sĩ được giao.
Đọc của Bệnh nhân dùng `encounters.read_self`; dữ liệu kết quả dùng thêm `clinical_results.read_self`.
Lịch sử phiên bản dùng `record_versions.read_assigned`.

Body bắt đầu khám:

```json
{
  "appointment_id": "UUID lịch hẹn",
  "appointment_version": "row_version mới nhất của lịch hẹn",
  "chief_complaint": "Khám định kỳ"
}
```

Body lưu bệnh án:

```json
{
  "version": "row_version mới nhất của bệnh án",
  "chief_complaint": "Khám định kỳ",
  "clinical_notes": "Nội dung khám do bác sĩ nhập",
  "diagnosis_summary": "Kết luận do bác sĩ nhập",
  "treatment_plan": "Hướng xử trí và lời dặn",
  "vital_signs": {"temperature_c": 36.8, "pulse_bpm": 75},
  "diagnoses": [{"name": "Chẩn đoán do bác sĩ nhập", "is_primary": true}]
}
```

PUT thay thế các trường nội dung và toàn bộ danh sách chẩn đoán. Trường bỏ trống trở về
null/mảng rỗng; lấy bản hiện tại trước khi sửa. Mã chẩn đoán là tùy chọn, không tự đối chiếu ICD.
Chỉ số được kiểm tra kiểu/range và huyết áp tâm thu phải lớn hơn tâm trương nếu nhập đủ hai giá trị.

Mọi ghi sau bắt đầu cần `version` của **bệnh án**. Sửa/hủy/xóa chỉ định và thêm kết quả
cần thêm `order_version`; sửa/xóa kết quả cần thêm `result_version`.
Version là chuỗi 16 ký tự hex lấy từ GET, không phải số `version_no`.
Response ghi trả toàn bộ bệnh án với version mới; lấy các version từ response đó cho request kế tiếp.

DELETE nhận JSON body chứa version. Xóa kết quả cuối cùng đưa chỉ định về `ordered`;
nếu còn kết quả khác thì vẫn `completed`. Lịch sử trước khi xóa vẫn còn trong snapshot.
Không sửa/hủy chỉ định có kết quả, không nhập kết quả vào chỉ định đã hủy.

Import `docs/postman/Encounters.postman_collection.json`. Collection có biến token/ID/version
và scripts lưu version từ response. Chọn `order_id`/`result_id` phù hợp trước khi sửa/xóa.
Các request hủy/xóa là nhánh thử riêng, không chạy tuần tự sau khi hoàn tất bệnh án.
Swagger: `http://127.0.0.1:8000/docs`.

## Database và transaction

Migration mới `007_encounter_vitals.sql` thêm `encounters.vital_signs_json` với CHECK JSON hợp lệ.
Không thêm bảng. `encounters`, `diagnoses`, `clinical_orders`, `clinical_results`,
`record_versions`, `audit_logs` và `appointments` đã có sẵn.

`API/routes/encounters.py` → `BLL/encounter_service.py` → `DAL/encounter_repository.py`
→ `DAL/procedures.py` → `Database/procedures/encounters.sql`.
Ứng dụng tiếp tục chỉ gọi stored procedure bằng pyodbc, không dùng ORM/SQL inline.

Bắt đầu khám, lưu, chỉ định/kết quả, snapshot và audit commit trong cùng transaction.
Khóa `clinic-appointments-write` dùng chung với đặt lịch/tiếp nhận, `row_version` chống ghi đè,
unique index trên appointment ngăn hai bệnh án cho cùng lịch.
Mỗi lần ghi tăng `version_no`; snapshot chứa nội dung và các chẩn đoán/chỉ định/kết quả đang hiện hành.
Thay danh sách chẩn đoán/xóa chỉ định/xóa kết quả đều dùng soft-delete; nội dung cũ còn trong phiên bản trước.

Chạy từ gốc project:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\start.ps1
```

`db-init` áp dụng migration mới một lần và CREATE OR ALTER các procedure. Không sửa migration đã chạy.

## File và kiểm thử

Tạo mới `Model/encounters.py`, `API/routes/encounters.py`, `BLL/encounter_service.py`,
`DAL/encounter_repository.py`, `Database/migrations/007_encounter_vitals.sql`,
`Database/procedures/encounters.sql`, `Tests/test_encounters.py`,
`Tests/test_encounters_integration.py`, tài liệu này và collection Postman.

Cập nhật `API/router.py`, `Frontend/index.html`, `Frontend/assets/app.js`,
`Frontend/assets/app.css`, `README.md` và `docs/stored-procedures.md`.

Unit test kiểm tra quyền từng hành động, input chỉ số/chẩn đoán/kết quả và rollback khi lỗi.
Integration test chạy trên SQL Server để kiểm tra toàn bộ luồng, bản nháp/Bệnh nhân,
quyền sở hữu, version, soft-delete, snapshot, audit, lọc/phân trang và request đồng thời.
