# Health Profile trong backend

Tài liệu này giải thích mục đích của từng file thuộc tính năng **Health
Profile** ở backend, cách các lớp phụ thuộc vào nhau và luồng xử lý của các API
liên quan.

## Phạm vi tính năng

Health Profile quản lý hai nhóm dữ liệu của người dùng:

- Thông tin sức khỏe cơ bản: ngày sinh, giới tính, cân nặng, chiều cao, mức độ
  vận động, mục tiêu chính và cân nặng mục tiêu.
- Sở thích hoặc hạn chế: dị ứng, chế độ ăn hạn chế, món/vị yêu thích và món/vị
  không thích.

Tính năng cũng theo dõi trạng thái onboarding:

- `NOT_STARTED`: chưa tạo hồ sơ và chưa bỏ qua onboarding.
- `SKIPPED`: chưa tạo hồ sơ nhưng đã bỏ qua onboarding.
- `COMPLETED`: đã có hồ sơ sức khỏe.

## Cấu trúc và hướng phụ thuộc

```text
HTTP request
    |
    v
delivery/routes.py -----> delivery/dto.py
    |
    v
service/profiles.py ----> domain/entities.py, domain/errors.py
    |
    v
repository/profiles.py   (contract/Protocol)
    ^
    |
infrastructure/sqlalchemy_profiles.py ----> PostgreSQL

wiring.py nối repository implementation vào service bằng FastAPI Depends
```

Ý nghĩa của cách chia này:

- `domain` chứa ngôn ngữ nghiệp vụ và không biết HTTP hay SQLAlchemy.
- `service` thực thi use case và các quy tắc nghiệp vụ.
- `repository` định nghĩa cổng truy cập dữ liệu mà service cần.
- `infrastructure` hiện thực cổng đó bằng SQLAlchemy/PostgreSQL.
- `delivery` chuyển đổi giữa HTTP/JSON và các kiểu dữ liệu trong domain.
- `wiring.py` lắp các thành phần lại bằng dependency injection.

## Mục đích từng file trong `health_profile`

### `health_profile/__init__.py`

Đánh dấu `health_profile` là một Python package và mô tả ngắn package này là
feature hồ sơ sức khỏe người dùng. File không chứa logic nghiệp vụ hay export
công khai nào.

### `health_profile/wiring.py`

Là **composition root** của riêng feature Health Profile:

- `get_health_profile_repository()` nhận `AsyncSession` từ
  `core.database.get_db_session` và tạo
  `SqlAlchemyHealthProfileRepository`.
- `get_health_profile_service()` nhận repository qua `Depends` rồi tạo
  `HealthProfileService`.

Nhờ file này, route chỉ phụ thuộc vào service; FastAPI chịu trách nhiệm tạo
session, repository và service cho mỗi request. Đây cũng là điểm được test
override để thay service thật bằng fake service.

### `health_profile/domain/__init__.py`

Đánh dấu thư mục `domain` là package và ghi rõ đây là nơi chứa các kiểu dữ liệu
nghiệp vụ của Health Profile. File hiện không re-export class nào.

### `health_profile/domain/entities.py`

Định nghĩa toàn bộ từ vựng và dữ liệu cốt lõi của feature, độc lập với FastAPI,
Pydantic và SQLAlchemy.

Các enum:

- `HealthProfileGender`: các giá trị giới tính được hỗ trợ.
- `HealthProfileActivityLevel`: các mức độ vận động.
- `HealthProfilePrimaryGoal`: mục tiêu duy trì, giảm/tăng cân hoặc tăng cơ.
- `HealthPreferenceType`: phân loại dị ứng, hạn chế ăn uống, sở thích và không
  thích.
- `HealthProfileOnboardingState`: ba trạng thái `NOT_STARTED`, `SKIPPED` và
  `COMPLETED`.

Các dataclass bất biến (`frozen=True`):

- `HealthPreference`: một preference đã được lưu, có ID và thời điểm tạo.
- `HealthPreferenceDraft`: preference đã chuẩn hóa nhưng chưa lưu DB.
- `HealthProfileDraft`: dữ liệu hồ sơ đã qua kiểm tra/chuẩn hóa, được service
  gửi xuống repository để lưu.
