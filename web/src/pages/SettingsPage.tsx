import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";

type SettingsPageProps = {
  onLoggedOut: () => Promise<void>;
};

export function SettingsPage({ onLoggedOut }: SettingsPageProps) {
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState(true);
  const [notificationEmail, setNotificationEmail] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const result = await api.getSettings();
    setEnabled(result.email_notifications_enabled);
    setNotificationEmail(result.notification_email);
    setLoginEmail(result.login_email);
    setDisplayName(result.display_name);
  }

  useEffect(() => {
    void load().catch((err) => setError(err instanceof ApiError ? err.message : "设置加载失败"));
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.saveSettings({
        emailNotificationsEnabled: enabled,
        notificationEmail
      });
      setMessage("设置已保存。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    await api.logout();
    await onLoggedOut();
    navigate("/login");
  }

  return (
    <section className="page">
      <div className="panel">
        <h2>设置</h2>
        <p className="muted">
          {displayName} · {loginEmail}
        </p>
      </div>
      <div className="panel">
        <form className="stack-form" onSubmit={handleSubmit}>
          <label className="toggle-row">
            <strong>成绩邮件提醒</strong>
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
          </label>
          <label className="field">
            <span>通知邮箱</span>
            <input value={notificationEmail} onChange={(event) => setNotificationEmail(event.target.value)} />
          </label>
          {message ? <div className="message success">{message}</div> : null}
          {error ? <div className="message error">{error}</div> : null}
          <button className="button primary" disabled={saving}>
            {saving ? "保存中..." : "保存设置"}
          </button>
          <button type="button" className="button ghost" onClick={handleLogout}>
            退出登录
          </button>
        </form>
      </div>
    </section>
  );
}
