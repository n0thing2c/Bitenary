from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from identity.domain.entities import CurrentUser, UserStatus
from identity.wiring import get_current_user
from virtual_fridge.domain.entities import (
    CategoryCount,
    ExpiryNotificationSettings,
    FoodState,
    FridgeItem,
    FridgeItemPage,
    FridgeSummary,
    IngredientSummary,
    Notification,
    NotificationPage,
    NotificationStatus,
    NotificationType,
)
from virtual_fridge.domain.errors import FridgeItemNotFoundError
from virtual_fridge.wiring import (
    get_expiry_notification_service,
    get_virtual_fridge_service,
)


def make_item(user_id: UUID) -> FridgeItem:
    now = datetime.now(UTC)
    return FridgeItem(
        fridge_item_id=uuid4(),
        user_id=user_id,
        ingredient=IngredientSummary(
            ingredient_id=uuid4(),
            name="Spinach",
            variant="raw",
            category="Vegetables",
        ),
        quantity=Decimal("250"),
        unit="g",
        food_state=FoodState.RAW,
        expiry_date=date.today() + timedelta(days=2),
        created_at=now,
        updated_at=now,
    )


class FakeVirtualFridgeService:
    def __init__(self, user_id: UUID) -> None:
        self.item = make_item(user_id)
        self.deleted = False

    async def create_item(self, **values: object) -> FridgeItem:
        self.item = FridgeItem(
            fridge_item_id=uuid4(),
            user_id=values["user_id"],  # type: ignore[arg-type]
            ingredient=IngredientSummary(
                ingredient_id=values["ingredient_id"],  # type: ignore[arg-type]
                name="Spinach",
                variant="raw",
                category="Vegetables",
            ),
            quantity=values["quantity"],  # type: ignore[arg-type]
            unit=values["unit"],  # type: ignore[arg-type]
            food_state=values["food_state"],  # type: ignore[arg-type]
            expiry_date=values["expiry_date"],  # type: ignore[arg-type]
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return self.item

    async def get_item(self, **values: object) -> FridgeItem:
        if values["fridge_item_id"] != self.item.fridge_item_id:
            raise FridgeItemNotFoundError
        return self.item

    async def update_item(self, **values: object) -> FridgeItem:
        changes = values["changes"]
        self.item = FridgeItem(
            **{
                **self.item.__dict__,
                **changes,  # type: ignore[arg-type]
                "updated_at": datetime.now(UTC),
            }
        )
        return self.item

    async def delete_item(self, **values: object) -> None:
        if values["fridge_item_id"] != self.item.fridge_item_id:
            raise FridgeItemNotFoundError
        self.deleted = True

    async def list_items(self, **values: object) -> FridgeItemPage:
        return FridgeItemPage(
            items=(self.item,),
            page=int(values["page"]),
            size=int(values["size"]),
            total=1,
        )

    async def get_summary(self, **_values: object) -> FridgeSummary:
        return FridgeSummary(
            total_items=1,
            fresh=0,
            expiring_soon=1,
            expiring_today=0,
            expired=0,
            categories=(CategoryCount(category="Vegetables", count=1),),
        )


class FakeExpiryNotificationService:
    def __init__(self, user_id: UUID, fridge_item_id: UUID) -> None:
        self.settings = ExpiryNotificationSettings(
            user_id=user_id,
            enabled=True,
            warning_days=3,
            timezone="Asia/Ho_Chi_Minh",
            delivery_hour=9,
        )
        now = datetime.now(UTC)
        self.notification = Notification(
            notification_id=uuid4(),
            user_id=user_id,
            fridge_item_id=fridge_item_id,
            notification_type=NotificationType.EXPIRING_SOON,
            status=NotificationStatus.SENT,
            title="Food item expiring soon",
            message="Spinach expires in 2 day(s).",
            trigger_date=date.today(),
            scheduled_for=now,
            sent_at=now,
            read_at=None,
            created_at=now,
        )

    async def get_settings(self, _user_id: UUID) -> ExpiryNotificationSettings:
        return self.settings

    async def save_settings(self, **values: object) -> ExpiryNotificationSettings:
        self.settings = ExpiryNotificationSettings(
            user_id=values["user_id"],  # type: ignore[arg-type]
            enabled=bool(values["enabled"]),
            warning_days=int(values["warning_days"]),
            timezone=str(values["timezone"]),
            delivery_hour=int(values["delivery_hour"]),
            updated_at=datetime.now(UTC),
        )
        return self.settings

    async def list_notifications(self, **values: object) -> NotificationPage:
        return NotificationPage(
            items=(self.notification,),
            page=int(values["page"]),
            size=int(values["size"]),
            total=1,
        )

    async def mark_read(self, **_values: object) -> Notification:
        self.notification = Notification(
            **{
                **self.notification.__dict__,
                "status": NotificationStatus.READ,
                "read_at": datetime.now(UTC),
            }
        )
        return self.notification

    async def mark_all_read(self, **_values: object) -> int:
        return 1


@pytest.fixture()
def fridge_client() -> tuple[
    TestClient,
    FakeVirtualFridgeService,
    FakeExpiryNotificationService,
    CurrentUser,
]:
    current_user = CurrentUser(
        user_id=uuid4(),
        authentik_sub="authentik-fridge-user",
        username="Fridge User",
        email="fridge@example.com",
        status=UserStatus.ACTIVE,
    )
    fridge_service = FakeVirtualFridgeService(current_user.user_id)
    notification_service = FakeExpiryNotificationService(
        current_user.user_id,
        fridge_service.item.fridge_item_id,
    )
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_virtual_fridge_service] = lambda: fridge_service
    app.dependency_overrides[get_expiry_notification_service] = (
        lambda: notification_service
    )
    with TestClient(app) as client:
        yield client, fridge_service, notification_service, current_user
    app.dependency_overrides.clear()


