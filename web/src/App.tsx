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
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/app/schedule" replace /> : <LoginPage onAuthed={refreshSession} />} />
      <Route
        path="/register"
        element={user ? <Navigate to="/app/schedule" replace /> : <RegisterPage onAuthed={refreshSession} />}
      />
      {user ? (
        <Route path="/app" element={<AppShell />}>
          <Route path="portal" element={<PortalPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="grades" element={<GradesPage />} />
          <Route path="settings" element={<SettingsPage onLoggedOut={refreshSession} />} />
          <Route index element={<Navigate to="/app/schedule" replace />} />
        </Route>
      ) : null}
      <Route path="*" element={<Navigate to={user ? "/app/schedule" : "/login"} replace />} />
    </Routes>
  );
}
