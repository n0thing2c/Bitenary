import type { ReactNode } from "react";
import type { CurrentUser } from "../../auth/model/types";
import { TopNav } from "../../../shared/ui/TopNav";

type AppShellProps = {
  user: CurrentUser;
  children: ReactNode;
  isLoggingOut: boolean;
  onLogout: () => void;
};

export function AppShell({
  user,
  children,
  isLoggingOut,
  onLogout,
}: AppShellProps) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "var(--color-paper)" }}>
      <TopNav user={user} isLoggingOut={isLoggingOut} onLogout={onLogout} />
      <div 
        style={{ 
          flex: 1, 
          display: "flex", 
          flexDirection: "column",
          background: "var(--color-surface)",
          borderTopLeftRadius: "var(--radius-lg)",
          borderTopRightRadius: "var(--radius-lg)",
          borderTop: "1px solid var(--color-border)",
          borderLeft: "1px solid var(--color-border)",
          borderRight: "1px solid var(--color-border)",
          overflow: "hidden"
        }}
      >
        {children}
      </div>
    </div>
  );
}
