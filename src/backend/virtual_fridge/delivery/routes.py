from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.config import Settings, get_settings
from identity.domain.entities import CurrentUser
from identity.wiring import get_current_user
from virtual_fridge.delivery.dto import (
    CreateFridgeItemRequest,
    ExpiryNotificationSettingsRequest,
    ExpiryNotificationSettingsResponse,
    FridgeItemListResponse,
    FridgeItemResponse,
    FridgeSummaryResponse,
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UpdateFridgeItemRequest,
    item_list_response,
    item_response,
    notification_list_response,
    notification_response,
    settings_response,
    summary_response,
)
from virtual_fridge.domain.entities import (
    ExpiryStatus,
    FoodState,
    FridgeItemSort,
    NotificationType,
)
from virtual_fridge.domain.errors import (
    FridgeItemNotFoundError,
    IngredientNotFoundError,
    InvalidFridgeItemError,
    InvalidNotificationSettingsError,
    NotificationNotFoundError,
)
from virtual_fridge.service.expiry_notifications import ExpiryNotificationService
from virtual_fridge.service.fridge import VirtualFridgeService
from virtual_fridge.wiring import (
    get_expiry_notification_service,
    get_virtual_fridge_service,
)


router = APIRouter(prefix="/virtual-fridge", tags=["virtual-fridge"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/items", response_model=FridgeItemListResponse)
async def list_fridge_items(
    q: str | None = Query(default=None, max_length=512),
    category: str | None = Query(default=None, max_length=128),
    expiry_status: ExpiryStatus | None = Query(default=None),
    food_state: FoodState | None = Query(default=None),
    sort: FridgeItemSort = Query(default=FridgeItemSort.EXPIRY_ASC),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
    settings: Settings = Depends(get_settings),
) -> FridgeItemListResponse:
    today = date.today()
    result = await service.list_items(
        user_id=current_user.user_id,
        q=q,
        category=category,
        expiry_status=expiry_status,
        food_state=food_state,
        sort=sort,
        page=page,
        size=size,
        today=today,
    )
    return item_list_response(
        result,
        today=today,
        warning_days=settings.fridge_expiry_warning_days,
    )


@router.post(
    "/items",
    response_model=FridgeItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fridge_item(
    payload: CreateFridgeItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
    settings: Settings = Depends(get_settings),
) -> FridgeItemResponse:
    try:
        item = await service.create_item(
            user_id=current_user.user_id,
            ingredient_id=payload.ingredient_id,
            quantity=payload.quantity,
            unit=payload.unit,
            food_state=payload.food_state,
            expiry_date=payload.expiry_date,
        )
    except IngredientNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ingredient was not found") from exc
    except InvalidFridgeItemError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return item_response(
        item,
        today=date.today(),
        warning_days=settings.fridge_expiry_warning_days,
    )


@router.get("/summary", response_model=FridgeSummaryResponse)
async def get_fridge_summary(
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
) -> FridgeSummaryResponse:
    summary = await service.get_summary(user_id=current_user.user_id)
    return summary_response(summary)


@router.get(
    "/notification-settings",
    response_model=ExpiryNotificationSettingsResponse,
)
async def get_notification_settings(
    current_user: CurrentUser = Depends(get_current_user),
    service: ExpiryNotificationService = Depends(get_expiry_notification_service),
) -> ExpiryNotificationSettingsResponse:
    return settings_response(await service.get_settings(current_user.user_id))


@router.put(
    "/notification-settings",
    response_model=ExpiryNotificationSettingsResponse,
)
async def update_notification_settings(
    payload: ExpiryNotificationSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ExpiryNotificationService = Depends(get_expiry_notification_service),
) -> ExpiryNotificationSettingsResponse:
    try:
        saved = await service.save_settings(
            user_id=current_user.user_id,
            enabled=payload.enabled,
            warning_days=payload.warning_days,
            timezone=payload.timezone,
            delivery_hour=payload.delivery_hour,
        )
    except InvalidNotificationSettingsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return settings_response(saved)


@router.get("/items/{fridge_item_id}", response_model=FridgeItemResponse)
async def get_fridge_item(
    fridge_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
    settings: Settings = Depends(get_settings),
) -> FridgeItemResponse:
    try:
        item = await service.get_item(
            user_id=current_user.user_id,
            fridge_item_id=fridge_item_id,
        )
    except FridgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fridge item was not found") from exc
    return item_response(
        item,
        today=date.today(),
        warning_days=settings.fridge_expiry_warning_days,
    )


@router.patch("/items/{fridge_item_id}", response_model=FridgeItemResponse)
async def update_fridge_item(
    fridge_item_id: UUID,
    payload: UpdateFridgeItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
    settings: Settings = Depends(get_settings),
) -> FridgeItemResponse:
    try:
        item = await service.update_item(
            user_id=current_user.user_id,
            fridge_item_id=fridge_item_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except FridgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fridge item was not found") from exc
    except IngredientNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Ingredient was not found") from exc
    except InvalidFridgeItemError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return item_response(
        item,
        today=date.today(),
        warning_days=settings.fridge_expiry_warning_days,
    )


@router.delete(
    "/items/{fridge_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_fridge_item(
    fridge_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: VirtualFridgeService = Depends(get_virtual_fridge_service),
) -> None:
    try:
        await service.delete_item(
            user_id=current_user.user_id,
            fridge_item_id=fridge_item_id,
        )
    except FridgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fridge item was not found") from exc


@notifications_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(default=False),
    notification_type: NotificationType | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: ExpiryNotificationService = Depends(get_expiry_notification_service),
) -> NotificationListResponse:
    result = await service.list_notifications(
        user_id=current_user.user_id,
        unread_only=unread_only,
        notification_type=notification_type,
        page=page,
        size=size,
    )
    return notification_list_response(result)


@notifications_router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
    service: ExpiryNotificationService = Depends(get_expiry_notification_service),
) -> MarkAllReadResponse:
    updated = await service.mark_all_read(user_id=current_user.user_id)
    return MarkAllReadResponse(updated=updated)


@notifications_router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ExpiryNotificationService = Depends(get_expiry_notification_service),
) -> NotificationResponse:
    try:
        notification = await service.mark_read(
            user_id=current_user.user_id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notification was not found") from exc
    return notification_response(notification)
