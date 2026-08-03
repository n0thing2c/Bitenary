# Backend Virtual Fridge

Tài liệu này hướng dẫn chạy migration, test tự động và kiểm thử thủ công backend Virtual Fridge.

## Chức năng đã triển khai

- CRUD fridge item theo từng user và từng lô thực phẩm.
- Chọn ingredient từ `ingredient_master`; name, variant và category được join khi đọc.
- Search theo ingredient name/variant.
- Filter theo category, expiry status và food state.
- Sort theo expiry, ingredient name hoặc thời gian cập nhật.
- Summary theo expiry status và category.
- In-app expiry notification settings theo warning window, timezone và delivery hour.
- Expiry scan job chạy độc lập, chống trùng bằng database unique constraint.
- Notification list, mark read và mark all read.
- Query nội bộ để recipe/meal-plan lấy item chưa hết hạn.

## API

### Virtual Fridge

| Method | Endpoint | CSRF | Mục đích |
| --- | --- | --- | --- |
| GET | `/api/virtual-fridge/items` | Không | List/search/filter/sort |
| POST | `/api/virtual-fridge/items` | Có | Tạo item |
| GET | `/api/virtual-fridge/items/{id}` | Không | Chi tiết item |
| PATCH | `/api/virtual-fridge/items/{id}` | Có | Cập nhật một phần |
| DELETE | `/api/virtual-fridge/items/{id}` | Có | Xóa item |
| GET | `/api/virtual-fridge/summary` | Không | Tổng hợp inventory |
| GET | `/api/virtual-fridge/notification-settings` | Không | Lấy expiry settings |
| PUT | `/api/virtual-fridge/notification-settings` | Có | Cập nhật expiry settings |

List query hỗ trợ:

```text
q
category
expiry_status=FRESH|EXPIRING_SOON|EXPIRING_TODAY|EXPIRED
food_state=RAW|COOKED|FROZEN|PREPPED
sort=expiry_asc|expiry_desc|name_asc|updated_desc
page
size
```

### Notifications

| Method | Endpoint | CSRF | Mục đích |
| --- | --- | --- | --- |
| GET | `/api/notifications` | Không | List notification |
| PATCH | `/api/notifications/{id}/read` | Có | Đánh dấu đã đọc |
| PATCH | `/api/notifications/read-all` | Có | Đánh dấu tất cả đã đọc |

Tất cả endpoint trong tài liệu này yêu cầu cookie đăng nhập hợp lệ. Mutation yêu cầu thêm CSRF cookie và header `X-CSRF-Token` có cùng giá trị.

## 1. Chuẩn bị môi trường

Từ repository root:

```powershell
cd src/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu `.venv` đã có thì chỉ cần chạy lệnh cài requirements.

Kiểm tra `.env` có ít nhất:

```env
DATABASE_URL=postgresql+asyncpg://bitenary:bitenary@localhost:5433/bitenary
FRIDGE_EXPIRY_WARNING_DAYS=3
FRIDGE_DEFAULT_TIMEZONE=Asia/Ho_Chi_Minh
FRIDGE_DEFAULT_DELIVERY_HOUR=9
```

`tzdata` đã được thêm vào `requirements.txt` để IANA timezone hoạt động trên Windows.

## 2. Chạy PostgreSQL và migration

Từ repository root:

```powershell
docker compose -f infrastructure/bitenary-db/docker-compose.yml up -d
docker compose -f infrastructure/bitenary-db/docker-compose.yml ps
```

Chạy migration:

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c alembic.ini current
```

Revision hiện tại sau khi upgrade phải là:

```text
202608020006 (head)
```

