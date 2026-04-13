import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";

type PortalData = Awaited<ReturnType<typeof api.getPortal>>;

export function PortalPage() {
  const [data, setData] = useState<PortalData | null>(null);
  const [portalUsername, setPortalUsername] = useState("");
  const [portalPassword, setPortalPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const result = await api.getPortal();
      setData(result);
      setPortalUsername(result.portal_username ?? "");
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载教务账号失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.savePortal({ portalUsername, portalPassword });
      setMessage("教务账号已保存。");
      setPortalPassword("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="page">
      <div className="panel">
        <h2>教务账号</h2>
        {loading ? (
          <p className="muted">正在加载...</p>
        ) : (
          <div className="status-grid">
            <div className="status-card">
              <span>绑定状态</span>
              <strong>{data?.is_bound ? "已绑定" : "未绑定"}</strong>
            </div>
            <div className="status-card">
              <span>最近登录</span>
              <strong>{data?.last_successful_login_at ? new Date(data.last_successful_login_at).toLocaleString() : "暂无"}</strong>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <form className="stack-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>教务账号 / 学号</span>
            <input value={portalUsername} onChange={(event) => setPortalUsername(event.target.value)} />
          </label>
          <label className="field">
            <span>教务密码</span>
            <input
              type="password"
              value={portalPassword}
              onChange={(event) => setPortalPassword(event.target.value)}
              placeholder="重新保存时请再次输入"
            />
          </label>
          {message ? <div className="message success">{message}</div> : null}
          {error ? <div className="message error">{error}</div> : null}
          <button className="button primary" disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </button>
        </form>
      </div>
    </section>
  );
}
