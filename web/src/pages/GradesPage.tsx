import { useEffect, useState } from "react";
import { ApiError, api, GradesPayload } from "../lib/api";
import { readCache, removeCache, writeCache } from "../lib/localCache";

const GRADES_CACHE_KEY = "cat-schedule:grades:current";
const GRADES_CACHE_TTL_MS = 30 * 60 * 1000;

export function GradesPage() {
  const [data, setData] = useState<GradesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");

    const cacheEntry = readCache<GradesPayload>(GRADES_CACHE_KEY, GRADES_CACHE_TTL_MS);
    if (cacheEntry) {
      setData(cacheEntry.data);
      setLoading(false);
      if (!cacheEntry.stale) {
        return;
      }
    } else {
      setLoading(true);
    }

    try {
      const result = await api.getGrades();
      setData(result);
      writeCache(GRADES_CACHE_KEY, result);
    } catch (err) {
      if (!cacheEntry) {
        setError(err instanceof ApiError ? err.message : "成绩加载失败");
      } else {
        setError(err instanceof ApiError ? `${err.message}，先展示本地缓存。` : "网络异常，先展示本地缓存。");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCheck() {
    setChecking(true);
    setMessage("");
    setError("");
    try {
      await api.checkGrades();
      removeCache(GRADES_CACHE_KEY);
      setMessage("已提交成绩检查。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "提交检查失败");
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="page">
      <div className="panel">
        <div className="panel-row">
          <div>
            <h2>成绩</h2>
            <p className="muted">最近检查：{data?.last_checked_at ? new Date(data.last_checked_at).toLocaleString() : "暂无"}</p>
            <p className="muted">通知邮箱：{data?.notification_email ?? "未设置"}</p>
          </div>
          <button className="button primary compact" onClick={handleCheck} disabled={checking}>
            {checking ? "提交中..." : "立即检查"}
          </button>
        </div>
        {message ? <div className="message success">{message}</div> : null}
        {error ? <div className="message error">{error}</div> : null}
      </div>

      <div className="panel">
        {loading ? (
          <p className="muted">正在加载成绩...</p>
        ) : !data?.terms.length ? (
          <p className="muted">还没有成绩，先手动检查一次吧。</p>
        ) : (
          <div className="term-stack">
            {data.terms.map((term) => (
              <section key={term.term} className="term-card">
                <div className="panel-row">
                  <h3>{term.term}</h3>
                  <span className="badge">{term.items.length} 门</span>
                </div>
                <div className="grade-list">
                  {term.items.map((item) => (
                    <div key={item.id} className="grade-card">
                      <div>
                        <strong>{item.course_name}</strong>
                        <p>{item.course_code || "无课程号"}</p>
                      </div>
                      <div className="grade-score">{item.score || "待出分"}</div>
                      <small>
                        学分 {item.credit || "-"} · {item.assessment_method || "未识别"} · {item.course_attribute || "-"}
                      </small>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