- `HealthProfile`: hồ sơ hoàn chỉnh trả về từ repository, gồm cả preferences và
  timestamps.
- `HealthProfileState`: gói trạng thái onboarding cùng hồ sơ tùy chọn. Khi chưa
  hoàn tất, `profile` có thể là `None`.

Việc tách `Draft` khỏi entity đã lưu giúp phân biệt dữ liệu đầu vào chưa có ID,
timestamp với dữ liệu đã tồn tại trong hệ thống.

### `health_profile/domain/errors.py`

Khai báo hệ phân cấp lỗi của feature:

- `HealthProfileError`: lớp lỗi gốc để có thể bắt toàn bộ lỗi Health Profile
  khi cần.
- `InvalidHealthProfileError`: dữ liệu vi phạm quy tắc nghiệp vụ, được lớp HTTP
  đổi thành response `422 Unprocessable Entity`.
- `HealthProfileOwnerNotFoundError`: không tìm thấy local user sở hữu hồ sơ,
  được đổi thành response `404 Not Found`.

Các lỗi riêng của domain giúp service và repository không phải phụ thuộc vào
`HTTPException` của FastAPI.

### `health_profile/repository/__init__.py`

Đánh dấu thư mục `repository` là package chứa các hợp đồng truy cập dữ liệu.
File hiện không re-export thành phần nào.

### `health_profile/repository/profiles.py`

Định nghĩa `HealthProfileRepository` dưới dạng `Protocol`. Đây là interface mà
service sử dụng, gồm ba thao tác bất đồng bộ:

- `get_state(user_id)`: lấy trạng thái onboarding và hồ sơ hiện tại.
- `save(user_id, draft)`: tạo mới hoặc cập nhật hồ sơ.
- `mark_onboarding_skipped(user_id, skipped_at)`: ghi nhận người dùng bỏ qua
  onboarding.

Service chỉ cần một object tuân theo contract này, nên unit test có thể dùng
fake repository mà không cần PostgreSQL. Các lệnh `raise NotImplementedError`
chỉ là thân mặc định của Protocol; implementation thật nằm ở lớp
infrastructure.

### `health_profile/service/__init__.py`

Đánh dấu thư mục `service` là package chứa các use case của Health Profile.
File hiện không re-export thành phần nào.

### `health_profile/service/profiles.py`

Chứa lớp `HealthProfileService` và các quy tắc nghiệp vụ dùng trước khi truy
cập dữ liệu.

Các use case của service:

- `get_state()`: chuyển yêu cầu lấy trạng thái sang repository.
- `save()`: kiểm tra các giá trị, chuẩn hóa preferences, tạo
  `HealthProfileDraft`, rồi yêu cầu repository lưu.
- `skip_onboarding()`: tạo timestamp UTC ở thời điểm xử lý và yêu cầu repository
  ghi nhận trạng thái bỏ qua.

Các hàm hỗ trợ:

- `validate_profile_values()`: ngày sinh phải ở quá khứ; cân nặng, chiều cao và
  cân nặng mục tiêu (nếu có) phải hợp lệ và lớn hơn 0.
- `validate_positive_decimal()`: loại cả số không hữu hạn như `NaN`/`Infinity`
  và số không dương.
- `normalize_preferences()`: gộp khoảng trắng, không chấp nhận chuỗi rỗng hoặc
  dài quá 100 ký tự, tạo giá trị `casefold()` để so sánh, rồi loại trùng theo
  cặp `(preference_type, normalized_value)` mà vẫn giữ thứ tự xuất hiện đầu
  tiên.

Đây là lớp nên chứa các quy tắc dùng chung cho mọi delivery adapter, không chỉ
HTTP.

### `health_profile/infrastructure/__init__.py`

Đánh dấu thư mục `infrastructure` là package chứa adapter kỹ thuật của feature.
File hiện không re-export thành phần nào.

### `health_profile/infrastructure/sqlalchemy_profiles.py`

Là implementation PostgreSQL/SQLAlchemy cho
`HealthProfileRepository`. File có ba trách nhiệm chính.

