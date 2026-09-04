import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPostJson,
  apiPut,
} from "../../../shared/api/httpClient";
import type { CsrfResponse } from "../../auth/model/types";
import type {
  CategoriesResponse,
  ExpiryNotification,
  FridgeItem,
  FridgeItemInput,
  FridgeItemList,
  FridgeSummary,
  IngredientList,
  InventoryQuery,
  NotificationList,
  NotificationSettings,
} from "../model/types";

async function csrfToken(): Promise<string> {
  const response = await apiGet<CsrfResponse>("/api/auth/csrf");
  return response.csrf_token;
}

export function getFridgeItems(query: InventoryQuery): Promise<FridgeItemList> {
  const params = new URLSearchParams({ sort: query.sort, page: "1", size: "100" });
  if (query.q.trim()) params.set("q", query.q.trim());
  if (query.category) params.set("category", query.category);
  if (query.expiry_status) params.set("expiry_status", query.expiry_status);
  if (query.food_state) params.set("food_state", query.food_state);
  return apiGet<FridgeItemList>(`/api/virtual-fridge/items?${params}`);
}

export function getFridgeSummary(): Promise<FridgeSummary> {
  return apiGet<FridgeSummary>("/api/virtual-fridge/summary");
}

export function getIngredientCategories(): Promise<CategoriesResponse> {
  return apiGet<CategoriesResponse>("/api/ingredients/categories");
}

export function searchIngredients(query: string): Promise<IngredientList> {
  const params = new URLSearchParams({
    q: query.trim(),
    only_default: "false",
    page: "1",
    size: "8",
  });
  return apiGet<IngredientList>(`/api/ingredients?${params}`);
}

export async function createFridgeItem(input: FridgeItemInput): Promise<FridgeItem> {
  return apiPostJson<FridgeItem>(
    "/api/virtual-fridge/items",
    input,
    await csrfToken(),
  );
}

export async function updateFridgeItem(
  itemId: string,
  input: FridgeItemInput,
): Promise<FridgeItem> {
  return apiPatch<FridgeItem>(
    `/api/virtual-fridge/items/${itemId}`,
    input,
    await csrfToken(),
  );
}

export async function deleteFridgeItem(itemId: string): Promise<void> {
  return apiDelete(
    `/api/virtual-fridge/items/${itemId}`,
    await csrfToken(),
  );
}

export function getNotificationSettings(): Promise<NotificationSettings> {
  return apiGet<NotificationSettings>(
    "/api/virtual-fridge/notification-settings",
  );
}

export async function saveNotificationSettings(
  settings: Omit<NotificationSettings, "updated_at">,
): Promise<NotificationSettings> {
  return apiPut<NotificationSettings>(
    "/api/virtual-fridge/notification-settings",
    settings,
    await csrfToken(),
  );
}

export function getNotifications(): Promise<NotificationList> {
  return apiGet<NotificationList>(
    "/api/notifications?unread_only=true&page=1&size=20",
  );
}

export async function markNotificationRead(
  notificationId: string,
): Promise<ExpiryNotification> {
  return apiPatch<ExpiryNotification>(
    `/api/notifications/${notificationId}/read`,
    undefined,
    await csrfToken(),
  );
}

export async function markAllNotificationsRead(): Promise<{ updated: number }> {
  return apiPatch<{ updated: number }>(
    "/api/notifications/read-all",
    undefined,
    await csrfToken(),
  );
}
