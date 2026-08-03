export type FoodState = "RAW" | "COOKED" | "FROZEN" | "PREPPED";

export type ExpiryStatus =
  | "FRESH"
  | "EXPIRING_SOON"
  | "EXPIRING_TODAY"
  | "EXPIRED";

export type FridgeItemSort =
  | "expiry_asc"
  | "expiry_desc"
  | "name_asc"
  | "updated_desc";

export type Ingredient = {
  ingredient_id: string;
  name: string;
  variant: string;
  category: string;
  is_default?: boolean;
};

export type FridgeItem = {
  fridge_item_id: string;
  ingredient: Ingredient;
  quantity: number;
  unit: string;
  food_state: FoodState | null;
  expiry_date: string;
  expiry_status: ExpiryStatus;
  days_until_expiry: number;
  created_at: string;
  updated_at: string;
};

export type FridgeItemList = {
  items: FridgeItem[];
  page: number;
  size: number;
  total: number;
  total_pages: number;
};

export type FridgeSummary = {
  total_items: number;
  fresh: number;
  expiring_soon: number;
  expiring_today: number;
  expired: number;
  categories: { category: string; count: number }[];
};

export type IngredientList = {
  items: Ingredient[];
  page: number;
  size: number;
  total_in_page: number;
};

export type CategoriesResponse = { categories: string[] };

export type FridgeItemInput = {
  ingredient_id: string;
  quantity: number;
  unit: string;
  food_state: FoodState | null;
  expiry_date: string;
};

export type InventoryQuery = {
  q: string;
  category: string;
  expiry_status: ExpiryStatus | "";
  food_state: FoodState | "";
  sort: FridgeItemSort;
};

export type NotificationSettings = {
  enabled: boolean;
  warning_days: number;
  timezone: string;
  delivery_hour: number;
  updated_at: string | null;
};

export type ExpiryNotification = {
  notification_id: string;
  fridge_item_id: string;
  notification_type: "EXPIRING_SOON" | "EXPIRED";
  status: "PENDING" | "SENT" | "READ" | "FAILED";
  title: string;
  message: string;
  trigger_date: string;
  scheduled_for: string;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
};

export type NotificationList = {
  items: ExpiryNotification[];
  page: number;
  size: number;
  total: number;
  total_pages: number;
};