**1. Khai báo ORM model**

- `HealthProfileModel` ánh xạ bảng `health_profiles`. `user_id` vừa là khóa
  chính vừa là khóa ngoại đến `users`, nên mỗi user có tối đa một health
  profile. Các check constraint bảo vệ cân nặng/chiều cao ở tầng DB.
- `HealthProfilePreferenceModel` ánh xạ bảng
  `health_profile_preferences`. Mỗi preference có UUID riêng; unique constraint
  trên `(user_id, preference_type, normalized_value)` ngăn dữ liệu trùng sau
  chuẩn hóa.
- Hai khóa ngoại dùng `ON DELETE CASCADE`, vì vậy dữ liệu health profile được
  xóa theo khi local user bị xóa.

**2. Chuyển ORM model sang domain**

- `to_domain()` ghép một profile row với danh sách preference rows để tạo
  `HealthProfile` thuần domain.

**3. Thực thi repository**

- `get_state()` xác minh user tồn tại. Nếu chưa có profile, trạng thái được suy
  ra từ `users.profile_onboarding_dismissed_at`; nếu có profile, trạng thái luôn
  là `COMPLETED`.
- `save()` thực hiện upsert profile, đặt lại trạng thái skip, xóa toàn bộ
  preferences cũ rồi chèn danh sách mới, commit, refresh và trả domain entity.
  Vì vậy request PUT biểu diễn toàn bộ danh sách preferences mong muốn, không
  phải bản vá từng preference.
- `mark_onboarding_skipped()` chỉ ghi timestamp khi chưa có profile. Nếu đã có
  profile, trạng thái vẫn là `COMPLETED` và dữ liệu không bị xóa.
- `_load_preferences()` tải preferences theo thứ tự `created_at`, sau đó
  `preference_id`, để kết quả ổn định.

### `health_profile/delivery/__init__.py`

Đánh dấu thư mục `delivery` là package chứa HTTP adapter của Health Profile.
File hiện không re-export thành phần nào.

### `health_profile/delivery/dto.py`

Định nghĩa schema Pydantic của request/response và các hàm ánh xạ domain sang
JSON response.

Request DTO:

- `HealthPreferenceRequest`: nhận loại và nội dung preference; kiểm tra độ dài,
  gộp khoảng trắng và chặn giá trị chỉ có whitespace.
- `UpsertHealthProfileRequest`: schema toàn bộ payload PUT; giới hạn số chữ số,
  phần thập phân, giá trị dương, ngày sinh trong quá khứ và tối đa 100
  preferences.

Response DTO:

- `AccountSummaryResponse`: thông tin tài khoản tối thiểu đi kèm hồ sơ.
- `HealthPreferenceResponse`: chỉ công khai loại và giá trị hiển thị; không lộ
  `preference_id` hay `normalized_value`.
- `HealthProfileResponse`: hồ sơ sức khỏe trả cho client.
- `HealthProfileEnvelopeResponse`: response cấp cao nhất gồm trạng thái
  onboarding, account và health profile tùy chọn.

Hàm ánh xạ:

- `envelope_response()` kết hợp `HealthProfileState` với `CurrentUser`.
- `profile_response()` chuyển entity thành response và đổi `Decimal` sang
  `float` để khớp API hiện tại.
- `preference_response()` lọc entity preference về các trường public.

DTO có validation sớm để FastAPI trả `422` trước khi gọi service; service vẫn
kiểm tra lại các bất biến quan trọng để không phụ thuộc riêng vào HTTP input.

### `health_profile/delivery/routes.py`

Khai báo router FastAPI với prefix `/health-profile`. Khi được gắn vào router
gốc `/api`, feature cung cấp ba endpoint:

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| `GET` | `/api/health-profile` | Lấy account, trạng thái onboarding và hồ sơ hiện tại |
| `PUT` | `/api/health-profile` | Tạo mới hoặc thay thế/cập nhật toàn bộ hồ sơ |
| `POST` | `/api/health-profile/onboarding/skip` | Bỏ qua onboarding nếu chưa có hồ sơ |

