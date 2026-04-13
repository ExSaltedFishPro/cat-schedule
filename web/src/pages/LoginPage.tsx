import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";

type LoginPageProps = {
  onAuthed: () => Promise<void>;
};

export function LoginPage({ onAuthed }: LoginPageProps) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.login({ email, password });
      await onAuthed();
      navigate("/app/schedule");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <section className="auth-card">
        <h1>登录</h1>
        <form className="stack-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>邮箱</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入登录密码"
            />
          </label>
          {error ? <div className="message error">{error}</div> : null}
          <button className="button primary" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </button>
        </form>
        <div className="auth-footer">
          <span>已有邀请链接？</span>
          <Link to="/register">去注册</Link>
        </div>
      </section>
    </div>
  );
}