Kiểm tra migration không cần thay đổi database:

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head --sql | Out-Null
```

Chỉ test downgrade trên database phát triển có thể phục hồi:

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade 202608020005
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Downgrade về `202608020005` sẽ xóa notification tables. Không chạy trên production hoặc database có dữ liệu cần giữ.

## 3. Chạy test tự động

### Test riêng Virtual Fridge

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m pytest `
  tests/test_virtual_fridge_service.py `
  tests/test_virtual_fridge_routes.py `
  tests/test_expiry_notifications.py `
  -q
```

Kết quả mong đợi:

```text
18 passed
```

### Regression toàn backend

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

### Compile và OpenAPI

```powershell
.\.venv\Scripts\python.exe -m compileall `
  app api core identity ingredients health_profile virtual_fridge

.\.venv\Scripts\python.exe -c `
  "from app.main import create_app; print(len(create_app().openapi()['paths']))"
```

Lệnh OpenAPI cần `.env` có API key cấu hình hợp lệ vì app khởi tạo MCP server khi import.

## 4. Chạy backend

```powershell
cd src/backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Kiểm tra:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod "http://localhost:8000/api/ingredients?q=spinach"
```

Mở OpenAPI tại `http://localhost:8000/docs` để kiểm tra schema.

## 5. Lấy ingredient ID

Ingredient search là nguồn dữ liệu chuẩn cho create request:

```powershell
$ingredientResult = Invoke-RestMethod `
  "http://localhost:8000/api/ingredients?q=spinach&only_default=false"

$ingredientId = $ingredientResult.items[0].ingredient_id
$ingredientId
```

Category endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/api/ingredients/categories
```

## 6. Chuẩn bị authentication cookie cho manual test

Đăng nhập Bitenary qua frontend/Auth flow trước. Từ Browser DevTools, lấy hai cookie của `localhost`:

- Access cookie dùng bởi backend authentication.
- `bitenary_csrf`.

Tạo PowerShell web session. Thay placeholder bằng giá trị thật; không commit hoặc ghi access token vào file:

```powershell
$apiBase = "http://localhost:8000"
$accessToken = "<access-cookie-value>"
$csrfToken = "<bitenary-csrf-cookie-value>"

$webSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$webSession.Cookies.Add(
  [System.Net.Cookie]::new("bitenary_access", $accessToken, "/", "localhost")
)
$webSession.Cookies.Add(
  [System.Net.Cookie]::new("bitenary_csrf", $csrfToken, "/", "localhost")
)
$csrfHeaders = @{ "X-CSRF-Token" = $csrfToken }
```

Nếu project đổi tên access cookie, kiểm tra constant `ACCESS_COOKIE_NAME` trong `identity/delivery/cookies.py` và dùng đúng tên đó.

## 7. Manual test CRUD

### Tạo item

```powershell
$createBody = @{
  ingredient_id = $ingredientId
  quantity = 500
  unit = "g"
  food_state = "RAW"
  expiry_date = (Get-Date).AddDays(2).ToString("yyyy-MM-dd")
} | ConvertTo-Json

$created = Invoke-RestMethod `
  -Method Post `
  -Uri "$apiBase/api/virtual-fridge/items" `
  -WebSession $webSession `
  -Headers $csrfHeaders `
  -ContentType "application/json" `
  -Body $createBody

$itemId = $created.fridge_item_id
$created
```

Kỳ vọng:

- HTTP `201`.
- Ingredient name/category lấy từ master data.
- `expiry_status` là `EXPIRING_SOON` với cấu hình warning mặc định 3 ngày.
- `days_until_expiry` xấp xỉ 2.

### List, filter và sort

```powershell
Invoke-RestMethod `
  -Uri "$apiBase/api/virtual-fridge/items?expiry_status=EXPIRING_SOON&sort=expiry_asc" `
  -WebSession $webSession

Invoke-RestMethod `
  -Uri "$apiBase/api/virtual-fridge/items?q=spinach&category=Vegetables%20and%20Vegetable%20Products" `
  -WebSession $webSession
```

### Summary

```powershell
Invoke-RestMethod `
  -Uri "$apiBase/api/virtual-fridge/summary" `
  -WebSession $webSession
```

