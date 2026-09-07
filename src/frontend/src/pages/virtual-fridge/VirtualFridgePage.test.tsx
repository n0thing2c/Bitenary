import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { searchIngredients } from "../../features/virtual-fridge/api/virtualFridgeApi";
import type {
  Ingredient,
  IngredientList,
} from "../../features/virtual-fridge/model/types";
import { useVirtualFridge } from "../../features/virtual-fridge/model/useVirtualFridge";
import { VirtualFridgePage } from "./VirtualFridgePage";

vi.mock("../../features/virtual-fridge/api/virtualFridgeApi", () => ({
  searchIngredients: vi.fn(),
}));

vi.mock("../../features/virtual-fridge/model/useVirtualFridge", () => ({
  useVirtualFridge: vi.fn(),
}));

const pork: Ingredient = {
  ingredient_id: "ingredient-pork",
  name: "Pork",
  variant: "fresh, loin, whole, raw",
  category: "Pork Products",
  is_default: true,
};

const beef: Ingredient = {
  ingredient_id: "ingredient-beef",
  name: "Beef",
  variant: "brisket, whole, raw",
  category: "Beef Products",
  is_default: true,
};

function ingredientList(items: Ingredient[]): IngredientList {
  return { items, page: 1, size: 8, total_in_page: items.length };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

function renderPage() {
  render(
    <MemoryRouter>
      <VirtualFridgePage />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Add item" }));
  return screen.getByPlaceholderText("e.g. Atlantic salmon, spinach...");
}

describe("Virtual Fridge ingredient search", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(useVirtualFridge).mockReturnValue({
      list: { items: [], page: 1, size: 100, total: 0, total_pages: 0 },
      summary: null,
      categories: [],
      settings: null,
      isLoading: false,
      isSaving: false,
      error: null,
      loadInventory: vi.fn(async () => undefined),
      saveItem: vi.fn(async () => undefined),
      removeItem: vi.fn(async () => undefined),
      updateSettings: vi.fn(async () => undefined),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("does not request suggestions for an empty query", async () => {
    renderPage();

    await act(async () => vi.advanceTimersByTimeAsync(300));

    expect(searchIngredients).not.toHaveBeenCalled();
  });

  it("does not render a second notification trigger", () => {
    render(
      <MemoryRouter>
        <VirtualFridgePage />
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: "Notifications" }),
    ).not.toBeInTheDocument();
  });

  it("ignores an older response after the query changes", async () => {
    const porkRequest = deferred<IngredientList>();
    const beefRequest = deferred<IngredientList>();
    vi.mocked(searchIngredients)
      .mockReturnValueOnce(porkRequest.promise)
      .mockReturnValueOnce(beefRequest.promise);
    const input = renderPage();

    fireEvent.change(input, { target: { value: "pork" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));
    fireEvent.change(input, { target: { value: "beef" } });
    await act(async () => vi.advanceTimersByTimeAsync(250));

    await act(async () => beefRequest.resolve(ingredientList([beef])));
    expect(screen.getByRole("button", { name: /Beef/ })).toBeInTheDocument();

    await act(async () => porkRequest.resolve(ingredientList([pork])));
    expect(screen.queryByRole("button", { name: /Pork/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Beef/ })).toBeInTheDocument();
  });
});
