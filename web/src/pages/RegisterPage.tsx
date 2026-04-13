import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";

type RegisterPageProps = {
  onAuthed: () => Promise<void>;
};

export function RegisterPage({ onAuthed }: RegisterPageProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite") ?? "";
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(Boolean(inviteToken));
  const [inviteMessage, setInviteMessage] = useState(inviteToken ? "正在校验邀请链接..." : "需要邀请链接才能注册。");
  const [inviteValid, setInviteValid] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!inviteToken) {
      return;
    }

    setVerifying(true);
    void api
      .verifyInvite(inviteToken)
      .then((data) => {
        setInviteValid(true);
        const details = [
          data.note ? `备注：${data.note}` : "",
          typeof data.remaining_uses === "number" ? `剩余 ${data.remaining_uses} 次` : ""
        ]
          .filter(Boolean)
          .join(" · ");
        setInviteMessage(details ? `邀请可用 · ${details}` : "邀请可用");
      })
      .catch((err) => {
        setInviteValid(false);
        setInviteMessage(err instanceof ApiError ? err.message : "邀请链接不可用");
      })
      .finally(() => setVerifying(false));
  }, [inviteToken]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.register({
        displayName,
        email,
        password,
        inviteToken
      });
      await onAuthed();
      navigate("/app/portal");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <section className="auth-card">
        <h1>创建账号</h1>
        <div className={inviteValid ? "message success" : "message warning"}>{inviteMessage}</div>
        <form className="stack-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>昵称</span>
            <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="怎么称呼你" />
          </label>
          <label className="field">
            <span>邮箱</span>
            <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="接收通知的邮箱" />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="至少 8 位"
            />
          </label>
          {error ? <div className="message error">{error}</div> : null}
          <button className="button primary" disabled={!inviteValid || verifying || loading}>
            {loading ? "注册中..." : "注册并登录"}
          </button>
        </form>
        <div className="auth-footer">
          <span>已经有账号了？</span>
          <Link to="/login">返回登录</Link>
        </div>
      </section>
    </div>
  );
}