### Update

```powershell
$patchBody = @{
  quantity = 250
  food_state = "PREPPED"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Patch `
  -Uri "$apiBase/api/virtual-fridge/items/$itemId" `
  -WebSession $webSession `
  -Headers $csrfHeaders `
  -ContentType "application/json" `
  -Body $patchBody
```

### Delete

```powershell
Invoke-WebRequest `
  -Method Delete `
  -Uri "$apiBase/api/virtual-fridge/items/$itemId" `
  -WebSession $webSession `
  -Headers $csrfHeaders
```

Kỳ vọng HTTP `204`.

## 8. Manual test validation và security

Không gửi cookie:

```powershell
Invoke-WebRequest "$apiBase/api/virtual-fridge/items" -SkipHttpErrorCheck
```

Kỳ vọng `401`.

Gửi mutation không có CSRF header:

```powershell
Invoke-WebRequest `
  -Method Post `
  -Uri "$apiBase/api/virtual-fridge/items" `
  -WebSession $webSession `
  -ContentType "application/json" `
  -Body $createBody `
  -SkipHttpErrorCheck
```

Kỳ vọng `403`.

Quantity bằng 0:

```powershell
$invalidBody = @{
  ingredient_id = $ingredientId
  quantity = 0
  unit = "g"
  expiry_date = (Get-Date).ToString("yyyy-MM-dd")
} | ConvertTo-Json
```

Gửi `$invalidBody` như create request và kỳ vọng `422`.

Owner isolation được cover bởi automated service/route test. Khi test tích hợp với hai tài khoản, dùng item ID của tài khoản A trong session B và kỳ vọng `404`.

## 9. Test notification settings và expiry job

### Cập nhật settings

```powershell
$settingsBody = @{
  enabled = $true
  warning_days = 3
  timezone = "Asia/Ho_Chi_Minh"
  delivery_hour = 9
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Put `
  -Uri "$apiBase/api/virtual-fridge/notification-settings" `
  -WebSession $webSession `
  -Headers $csrfHeaders `
  -ContentType "application/json" `
  -Body $settingsBody
```

### Chạy expiry scanner

Từ `src/backend`:

```powershell
.\.venv\Scripts\python.exe -m virtual_fridge.jobs.scan_expiry
```

Deterministic test với thời gian cụ thể:

```powershell
.\.venv\Scripts\python.exe -m virtual_fridge.jobs.scan_expiry `
  --now "2026-08-02T09:00:00+07:00"
```

Output ví dụ:

```json
{"created": 1, "scanned": 1, "skipped": 0}
```

Chạy lại đúng lệnh trên. Do unique constraint `(fridge_item_id, notification_type, trigger_date)`, lần sau phải có `created: 0` cho cùng trigger.

### List và mark read

```powershell
$notifications = Invoke-RestMethod `
  -Uri "$apiBase/api/notifications?unread_only=true" `
  -WebSession $webSession

$notificationId = $notifications.items[0].notification_id

Invoke-RestMethod `
  -Method Patch `
  -Uri "$apiBase/api/notifications/$notificationId/read" `
  -WebSession $webSession `
  -Headers $csrfHeaders

Invoke-RestMethod `
  -Method Patch `
  -Uri "$apiBase/api/notifications/read-all" `
  -WebSession $webSession `
  -Headers $csrfHeaders
```

## 10. Điều kiện đạt

- Migration đạt head `202608020006`.
- 18 Virtual Fridge tests pass.
- Full backend regression pass.
- CRUD response chỉ chứa item của current user.
- Search/category/expiry filters trả đúng kết quả.
- Quantity <= 0 bị từ chối.
- Mutation không có CSRF bị từ chối.
- Expiry scanner chạy lặp không tạo notification trùng.
- Item đã hết hạn không xuất hiện trong internal available-ingredients query.