def csrf(client: TestClient) -> dict[str, str]:
    client.cookies.set("bitenary_csrf", "csrf-token")
    return {"X-CSRF-Token": "csrf-token"}


def create_payload(ingredient_id: UUID) -> dict[str, object]:
    return {
        "ingredient_id": str(ingredient_id),
        "quantity": 500,
        "unit": "g",
        "food_state": "RAW",
        "expiry_date": (date.today() + timedelta(days=2)).isoformat(),
    }


def test_create_requires_csrf(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, service, _notification_service, _user = fridge_client
    response = client.post(
        "/api/virtual-fridge/items",
        json=create_payload(service.item.ingredient.ingredient_id),
    )
    assert response.status_code == 403


def test_create_and_list_fridge_items(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, service, _notification_service, _user = fridge_client
    response = client.post(
        "/api/virtual-fridge/items",
        headers=csrf(client),
        json=create_payload(service.item.ingredient.ingredient_id),
    )
    assert response.status_code == 201
    assert response.json()["ingredient"]["name"] == "Spinach"
    assert response.json()["expiry_status"] == "EXPIRING_SOON"

    listed = client.get("/api/virtual-fridge/items?sort=name_asc")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["total_pages"] == 1


def test_patch_rejects_empty_and_null_required_field(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, service, _notification_service, _user = fridge_client
    headers = csrf(client)
    url = f"/api/virtual-fridge/items/{service.item.fridge_item_id}"
    assert client.patch(url, headers=headers, json={}).status_code == 422
    assert client.patch(url, headers=headers, json={"unit": None}).status_code == 422


def test_delete_item(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, service, _notification_service, _user = fridge_client
    response = client.delete(
        f"/api/virtual-fridge/items/{service.item.fridge_item_id}",
        headers=csrf(client),
    )
    assert response.status_code == 204
    assert service.deleted is True


def test_summary_and_notification_settings(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, _service, _notification_service, _user = fridge_client
    summary = client.get("/api/virtual-fridge/summary")
    assert summary.status_code == 200
    assert summary.json()["expiring_soon"] == 1

    settings = client.put(
        "/api/virtual-fridge/notification-settings",
        headers=csrf(client),
        json={
            "enabled": False,
            "warning_days": 5,
            "timezone": "UTC",
            "delivery_hour": 8,
        },
    )
    assert settings.status_code == 200
    assert settings.json()["enabled"] is False
    assert settings.json()["warning_days"] == 5


def test_notification_list_and_mark_read(
    fridge_client: tuple[TestClient, FakeVirtualFridgeService, FakeExpiryNotificationService, CurrentUser],
) -> None:
    client, _service, notification_service, _user = fridge_client
    listed = client.get("/api/notifications?unread_only=true")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    marked = client.patch(
        f"/api/notifications/{notification_service.notification.notification_id}/read",
        headers=csrf(client),
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "READ"
