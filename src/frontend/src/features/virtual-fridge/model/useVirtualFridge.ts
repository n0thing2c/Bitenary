import { useCallback, useEffect, useRef, useState } from "react";

import {
  createFridgeItem,
  deleteFridgeItem,
  getFridgeItems,
  getFridgeSummary,
  getIngredientCategories,
  getNotificationSettings,
  saveNotificationSettings,
  updateFridgeItem,
} from "../api/virtualFridgeApi";
import type {
  FridgeItem,
  FridgeItemInput,
  FridgeItemList,
  FridgeSummary,
  InventoryQuery,
  NotificationSettings,
} from "./types";

const EMPTY_LIST: FridgeItemList = {
  items: [],
  page: 1,
  size: 100,
  total: 0,
  total_pages: 0,
};

export function useVirtualFridge(query: InventoryQuery) {
  const [list, setList] = useState<FridgeItemList>(EMPTY_LIST);
  const [summary, setSummary] = useState<FridgeSummary | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const loadInventory = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setIsLoading(true);
    setError(null);
    try {
      const [items, nextSummary] = await Promise.all([
        getFridgeItems(query),
        getFridgeSummary(),
      ]);
      if (requestId.current !== currentRequest) return;
      setList(items);
      setSummary(nextSummary);
    } catch {
      if (requestId.current !== currentRequest) return;
      setError("We could not load your fridge. Check the connection and try again.");
    } finally {
      if (requestId.current === currentRequest) setIsLoading(false);
    }
  }, [query]);

  const loadSupportData = useCallback(async () => {
    const results = await Promise.allSettled([
      getIngredientCategories(),
      getNotificationSettings(),
    ]);
    const [categoryResult, settingsResult] = results;
    if (categoryResult.status === "fulfilled") {
      setCategories(categoryResult.value.categories);
    }
    if (settingsResult.status === "fulfilled") {
      setSettings(settingsResult.value);
    }
  }, []);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    void loadSupportData();
  }, [loadSupportData]);

  const saveItem = useCallback(
    async (input: FridgeItemInput, itemId?: string) => {
      setIsSaving(true);
      setError(null);
      try {
        if (itemId) await updateFridgeItem(itemId, input);
        else await createFridgeItem(input);
        await loadInventory();
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "The item could not be saved.";
        setError(message);
        throw caught;
      } finally {
        setIsSaving(false);
      }
    },
    [loadInventory],
  );

  const removeItem = useCallback(
    async (item: FridgeItem) => {
      setIsSaving(true);
      setError(null);
      try {
        await deleteFridgeItem(item.fridge_item_id);
        await loadInventory();
      } catch (caught) {
        const message =
          caught instanceof Error ? caught.message : "The item could not be deleted.";
        setError(message);
        throw caught;
      } finally {
        setIsSaving(false);
      }
    },
    [loadInventory],
  );

  const updateSettings = useCallback(
    async (nextSettings: Omit<NotificationSettings, "updated_at">) => {
      setIsSaving(true);
      setError(null);
      try {
        setSettings(await saveNotificationSettings(nextSettings));
      } catch (caught) {
        setError("Reminder settings could not be saved.");
        throw caught;
      } finally {
        setIsSaving(false);
      }
    },
    [],
  );

  return {
    list,
    summary,
    categories,
    settings,
    isLoading,
    isSaving,
    error,
    loadInventory,
    saveItem,
    removeItem,
    updateSettings,
  };
}
