# Quản lý phòng khám — SQL Server bằng Docker

Thư mục `clinic/` chứa phần triển khai mới cho đề tài phòng khám, theo hướng **FastAPI + pyodbc + SQL Server**. Các thư mục C# tại gốc repository là mã tham khảo của dự án cũ. Thiết kế nghiệp vụ dựa trên [SRS và ERD](docs/README.md) đã lưu cùng mã nguồn.

Hiện tại dự án đã có SQL Server, migration, FastAPI, kết nối `pyodbc`, JWT, refresh token và RBAC. Phần đăng ký công khai chỉ tạo tài khoản Bệnh nhân; tài khoản nhân viên do Admin quản lý ở các bước nghiệp vụ tiếp theo.

## 1. Chuẩn bị máy

- Windows trên CPU **x86_64/AMD64**, bật ảo hóa, cài **Docker Desktop với WSL 2** và chạy chế độ **Linux containers**. Image SQL Server Linux không hỗ trợ máy ARM theo [yêu cầu nền tảng của Microsoft](https://learn.microsoft.com/sql/linux/install-upgrade/setup).
- Mở Docker Desktop và chờ Docker Engine sẵn sàng. Lần chạy đầu cần Internet để tải image SQL Server 2022 Developer.
- VS Code với extension **SQL Server (mssql)** của **Microsoft**, ID `ms-mssql.mssql`. Repository đã thêm extension này vào danh sách gợi ý; mở Extensions và tìm `@recommended` để cài.
- PowerShell có sẵn trên Windows. Không cần cài SQL Server hoặc SSMS trực tiếp lên máy.

Compose giới hạn bộ nhớ SQL Server ở **2.048 MB** và tổng bộ nhớ container ở **3 GB**. Docker/WSL2 cần được cấp đủ bộ nhớ cho container, đồng thời chừa bộ nhớ cho hệ điều hành và các công cụ đang chạy.

Tài liệu cài đặt chính thức: [Docker Desktop trên Windows](https://docs.docker.com/desktop/setup/install/windows-install/), [extension MSSQL](https://learn.microsoft.com/en-us/sql/tools/visual-studio-code-extensions/mssql/mssql-extension-visual-studio-code).

## 2. Khởi tạo database

Mở terminal PowerShell tại **gốc repository** (`BTL_PTPMHDV`) và chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\setup.ps1
```

Script chuẩn bị `clinic/.env` nếu chưa có, sinh mật khẩu quản trị ngẫu nhiên, khởi động SQL Server, đợi health check thành công rồi chạy migration và bộ kiểm tra `db-check`. Mật khẩu không được in ra terminal. Nếu đã có `.env`, script sử dụng lại cấu hình đó.

Database được tạo với tên **`ClinicManagement`**. Cấu hình mặc định:

| Cấu hình | Giá trị |
| --- | --- |
| SQL Server | 2022 Developer, dùng cho phát triển/kiểm thử |
| Máy chủ từ Windows/VS Code | `localhost,14331` |
| Cổng được mở trên máy | `127.0.0.1:14331` |
| Máy chủ từ container cùng Compose | `sqlserver,1433` |
| Database | `ClinicManagement` |
| Tài khoản quản trị | `sa` |
| Mật khẩu | Giá trị `MSSQL_SA_PASSWORD` trong `clinic/.env` |
| Compose project | `clinic-management` |
| Volume dữ liệu | `sqlserver_data` trong Compose project |

`clinic/.env.example` mô tả cấu hình dùng chung. `clinic/.env` chứa mật khẩu riêng của máy và được loại khỏi Git. Để xem mật khẩu khi đăng nhập từ VS Code, mở `.env` tại máy bạn; không đưa giá trị này vào mã nguồn hoặc file cấu hình kết nối được commit.

Nếu muốn đổi cổng, sửa `MSSQL_PORT` trong `.env`, rồi chạy lại `setup.ps1`. Cổng bên trong container vẫn là `1433`; cập nhật cổng tương ứng trong kết nối VS Code.

## 3. Kết nối bằng extension trong VS Code

1. Mở biểu tượng SQL Server/MSSQL trên thanh bên, chọn tạo kết nối mới.
2. Chọn nhập thông số kết nối và điền các giá trị sau:

| Trường | Giá trị |
| --- | --- |
| Server name | `localhost,14331` |
| Authentication type | SQL Login |
| User name | `sa` |
| Password | Giá trị `MSSQL_SA_PASSWORD` trong `clinic/.env` |
| Database name | `ClinicManagement` |
| Encrypt | `True` / `Mandatory` |
| Trust server certificate | `True` |
| Connection/profile name | `Clinic Local Docker` |

3. Kết nối và mở `ClinicManagement` → Tables để xem các bảng.
4. Tạo một truy vấn mới, kiểm tra database đang chọn là `ClinicManagement`, rồi chạy:

```sql
SELECT DB_NAME() AS current_database;
SELECT name FROM sys.tables ORDER BY name;
SELECT * FROM dbo.roles;
```

`Trust server certificate = True` dùng cho chứng chỉ tự ký trong môi trường phát triển cục bộ này. Khi triển khai thực tế cần chứng chỉ hợp lệ và kiểm tra chứng chỉ của máy chủ.

`sa` chỉ dùng để dựng database và kiểm tra. FastAPI đăng nhập bằng SQL login `clinic_app` được tạo tự động; principal này không có quyền sửa hoặc xóa `audit_logs`, `record_versions`, `inventory_transactions` và `schema_migrations`.

## 4. Kiểm tra cấu trúc và dữ liệu khởi tạo

Chạy từ gốc repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\check.ps1
```

Script chạy bộ kiểm tra SQL và thống kê schema. Chỉ coi việc khởi tạo là thành công khi SQL Server healthy, migration kết thúc thành công và bộ kiểm tra không báo lỗi. Có thể đọc trực tiếp nội dung kiểm tra tại [`database/checks/verify.sql`](database/checks/verify.sql).

Đây là dữ liệu khởi tạo danh mục: 5 vai trò, các quyền và một số danh mục mẫu. Bộ dữ liệu mô phỏng **ít nhất 2.000 bản ghi** theo yêu cầu BTL sẽ được bổ sung ở bước seed nghiệp vụ; chưa có tài khoản bệnh nhân/bác sĩ để đăng nhập ứng dụng ở giai đoạn này.

## 5. Chạy FastAPI và xác thực

Khởi động toàn bộ database và API từ gốc repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\start.ps1
```

Sau khi hoàn tất:

| Thành phần | Địa chỉ |
| --- | --- |
| API | `http://127.0.0.1:8000` |
| Swagger | `http://127.0.0.1:8000/docs` |
| OpenAPI JSON | `http://127.0.0.1:8000/openapi.json` |
| Health check | `http://127.0.0.1:8000/health/ready` |

Các endpoint xác thực hiện có:

| Phương thức | Endpoint | Chức năng |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Đăng ký tài khoản và hồ sơ Bệnh nhân |
| `POST` | `/api/v1/auth/login` | Đăng nhập OAuth2 form, nhận access JWT và refresh token |
| `POST` | `/api/v1/auth/refresh` | Xoay vòng refresh token và cấp access token mới |
| `POST` | `/api/v1/auth/logout` | Thu hồi một hoặc toàn bộ phiên đăng nhập |
| `GET` | `/api/v1/auth/me` | Xem tài khoản, vai trò và quyền hiện tại |
| `GET` | `/api/v1/admin/users` | Danh sách tài khoản; yêu cầu quyền `users.read` |

Access token được ký bằng khóa riêng trong `.env` và hết hạn sau 30 phút. Refresh token chỉ lưu dạng SHA-256 trong database. Mật khẩu dùng Argon2; đăng nhập sai 5 lần khóa tài khoản 15 phút. Quyền được đọc trực tiếp từ `role_permissions` ở mỗi yêu cầu nên thay đổi RBAC có hiệu lực ngay.

Tạo tài khoản Admin đầu tiên bằng lệnh tương tác sau; mật khẩu được nhập ẩn và không xuất hiện trên command line:

```powershell
Set-Location .\clinic
docker compose run --rm api python -m app.cli.create_admin --username admin --email admin@example.com
```

Chạy lint, unit test và integration test với SQL Server thật:

```powershell
powershell -ExecutionPolicy Bypass -File .\clinic\scripts\test.ps1
```

## 6. Các lệnh Docker thường dùng

Các lệnh trong mục này chạy từ thư mục **`clinic/`**, sau khi đã có `.env`:

```powershell
Set-Location .\clinic
```

| Công việc | Lệnh |
| --- | --- |
| Khởi động SQL Server và đợi healthy | `docker compose up -d --wait sqlserver` |
| Khởi động API | `docker compose up -d --build api` |
| Chạy các migration còn thiếu | `docker compose run --rm db-init` |
| Chạy kiểm tra database | `docker compose --profile tools run --rm db-check` |
| Xem trạng thái | `docker compose ps` |
| Xem log SQL Server gần đây | `docker compose logs --tail 100 sqlserver` |
| Dừng tạm thời | `docker compose stop sqlserver` |
| Gỡ container/network, giữ volume dữ liệu | `docker compose down` |

Dữ liệu nằm trong named volume nên được giữ khi dừng hoặc tạo lại container. Volume không thay thế bản sao lưu; chỉ xóa volume khi chủ động muốn xóa toàn bộ dữ liệu. [Cách lưu dữ liệu SQL Server container](https://learn.microsoft.com/en-us/sql/linux/containers/configure?view=sql-server-ver16).

## 7. Cách quản lý migration

Script `scripts/migrate.sh` dùng `sqlcmd` trong container để tạo database nếu thiếu và chạy migration theo thứ tự tên file. Mỗi migration có lịch sử áp dụng và checksum, được chạy một lần; lần khởi động sau sẽ bỏ qua những migration đã áp dụng hợp lệ. Nếu nội dung migration đã chạy bị thay đổi, runner báo lỗi để tránh lệch cấu trúc giữa các máy.

Khi cần sửa cấu trúc, tạo file mới như `database/migrations/004_add_example.sql`; giữ nguyên migration đã được áp dụng. Mỗi file được runner bọc trong transaction để có thể rollback khi lỗi. Không viết `GO`, lệnh điều khiển `sqlcmd` hay tự `COMMIT`/`ROLLBACK` trong các file migration này.

Lưu file SQL bằng **UTF-8**; chuỗi Unicode T-SQL sử dụng tiền tố `N`, ví dụ `N'Lễ tân'`. Dữ liệu thời gian lưu theo **UTC**; ứng dụng sẽ chuyển sang `Asia/Ho_Chi_Minh` khi hiển thị.

## 8. Cấu trúc thư mục

```text
.vscode/
  extensions.json                  # Gợi ý extension MSSQL
clinic/
  README.md                        # Hướng dẫn này
  compose.yaml                     # SQL Server, migration, kiểm tra và FastAPI
  .env.example                     # Mẫu biến môi trường, không có mật khẩu thật
  .env                             # Cấu hình riêng, sinh cục bộ và không commit
  database/
    migrations/
      001_initial_schema.sql       # Schema theo ERD
      002_reference_data.sql       # Vai trò, quyền và danh mục ban đầu
      003_runtime_security.sql     # Quyền SQL cho principal ứng dụng
    checks/
      verify.sql                   # Kiểm tra database
  scripts/
    setup.ps1                      # Tạo cấu hình, khởi động, migrate và kiểm tra
    start.ps1                      # Dựng và khởi động toàn bộ database + API
    check.ps1                      # Chạy bộ kiểm tra database
    test.ps1                       # Lint và test backend với database thật
    migrate.sh                     # Runner migration trong container
  backend/
    app/                           # FastAPI, raw SQL repository, JWT và RBAC
    tests/                         # Unit test và integration test
    Dockerfile                    # Python + Microsoft ODBC Driver 18
    pyproject.toml / uv.lock       # Dependencies Python đã khóa phiên bản
```

## 9. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
| --- | --- |
| Không nhận lệnh `docker` | Cài Docker Desktop, sau đó mở lại terminal để cập nhật PATH. |
| Cannot connect to Docker daemon / lỗi named pipe | Mở Docker Desktop, chờ engine hoạt động và kiểm tra đang dùng Linux containers. |
| Cổng `14331` đã được sử dụng | Đổi `MSSQL_PORT` trong `.env`, chạy lại setup và sửa cổng kết nối VS Code. |
| SQL Server unhealthy | Xem `docker compose logs --tail 100 sqlserver`; kiểm tra mật khẩu, tài nguyên Docker và cấu hình WSL2. |
| Login failed for user `sa` sau khi sửa `.env` | Mật khẩu trong volume đã khởi tạo không tự đổi theo `.env`. Khôi phục cấu hình mật khẩu đúng; muốn đổi mật khẩu phải đăng nhập bằng mật khẩu hiện tại và đổi trong SQL Server, rồi cập nhật `.env`. |
| VS Code báo chứng chỉ không được tin cậy | Giữ Encrypt bật và bật Trust server certificate cho kết nối phát triển cục bộ. |
| Migration báo checksum không khớp | Khôi phục đúng nội dung file đã áp dụng; đưa thay đổi vào migration mới. Không sửa lịch sử migration để bỏ qua lỗi. |
| Không thấy bảng trong VS Code | Kiểm tra chọn đúng `ClinicManagement`, đã chạy `db-init` thành công, rồi refresh Object Explorer. |
| API không ready | Chạy `docker compose logs --tail 100 api` và kiểm tra SQL Server đang healthy. |

## 10. Ghi chú cấu trúc dữ liệu

Migration tạo **30 bảng theo SRS/ERD**; runner tạo thêm bảng kỹ thuật `schema_migrations` để lưu lịch sử và checksum. Các điểm cần giữ thống nhất khi viết FastAPI:

| Thành phần | Quy ước |
| --- | --- |
| ID | Các ID thực thể dùng `UNIQUEIDENTIFIER` (UUID), mặc định `NEWSEQUENTIALID()`; bảng liên kết có thể dùng khóa ghép. |
| Thời gian | `DATETIME2(3)` và cặp ngày/giờ lịch làm việc lưu theo UTC. Các trường chỉ có ngày như ngày sinh, khởi phát hoặc hạn sử dụng là ngày lịch, không chuyển múi giờ. |
| Cập nhật đồng thời | `row_version` do SQL Server tự đổi, dùng trong điều kiện `UPDATE ... WHERE` để phát hiện dữ liệu đã bị người khác sửa. Đây không phải lịch sử nội dung; `record_versions` mới lưu các bản chụp JSON của bản ghi. |
| Tiền hóa đơn | `invoice_items.amount` tự tính từ số lượng × đơn giá, làm tròn đến đồng; `invoices.total_amount` tự tính từ `subtotal - discount`. API phải cộng các dòng vào `subtotal` và đồng bộ `paid_amount` với thanh toán trong transaction. |
| Thông báo | `notifications.recipient` lưu địa chỉ email/số điện thoại để nhắc lịch cho bệnh nhân chưa có tài khoản; `user_id` được để trống với email/SMS. Thông báo trong ứng dụng yêu cầu `user_id`. |

Schema có khóa ngoại, `CHECK`, unique index và các trường soft-delete. Các ràng buộc này chưa tự thực hiện kiểm tra mọi khoảng lịch trùng nhau, xuất thuốc/trừ tồn kho, thu tiền hoặc ghi `audit_logs`/`record_versions`. Các service FastAPI sau này phải xử lý những nghiệp vụ đó trong transaction, áp dụng quyền truy cập và cập nhật `updated_at`; không có trigger tự tạo lịch sử trong bước này.

## 11. Bước tiếp theo

Nền tảng FastAPI, JWT và RBAC đã hoàn thành. Bước tiếp theo của Master Plan là CRUD hồ sơ bệnh nhân rồi luồng lịch hẹn, gồm tìm kiếm, lọc, sắp xếp, phân trang, kiểm tra quyền sở hữu và audit. Redis, hàng đợi, gửi email và bộ seed ít nhất 2.000 bản ghi được bổ sung ở các giai đoạn sau.
