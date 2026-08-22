import { useEffect, useMemo, useState } from "react";

import { searchIngredients } from "../../features/virtual-fridge/api/virtualFridgeApi";
import type {
  ExpiryNotification,
  ExpiryStatus,
  FoodState,
  FridgeItem,
  FridgeItemInput,
  FridgeItemSort,
  FridgeSummary,
  Ingredient,
  InventoryQuery,
  NotificationSettings,
} from "../../features/virtual-fridge/model/types";
import { useVirtualFridge } from "../../features/virtual-fridge/model/useVirtualFridge";

import "./VirtualFridgePage.css";

const STATUS_LABELS: Record<ExpiryStatus, string> = {
  FRESH: "Fresh",
  EXPIRING_SOON: "Expiring soon",
  EXPIRING_TODAY: "Expires today",
  EXPIRED: "Expired",
};

const FOOD_STATE_LABELS: Record<FoodState, string> = {
  RAW: "Raw",
  COOKED: "Cooked",
  FROZEN: "Frozen",
  PREPPED: "Prepped",
};

const DEFAULT_QUERY: InventoryQuery = {
  q: "",
  category: "",
  expiry_status: "",
  food_state: "",
  sort: "expiry_asc",
};

export function VirtualFridgePage() {
  const [query, setQuery] = useState<InventoryQuery>(DEFAULT_QUERY);
  const [searchText, setSearchText] = useState("");
  const [drawerItem, setDrawerItem] = useState<FridgeItem | "new" | null>(null);
  const [deleteItem, setDeleteItem] = useState<FridgeItem | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const fridge = useVirtualFridge(query);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setQuery((current) => ({ ...current, q: searchText }));
    }, 280);
    return () => window.clearTimeout(timeout);
  }, [searchText]);

  useEffect(() => {
    if (!drawerItem && !deleteItem) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || fridge.isSaving) return;
      if (deleteItem) setDeleteItem(null);
      else setDrawerItem(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [deleteItem, drawerItem, fridge.isSaving]);

  const activeFilterCount = [
    query.category,
    query.expiry_status,
    query.food_state,
  ].filter(Boolean).length;
  const unreadCount = fridge.notifications.filter(
    (notification) => notification.status !== "READ",
  ).length;

  async function submitItem(input: FridgeItemInput) {
    await fridge.saveItem(
      input,
      drawerItem && drawerItem !== "new" ? drawerItem.fridge_item_id : undefined,
    );
    setDrawerItem(null);
  }

  async function confirmDelete() {
    if (!deleteItem) return;
    await fridge.removeItem(deleteItem);
    setDeleteItem(null);
  }

  return (
    <main className="fridge-page">
      <header className="fridge-page__header">
        <div>
          <h1>Virtual Fridge</h1>
        </div>
        <div className="fridge-header-actions">
          <span className="fridge-header-actions__count">
            {fridge.summary?.total_items ?? fridge.list.total} stored item
            {(fridge.summary?.total_items ?? fridge.list.total) === 1 ? "" : "s"}
          </span>

          <button
            className="fridge-primary-button"
            type="button"
            onClick={() => setDrawerItem("new")}
          >
            <Icon name="plus" /> Add item
          </button>
        </div>
      </header>

      <div className="fridge-workspace">
        <section className="fridge-inventory" aria-labelledby="inventory-title">
          <div className="fridge-inventory__intro">
            <div>
              <p>Inventory status</p>
              <h2 id="inventory-title">What is in your fridge</h2>
              <span>Track quantities and catch expiry risks before food is wasted.</span>
            </div>
            <button
              className="fridge-secondary-button"
              type="button"
              onClick={() => setShowFilters((current) => !current)}
              aria-expanded={showFilters}
            >
              <Icon name="filter" /> Filters
              {activeFilterCount ? <b>{activeFilterCount}</b> : null}
            </button>
          </div>

          <div className="fridge-toolbar">
            <label className="fridge-search">
              <Icon name="search" />
              <span className="sr-only">Search inventory</span>
              <input
                value={searchText}
                placeholder="Search food or variant..."
                onChange={(event) => setSearchText(event.target.value)}
              />
              {searchText ? (
                <button
                  type="button"
                  aria-label="Clear search"
                  onClick={() => setSearchText("")}
                >
                  ×
                </button>
              ) : null}
            </label>
            <label className="fridge-sort">
              <span>Sort</span>
              <select
                value={query.sort}
                onChange={(event) =>
                  setQuery((current) => ({
                    ...current,
                    sort: event.target.value as FridgeItemSort,
                  }))
                }
              >
                <option value="expiry_asc">Expiry: nearest</option>
                <option value="expiry_desc">Expiry: latest</option>
                <option value="name_asc">Name: A-Z</option>
                <option value="updated_desc">Recently updated</option>
              </select>
            </label>
          </div>

          <CategoryChips
            categories={fridge.categories}
            active={query.category}
            onSelect={(category) =>
              setQuery((current) => ({ ...current, category }))
            }
          />

          {showFilters ? (
            <div className="fridge-filter-panel">
              <label>
                Category
                <select
                  value={query.category}
                  onChange={(event) =>
                    setQuery((current) => ({
                      ...current,
                      category: event.target.value,
                    }))
                  }
                >
                  <option value="">Any category</option>
                  {fridge.categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Expiry status
                <select
                  value={query.expiry_status}
                  onChange={(event) =>
                    setQuery((current) => ({
                      ...current,
                      expiry_status: event.target.value as ExpiryStatus | "",
                    }))
                  }
                >
                  <option value="">Any status</option>
                  <option value="FRESH">Fresh</option>
                  <option value="EXPIRING_SOON">Expiring soon</option>
                  <option value="EXPIRING_TODAY">Expires today</option>
                  <option value="EXPIRED">Expired</option>
                </select>
              </label>
              <label>
                Physical state
                <select
                  value={query.food_state}
                  onChange={(event) =>
                    setQuery((current) => ({
                      ...current,
                      food_state: event.target.value as FoodState | "",
                    }))
                  }
                >
                  <option value="">Any state</option>
                  <option value="RAW">Raw</option>
                  <option value="COOKED">Cooked</option>
                  <option value="FROZEN">Frozen</option>
                  <option value="PREPPED">Prepped</option>
                </select>
              </label>
              <button
                type="button"
                disabled={activeFilterCount === 0}
                onClick={() =>
                  setQuery((current) => ({
                    ...current,
                    category: "",
                    expiry_status: "",
                    food_state: "",
                  }))
                }
              >
                Clear filters
              </button>
            </div>
          ) : null}

          {fridge.error ? (
            <div className="fridge-inline-error" role="alert">
              <Icon name="warning" />
              <span>{fridge.error}</span>
              <button type="button" onClick={() => void fridge.loadInventory()}>
                Retry
              </button>
            </div>
          ) : null}

          {fridge.isLoading ? (
            <InventorySkeleton />
          ) : fridge.list.items.length > 0 ? (
            <div className="fridge-card-grid">
              {fridge.list.items.map((item) => (
                <FridgeItemCard
                  key={item.fridge_item_id}
                  item={item}
                  onEdit={() => setDrawerItem(item)}
                  onDelete={() => setDeleteItem(item)}
                />
              ))}
            </div>
          ) : (
            <EmptyInventory
              isFiltered={Boolean(searchText || activeFilterCount)}
              onAdd={() => setDrawerItem("new")}
              onReset={() => {
                setSearchText("");
                setQuery(DEFAULT_QUERY);
              }}
            />
          )}
        </section>

        <InventoryRail
          summary={fridge.summary}
          settings={fridge.settings}
          items={fridge.list.items}
          isSaving={fridge.isSaving}
          onSaveSettings={fridge.updateSettings}
        />
      </div>

      {drawerItem ? (
        <ItemDrawer
          item={drawerItem === "new" ? null : drawerItem}
          isSaving={fridge.isSaving}
          apiError={fridge.error}
          onClose={() => setDrawerItem(null)}
          onSubmit={submitItem}
        />
      ) : null}

      {deleteItem ? (
        <DeleteDialog
          item={deleteItem}
          isDeleting={fridge.isSaving}
          onCancel={() => setDeleteItem(null)}
          onConfirm={confirmDelete}
        />
      ) : null}
    </main>
  );
}

function CategoryChips({
  categories,
  active,
  onSelect,
}: {
  categories: string[];
  active: string;
  onSelect: (category: string) => void;
}) {
  return (
    <div className="fridge-category-chips" aria-label="Inventory category">
      <button
        type="button"
        className={!active ? "is-active" : ""}
        onClick={() => onSelect("")}
      >
        All
      </button>
      {categories.slice(0, 7).map((category) => (
        <button
          type="button"
          className={active === category ? "is-active" : ""}
          key={category}
          title={category}
          onClick={() => onSelect(category)}
        >
          {shortCategory(category)}
        </button>
      ))}
    </div>
  );
}

function FridgeItemCard({
  item,
  onEdit,
  onDelete,
}: {
  item: FridgeItem;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const statusTone = item.expiry_status.toLowerCase().replaceAll("_", "-");
  return (
    <article className={`fridge-card fridge-card--${statusTone}`}>
      <div className="fridge-card__topline">
        <span className={`fridge-card__category fridge-card__category--${statusTone}`}>
          {shortCategory(item.ingredient.category)}
        </span>
        <div className="fridge-card__actions">
          <button type="button" aria-label={`Edit ${item.ingredient.name}`} onClick={onEdit}>
            <Icon name="edit" />
          </button>
          <button
            type="button"
            aria-label={`Delete ${item.ingredient.name}`}
            onClick={onDelete}
          >
            <Icon name="trash" />
          </button>
        </div>
      </div>
      <h3>{item.ingredient.name}</h3>
      <p className="fridge-card__variant">
        {item.ingredient.variant || "Standard ingredient"}
      </p>
      <div className="fridge-card__quantity">
        <strong>{formatQuantity(item.quantity)}</strong>
        <span>{item.unit}</span>
        {item.food_state ? <small>{FOOD_STATE_LABELS[item.food_state]}</small> : null}
      </div>
      <div className="fridge-card__stability">
        <div>
          <span>Stability</span>
          <strong>{STATUS_LABELS[item.expiry_status]}</strong>
        </div>
        <span className="fridge-card__bar"><i /></span>
      </div>
      <div className="fridge-card__expiry">
        <Icon name="calendar" />
        <div>
          <span>{expiryMessage(item.days_until_expiry)}</span>
          <strong>{formatDate(item.expiry_date)}</strong>
        </div>
      </div>
    </article>
  );
}

function InventoryRail({
  summary,
  settings,
  items,
  isSaving,
  onSaveSettings,
}: {
  summary: FridgeSummary | null;
  settings: NotificationSettings | null;
  items: FridgeItem[];
  isSaving: boolean;
  onSaveSettings: (
    settings: Omit<NotificationSettings, "updated_at">,
  ) => Promise<void>;
}) {
  const [draft, setDraft] = useState<NotificationSettings | null>(settings);
  useEffect(() => setDraft(settings), [settings]);
  const nearestRisk = items.find((item) => item.expiry_status !== "FRESH");
  const maxCategoryCount = Math.max(
    1,
    ...(summary?.categories.map((category) => category.count) ?? []),
  );

  return (
    <aside className="fridge-rail">
      <section className="fridge-rail__section">
        <div className="fridge-rail__heading">
          <Icon name="activity" />
          <div>
            <p>Inventory signals</p>
            <h2>Storage overview</h2>
          </div>
        </div>
        <div className="fridge-summary-grid">
          <SummaryMetric label="Fresh" value={summary?.fresh ?? 0} tone="fresh" />
          <SummaryMetric
            label="Expiring"
            value={(summary?.expiring_soon ?? 0) + (summary?.expiring_today ?? 0)}
            tone="soon"
          />
          <SummaryMetric label="Expired" value={summary?.expired ?? 0} tone="expired" />
        </div>
      </section>

      <section className="fridge-rail__section">
        <p className="fridge-rail__eyebrow">Category distribution</p>
        <div className="fridge-category-bars">
          {summary?.categories.length ? (
            summary.categories.slice(0, 5).map((category) => (
              <div key={category.category}>
                <span title={category.category}>{shortCategory(category.category)}</span>
                <i>
                  <b style={{ width: `${(category.count / maxCategoryCount) * 100}%` }} />
                </i>
                <strong>{category.count}</strong>
              </div>
            ))
          ) : (
            <span className="fridge-rail__empty">No category data yet.</span>
          )}
        </div>
      </section>

      {nearestRisk ? (
        <section className={`fridge-risk-card fridge-risk-card--${nearestRisk.expiry_status.toLowerCase()}`}>
          <Icon name="warning" />
          <div>
            <p>Next stability risk</p>
            <strong>{nearestRisk.ingredient.name}</strong>
            <span>
              {expiryMessage(nearestRisk.days_until_expiry)}. Use or update this item to keep the inventory accurate.
            </span>
          </div>
        </section>
      ) : null}

      {draft ? (
        <section className="fridge-rail__section fridge-reminder-settings">
          <div className="fridge-reminder-settings__title">
            <div>
              <p className="fridge-rail__eyebrow">Expiry protocol</p>
              <h3>Smart reminders</h3>
            </div>
            <label className="fridge-toggle">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, enabled: event.target.checked } : current,
                  )
                }
              />
              <span />
            </label>
          </div>
          <div className="fridge-reminder-settings__fields">
            <label>
              Warn me
              <select
                value={draft.warning_days}
                disabled={!draft.enabled}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, warning_days: Number(event.target.value) } : current,
                  )
                }
              >
                <option value={1}>1 day before</option>
                <option value={2}>2 days before</option>
                <option value={3}>3 days before</option>
                <option value={5}>5 days before</option>
                <option value={7}>7 days before</option>
              </select>
            </label>
            <label>
              Delivery time
              <select
                value={draft.delivery_hour}
                disabled={!draft.enabled}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, delivery_hour: Number(event.target.value) } : current,
                  )
                }
              >
                {[7, 8, 9, 10, 12, 18, 20].map((hour) => (
                  <option key={hour} value={hour}>{`${String(hour).padStart(2, "0")}:00`}</option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="button"
            disabled={isSaving || sameSettings(draft, settings)}
            onClick={() =>
              void onSaveSettings({
                enabled: draft.enabled,
                warning_days: draft.warning_days,
                timezone: draft.timezone,
                delivery_hour: draft.delivery_hour,
              })
            }
          >
            {isSaving ? "Saving..." : "Save reminder policy"}
          </button>
        </section>
      ) : null}
    </aside>
  );
}

function SummaryMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "fresh" | "soon" | "expired";
}) {
  return (
    <article className={`fridge-summary-metric fridge-summary-metric--${tone}`}>
      <span>{label}</span>
      <strong>{String(value).padStart(2, "0")}</strong>
    </article>
  );
}

function ItemDrawer({
  item,
  isSaving,
  apiError,
  onClose,
  onSubmit,
}: {
  item: FridgeItem | null;
  isSaving: boolean;
  apiError: string | null;
  onClose: () => void;
  onSubmit: (input: FridgeItemInput) => Promise<void>;
}) {
  const [ingredientQuery, setIngredientQuery] = useState(item?.ingredient.name ?? "");
  const [selectedIngredient, setSelectedIngredient] = useState<Ingredient | null>(
    item?.ingredient ?? null,
  );
  const [ingredientResults, setIngredientResults] = useState<Ingredient[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [quantity, setQuantity] = useState(item ? String(item.quantity) : "");
  const [unit, setUnit] = useState(item?.unit ?? "g");
  const [foodState, setFoodState] = useState<FoodState | "">(item?.food_state ?? "RAW");
  const [expiryDate, setExpiryDate] = useState(item?.expiry_date ?? "");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedIngredient && ingredientQuery === selectedIngredient.name) return;
    const timeout = window.setTimeout(async () => {
      setIsSearching(true);
      try {
        const response = await searchIngredients(ingredientQuery);
        setIngredientResults(response.items);
      } catch {
        setIngredientResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [ingredientQuery, selectedIngredient]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numericQuantity = Number(quantity);
    if (!selectedIngredient) {
      setFormError("Choose an ingredient from the search results.");
      return;
    }
    if (!Number.isFinite(numericQuantity) || numericQuantity <= 0) {
      setFormError("Quantity must be greater than zero.");
      return;
    }
    if (!unit.trim()) {
      setFormError("Unit is required.");
      return;
    }
    if (!expiryDate) {
      setFormError("Expiry date is required.");
      return;
    }
    setFormError(null);
    await onSubmit({
      ingredient_id: selectedIngredient.ingredient_id,
      quantity: numericQuantity,
      unit: unit.trim(),
      food_state: foodState || null,
      expiry_date: expiryDate,
    });
  }

  function chooseIngredient(ingredient: Ingredient) {
    setSelectedIngredient(ingredient);
    setIngredientQuery(ingredient.name);
    setIngredientResults([]);
  }

  return (
    <div
      className="fridge-drawer-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isSaving) onClose();
      }}
    >
      <aside
        className="fridge-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fridge-drawer-title"
      >
        <header className="fridge-drawer__header">
          <div className="fridge-drawer__icon"><Icon name={item ? "edit" : "plus"} /></div>
          <div>
            <p>{item ? "Inventory record" : "New inventory record"}</p>
            <h2 id="fridge-drawer-title">{item ? "Update fridge item" : "Add to fridge"}</h2>
          </div>
          <button type="button" disabled={isSaving} onClick={onClose} aria-label="Close drawer">×</button>
        </header>

        <form className="fridge-form" onSubmit={(event) => void submit(event)}>
          <fieldset>
            <legend><span>1</span> Identification</legend>
            <label className="fridge-form__ingredient">
              Food / ingredient
              <div>
                <Icon name="search" />
                <input
                  autoFocus
                  value={ingredientQuery}
                  placeholder="e.g. Atlantic salmon, spinach..."
                  onChange={(event) => {
                    setIngredientQuery(event.target.value);
                    setSelectedIngredient(null);
                  }}
                />
                {isSearching ? <i className="fridge-form__spinner" /> : null}
              </div>
              {ingredientResults.length > 0 ? (
                <ul className="fridge-ingredient-results">
                  {ingredientResults.map((ingredient) => (
                    <li key={ingredient.ingredient_id}>
                      <button type="button" onClick={() => chooseIngredient(ingredient)}>
                        <span><strong>{ingredient.name}</strong><small>{ingredient.variant || "Standard"}</small></span>
                        <em>{shortCategory(ingredient.category)}</em>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </label>
            <div className="fridge-form__readonly">
              <span>Biochemical category</span>
              <strong>{selectedIngredient ? selectedIngredient.category : "Select an ingredient first"}</strong>
            </div>
          </fieldset>

          <fieldset>
            <legend><span>2</span> Quantification & state</legend>
            <div className="fridge-form__two-columns">
              <label>
                Volume / mass
                <input
                  type="number"
                  min="0.001"
                  step="0.001"
                  inputMode="decimal"
                  value={quantity}
                  placeholder="0.0"
                  onChange={(event) => setQuantity(event.target.value)}
                />
              </label>
              <label>
                Unit
                <input
                  value={unit}
                  maxLength={32}
                  placeholder="g, ml, pcs..."
                  onChange={(event) => setUnit(event.target.value)}
                />
              </label>
            </div>
            <div className="fridge-form__state-label">Physical state</div>
            <div className="fridge-state-options">
              {(Object.keys(FOOD_STATE_LABELS) as FoodState[]).map((state) => (
                <button
                  type="button"
                  className={foodState === state ? "is-active" : ""}
                  key={state}
                  onClick={() => setFoodState(state)}
                >
                  <Icon name={state === "FROZEN" ? "snow" : state === "COOKED" ? "heat" : "state"} />
                  {FOOD_STATE_LABELS[state]}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="fridge-form__danger-legend"><span>3</span> Stability protocol</legend>
            <label>
              Estimated expiry
              <input
                type="date"
                value={expiryDate}
                onChange={(event) => setExpiryDate(event.target.value)}
              />
            </label>
            <div className="fridge-quick-dates">
              <button type="button" onClick={() => setExpiryDate(addDays(expiryDate, 3))}>+3 days</button>
              <button type="button" onClick={() => setExpiryDate(addDays(expiryDate, 7))}>+1 week</button>
              <button type="button" onClick={() => setExpiryDate(addDays(expiryDate, 30))}>+1 month</button>
            </div>
          </fieldset>

          {formError || apiError ? (
            <div className="fridge-form__error" role="alert">
              <Icon name="warning" /> {formError ?? apiError}
            </div>
          ) : null}

          <div className="fridge-form__actions">
            <button type="button" disabled={isSaving} onClick={onClose}>Cancel</button>
            <button type="submit" disabled={isSaving}>
              <Icon name="save" /> {isSaving ? "Saving..." : item ? "Save changes" : "Save item"}
            </button>
          </div>
        </form>
      </aside>
    </div>
  );
}

function DeleteDialog({
  item,
  isDeleting,
  onCancel,
  onConfirm,
}: {
  item: FridgeItem;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
}) {
  return (
    <div className="fridge-dialog-backdrop" role="presentation">
      <section className="fridge-delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-title">
        <span className="fridge-delete-dialog__icon"><Icon name="trash" /></span>
        <p>Remove inventory record</p>
        <h2 id="delete-title">Delete {item.ingredient.name}?</h2>
        <span>This removes the stored quantity and its expiry tracking. This action cannot be undone.</span>
        <div>
          <button type="button" disabled={isDeleting} onClick={onCancel}>Keep item</button>
          <button type="button" disabled={isDeleting} onClick={() => void onConfirm()}>
            {isDeleting ? "Deleting..." : "Delete item"}
          </button>
        </div>
      </section>
    </div>
  );
}

function NotificationCenter({
  notifications,
  onRead,
  onReadAll,
  onClose,
}: {
  notifications: ExpiryNotification[];
  onRead: (id: string) => Promise<void>;
  onReadAll: () => Promise<void>;
  onClose: () => void;
}) {
  const unread = notifications.filter((notification) => notification.status !== "READ");
  return (
    <section className="fridge-notifications" aria-label="Expiry notifications">
      <header>
        <div><p>Stability alerts</p><h2>Notifications</h2></div>
        <button type="button" aria-label="Close notifications" onClick={onClose}>×</button>
      </header>
      {notifications.length ? (
        <div className="fridge-notifications__list">
          {notifications.map((notification) => (
            <button
              type="button"
              className={notification.status !== "READ" ? "is-unread" : ""}
              key={notification.notification_id}
              onClick={() => notification.status !== "READ" && void onRead(notification.notification_id)}
            >
              <span><Icon name={notification.notification_type === "EXPIRED" ? "warning" : "clock"} /></span>
              <div><strong>{notification.title}</strong><p>{notification.message}</p><small>{formatRelativeTime(notification.created_at)}</small></div>
            </button>
          ))}
        </div>
      ) : (
        <div className="fridge-notifications__empty"><Icon name="bell" /><strong>No alerts yet</strong><span>Expiry reminders will appear here.</span></div>
      )}
      {unread.length ? <button className="fridge-notifications__read-all" type="button" onClick={() => void onReadAll()}>Mark all as read</button> : null}
    </section>
  );
}

function EmptyInventory({
  isFiltered,
  onAdd,
  onReset,
}: {
  isFiltered: boolean;
  onAdd: () => void;
  onReset: () => void;
}) {
  return (
    <section className="fridge-empty">
      <span><Icon name={isFiltered ? "search" : "fridge"} /></span>
      <p>{isFiltered ? "No matches" : "Inventory is empty"}</p>
      <h2>{isFiltered ? "Try a broader search" : "Start tracking what you have"}</h2>
      <small>
        {isFiltered
          ? "Clear your filters or search for another ingredient."
          : "Add your first ingredient to monitor quantity and expiry."}
      </small>
      <button type="button" onClick={isFiltered ? onReset : onAdd}>
        {isFiltered ? "Reset search" : "Add first item"}
      </button>
    </section>
  );
}

function InventorySkeleton() {
  return (
    <div className="fridge-card-grid" aria-label="Loading inventory">
      {[1, 2, 3, 4].map((index) => <span className="fridge-card-skeleton" key={index} />)}
    </div>
  );
}

type IconName =
  | "activity" | "bell" | "calendar" | "clock" | "edit" | "filter"
  | "fridge" | "heat" | "plus" | "save" | "search" | "snow"
  | "state" | "trash" | "warning";

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    activity: <><path d="M4 17h3l2.1-9 3.3 11 2.2-7H20" /><path d="M5 4.5h14" /></>,
    bell: <><path d="M7 10a5 5 0 0 1 10 0c0 5 2 5 2 6H5c0-1 2-1 2-6Z" /><path d="M10 19h4" /></>,
    calendar: <><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></>,
    clock: <><circle cx="12" cy="12" r="8" /><path d="M12 8v5l3 2" /></>,
    edit: <><path d="m5 16-.8 3.8L8 19l10-10-3-3L5 16Z" /><path d="m13.8 7.2 3 3" /></>,
    filter: <path d="M4 6h16l-6 7v5l-4 2v-7L4 6Z" />,
    fridge: <><rect x="6" y="3" width="12" height="18" rx="2" /><path d="M6 9h12M9 6v1M9 12v2" /></>,
    heat: <><path d="M8 18c-2-3 1-4 0-7M12 18c-2-3 1-5 0-9M16 18c-2-3 1-4 0-7" /></>,
    plus: <path d="M12 5v14M5 12h14" />,
    save: <><path d="M5 4h12l2 2v14H5V4Z" /><path d="M8 4v6h8V4M8 20v-6h8v6" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>,
    snow: <><path d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9" /></>,
    state: <><circle cx="12" cy="12" r="7" /><path d="M12 5v14M5 12h14" /></>,
    trash: <><path d="M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" /></>,
    warning: <><path d="m12 4 9 16H3L12 4Z" /><path d="M12 9v5M12 17h.01" /></>,
  };
  return <svg className="fridge-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function shortCategory(category: string): string {
  const compact = category
    .replace(/\s+and\s+.*products?/i, "")
    .replace(/products?/gi, "")
    .replace(/finfish and shellfish/i, "Seafood")
    .replace(/vegetables?/i, "Vegetables")
    .trim();
  return compact.length > 22 ? `${compact.slice(0, 20)}…` : compact || "Other";
}

function formatQuantity(quantity: number): string {
  return new Intl.NumberFormat("en", { maximumFractionDigits: 3 }).format(quantity);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", { day: "2-digit", month: "short", year: "numeric" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function expiryMessage(days: number): string {
  if (days < -1) return `Expired ${Math.abs(days)} days ago`;
  if (days === -1) return "Expired yesterday";
  if (days === 0) return "Expires today";
  if (days === 1) return "Expires tomorrow";
  return `Expires in ${days} days`;
}

function addDays(current: string, days: number): string {
  const base = current ? new Date(`${current}T12:00:00`) : new Date();
  base.setDate(base.getDate() + days);
  return `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, "0")}-${String(base.getDate()).padStart(2, "0")}`;
}

function sameSettings(a: NotificationSettings, b: NotificationSettings | null): boolean {
  return Boolean(
    b && a.enabled === b.enabled && a.warning_days === b.warning_days &&
    a.timezone === b.timezone && a.delivery_hour === b.delivery_hour,
  );
}

function formatRelativeTime(value: string): string {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
