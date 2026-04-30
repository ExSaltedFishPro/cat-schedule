import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";

type PortalData = Awaited<ReturnType<typeof api.getPortal>>;
type ExamItem = {
  id: string;
  course_name: string;
  exam_time_text?: string | null;
  exam_start_at?: string | null;
  exam_end_at?: string | null;
  location?: string | null;
  seat_no?: string | null;
};

function getUpcomingExams(payload: Awaited<ReturnType<typeof api.getSchedule>>): ExamItem[] {
  const now = Date.now();
  return ((payload as { exams?: ExamItem[] }).exams ?? [])
    .filter((item) => {
      const endAt = new Date(item.exam_end_at || item.exam_start_at || "").getTime();
      return !Number.isNaN(endAt) && endAt >= now;
    })
    .sort((left, right) => {
      const leftTime = new Date(left.exam_start_at || "").getTime();
      const rightTime = new Date(right.exam_start_at || "").getTime();
      return leftTime - rightTime;
    });
}

export function PortalPage() {
  const [data, setData] = useState<PortalData | null>(null);
  const [upcomingExams, setUpcomingExams] = useState<ExamItem[]>([]);
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
      if (result.is_bound) {
        try {
          const schedule = await api.getSchedule();
          setUpcomingExams(getUpcomingExams(schedule));
        } catch {
          setUpcomingExams([]);
        }
      } else {
        setUpcomingExams([]);
      }
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
        <h2>首页</h2>
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
        <h2>未结束考试</h2>
        {loading ? (
          <p className="muted">正在加载...</p>
        ) : !data?.is_bound ? (
          <div className="empty-state">绑定教务账号后会显示考试安排。</div>
        ) : !upcomingExams.length ? (
          <div className="empty-state">暂无未结束考试。</div>
        ) : (
          <div className="grade-list">
            {upcomingExams.map((exam) => (
              <div key={exam.id} className="grade-card">
                <div>
                  <strong>{exam.course_name}</strong>
                  <p>{exam.exam_time_text || "时间未公布"}</p>
                  <small>
                    {[exam.location, exam.seat_no ? `座位 ${exam.seat_no}` : null].filter(Boolean).join(" · ") || "地点未公布"}
                  </small>
                </div>
              </div>
            ))}
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