Cả ba endpoint yêu cầu `CurrentUser`, tức người gọi phải đăng nhập. Hai endpoint
thay đổi dữ liệu (`PUT`, `POST`) được middleware chung xác minh CSRF trước khi
route được gọi.
Route chuyển lỗi nghiệp vụ sang HTTP status phù hợp:

- `InvalidHealthProfileError` thành `422`.
- `HealthProfileOwnerNotFoundError` thành `404`.

`PUT` gọi `save()` rồi `get_state()` để trả envelope mới nhất. `POST .../skip`
trả `204 No Content` khi thành công.

## Các file backend liên quan trực tiếp

Các file dưới đây nằm ngoài package `health_profile` nhưng là một phần của việc
tích hợp và kiểm thử feature.

### `alembic/versions/202607300004_create_health_profiles.py`

Migration tạo bốn PostgreSQL enum, thêm cột
`users.profile_onboarding_dismissed_at`, tạo hai bảng `health_profiles` và
`health_profile_preferences`, cùng các khóa ngoại, constraint và index. Hàm
`downgrade()` gỡ các thành phần theo thứ tự ngược lại.

ORM model mô tả trạng thái code hiện tại, còn migration là lịch sử thay đổi
schema thực sự được Alembic chạy lên database; cần duy trì cả hai đồng bộ.

### `api/routers.py`

Import `health_profile.delivery.routes.router` và gắn nó vào router `/api`.
Nếu bỏ dòng `include_router(health_profile_router)`, các endpoint Health Profile
sẽ không được đăng ký dù package vẫn tồn tại.

### `tests/test_health_profile_service.py`

Unit test lớp service bằng `FakeHealthProfileRepository`. File kiểm tra việc
chuẩn hóa/loại trùng preferences, từ chối ngày sinh hoặc số đo không hợp lệ và
ghi nhận trạng thái skip. Các test này không cần HTTP hay database thật.

### `tests/test_health_profile_routes.py`

Test HTTP contract bằng FastAPI `TestClient` và dependency override. File kiểm
tra response khi chưa có profile, yêu cầu đăng nhập, yêu cầu CSRF cho thao tác
ghi, tạo profile thành công, validation ngày sinh và endpoint skip onboarding.

### Các dependency dùng chung

- `core/database.py`: cung cấp `Base`, `AsyncSession` và dependency session cho
  ORM/repository.
- `core/csrf.py`: ký token và bảo vệ tập trung các request thay đổi dữ liệu.
- `identity/wiring.py`: cung cấp `CurrentUser` đã xác thực cho route.
- `identity/infrastructure/sqlalchemy_users.py`: chứa `UserModel`, bao gồm cột
  lưu thời điểm bỏ qua profile onboarding.

## Luồng xử lý chính

### Lấy hồ sơ

1. `GET /api/health-profile` xác thực user qua `get_current_user`.
2. Route lấy `HealthProfileService` qua `wiring.py`.
3. Service gọi `repository.get_state()`.
4. SQLAlchemy repository đọc user, profile và preferences rồi trả domain state.
5. `dto.py` ghép state với account và serialize thành JSON.

### Tạo hoặc cập nhật hồ sơ

1. FastAPI/Pydantic parse và kiểm tra payload PUT.
2. Route xác thực user và CSRF token.
3. Service kiểm tra bất biến, chuẩn hóa và loại trùng preferences.
4. Repository upsert profile, thay toàn bộ preferences và commit transaction.
5. Route đọc state mới rồi trả envelope có `onboarding_state=COMPLETED`.

### Bỏ qua onboarding

1. Route xác thực user và CSRF token.
2. Service tạo thời điểm UTC hiện tại.
3. Nếu chưa có profile, repository lưu timestamp skip trên bảng `users`.
4. Nếu đã có profile, repository giữ nguyên trạng thái `COMPLETED`.

## File không cần chỉnh sửa thủ công

Các thư mục `__pycache__/` và file `*.pyc` dưới `health_profile` là bytecode do
Python tự sinh khi chạy ứng dụng hoặc test. Chúng không chứa source of truth,
không thuộc thiết kế của feature và không nên được chỉnh sửa hay viết tài liệu
nghiệp vụ riêng cho từng file.
