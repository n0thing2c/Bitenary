import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SettingsPanel } from "./SettingsPanel";

function renderPanel(overrides: Partial<{
  onClose: () => void;
  onOpenMcpConnections: () => void;
  onChangePassword: () => void;
}> = {}) {
  const props = {
    onClose: vi.fn(),
    onOpenMcpConnections: vi.fn(),
    onChangePassword: vi.fn(),
    ...overrides,
  };
  render(<SettingsPanel {...props} />);
  return props;
}

describe("SettingsPanel", () => {
  it("renders both settings actions and focuses the close button", () => {
    renderPanel();

    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "MCP connections" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Change password" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close settings" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("closes from the close button, backdrop and Escape key", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPanel({ onClose });

    await user.click(screen.getByRole("button", { name: "Close settings" }));
    fireEvent.mouseDown(screen.getByTestId("settings-backdrop"));
    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("dispatches MCP and password actions", async () => {
    const user = userEvent.setup();
    const props = renderPanel();

    await user.click(screen.getByRole("button", { name: "MCP connections" }));
    await user.click(screen.getByRole("button", { name: "Change password" }));

    expect(props.onOpenMcpConnections).toHaveBeenCalledOnce();
    expect(props.onChangePassword).toHaveBeenCalledOnce();
  });
});
