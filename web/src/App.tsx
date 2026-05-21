import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ApiError, api } from "./lib/api";
import { GradesPage } from "./pages/GradesPage";
import { LoginPage } from "./pages/LoginPage";
import { PortalPage } from "./pages/PortalPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SchedulePage } from "./pages/SchedulePage";
import { SettingsPage } from "./pages/SettingsPage";

type SessionUser = {
  id: string;
  display_name: string;
  email: string;
};

type AppNotification = {
  id: string;
  fingerprint?: string;
  title: string;
  body: string;
  level: "info" | "warning" | "error" | string;
  created_at?: string | null;
};

type NotificationPayload = {
  version: string;
  items: AppNotification[];
};

const SHOWN_NOTIFICATION_KEY = "cat-schedule:notifications:shown";

function readShownNotificationIds() {
  try {
    return new Set(JSON.parse(window.localStorage.getItem(SHOWN_NOTIFICATION_KEY) || "[]") as string[]);
  } catch {
    return new Set<string>();
  }
}

function writeShownNotificationIds(values: Set<string>) {
  try {
    window.localStorage.setItem(SHOWN_NOTIFICATION_KEY, JSON.stringify([...values]));
  } catch {
    // Local notification state is best-effort only.
  }
}

function NotificationCenter({ enabled }: { enabled: boolean }) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  useEffect(() => {
    if (!enabled) {
      setNotifications([]);
      return undefined;
    }

    let cancelled = false;

    async function checkNotifications() {
      try {
        const response = await fetch("/api/notifications", { credentials: "include" });
        if (!response.ok) {
          return;
        }
        const envelope = (await response.json()) as { ok: boolean; data: NotificationPayload };
        if (!envelope.ok) {
          return;
        }
        const shownIds = readShownNotificationIds();
        const unseen = envelope.data.items.filter((item) => !shownIds.has(`${item.id}:${item.fingerprint || ""}`));
        if (!unseen.length || cancelled) {
          return;
        }
        for (const item of unseen) {
          shownIds.add(`${item.id}:${item.fingerprint || ""}`);
        }
        writeShownNotificationIds(shownIds);
        setNotifications((current) => [...current, ...unseen]);
      } catch {
        // Notification polling must never interrupt normal app usage.
      }
    }

    void checkNotifications();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  if (!notifications.length) {
    return null;
  }

  return (
    <div className="notification-stack">
      {notifications.map((item) => (
        <article key={item.id} className={`app-notification ${item.level || "info"}`}>
          <button
            className="notification-close"
            aria-label="关闭通知"
            onClick={() => setNotifications((current) => current.filter((entry) => entry.id !== item.id))}
          >
            ×
          </button>
          <strong>{item.title}</strong>
          {item.body ? <p>{item.body}</p> : null}
        </article>
      ))}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshSession() {
    setLoading(true);
    try {
      const result = await api.me();
      setUser(result.user);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshSession();
  }, []);

  if (loading) {
    return <div className="app-loading">正在加载应用...</div>;
  }

  return (
    <>
      <NotificationCenter enabled={Boolean(user)} />
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/app/portal" replace /> : <LoginPage onAuthed={refreshSession} />} />
        <Route
          path="/register"
          element={user ? <Navigate to="/app/portal" replace /> : <RegisterPage onAuthed={refreshSession} />}
        />
        {user ? (
          <Route path="/app" element={<AppShell />}>
            <Route path="portal" element={<PortalPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="grades" element={<GradesPage />} />
            <Route path="settings" element={<SettingsPage onLoggedOut={refreshSession} />} />
            <Route index element={<Navigate to="/app/portal" replace />} />
          </Route>
        ) : null}
        <Route path="*" element={<Navigate to={user ? "/app/portal" : "/login"} replace />} />
      </Routes>
    </>
  );
}
