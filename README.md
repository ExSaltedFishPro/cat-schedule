# C.A.T.课表

C.A.T. Team 的课表系统，设计之初的目标是：

代替周三课表，用于战队内部成员的课表和成绩查询，提供更快的访问速度和更友好的界面，同时支持成绩变动的自动邮件通知。现在选择开源出来，供有需要的同学（特别是iOS用户）参考和使用。

包含：

- FastAPI 后端 API@Port 8000
- PostgreSQL@Port 5432 数据库
- Redis + RQ 异步任务@Port 6379
- APScheduler 定时查分
- Typer CLI
- React + Vite 移动优先前端@Port 5173
- Resend 邮件提醒

教务系统访问全部由后端完成。前端只读缓存，不直接抓教务。

## 部署

可以将服务使用Nginx反向代理到80端口，并启用HTTPS。也可以直接暴露8000端口，配合Cloudflare等CDN使用。前端可以单独部署在Vercel等平台，或者和后端一起部署。

## 功能概览

- 邀请制注册，普通用户不能自行注册
- 长生命周期登录 Cookie
- 教务账号绑定，密码加密存储
- 复用 JSESSIONID，失效自动重登
- 课表缓存读取，手动异步刷新
- 成绩缓存读取，手动或定时异步检查
- 检测新成绩 / 待出分变已出分后邮件通知
- CLI 创建、查看、撤销邀请

## 技术栈

- 后端：FastAPI + SQLAlchemy 2 + Alembic
- 数据库：PostgreSQL
- 队列：Redis + RQ
- 定时任务：APScheduler
- 前端：React + Vite
- 抓取解析：requests + BeautifulSoup
- 密码哈希：PBKDF2-SHA256
- 敏感字段加密：Fernet

## 目录结构

```text
.
├─ backend/
│  ├─ alembic/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ db/
│  │  ├─ models/
│  │  ├─ portal/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ tasks/
│  │  ├─ cli.py
│  │  └─ main.py
│  ├─ tests/
│  └─ pyproject.toml
├─ web/
│  ├─ src/
│  └─ package.json
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## 配置

```bash
cp .env.example .env
```

关键变量：

```env
APP_SECRET_KEY=change-me-to-a-long-random-string
DATA_ENCRYPTION_KEY=your-fernet-key
RESEND_API_KEY=your-resend-api-key
PORTAL_CAPTCHA_SOLVER=auto
PORTAL_CAPTCHA_MAX_ATTEMPTS=3
```

说明：

- `APP_SECRET_KEY`：应用级 secret
- `DATA_ENCRYPTION_KEY`：用于加密教务密码和 Cookie，必须是合法 Fernet key
- `RESEND_API_KEY`：可留空；留空时不会真的发邮件，但查分逻辑仍会跑
- `PORTAL_CAPTCHA_SOLVER`：推荐 `auto`，会优先走 `ddddocr`，不可用时自动 fallback
- `PORTAL_CAPTCHA_MAX_ATTEMPTS`：验证码识别失败时的自动重试次数

生成 Fernet key：

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## Docker 启动

配置好 `.env` 后直接：

```bash
docker compose up --build
```

这会启动：

- `db`
- `redis`
- `migrate`
- `api`
- `worker`
- `scheduler`
- `web`

其中 `migrate` 会先单独执行一次 `alembic upgrade head`，完成后 `api / worker / scheduler` 再启动。

## CLI

CLI 入口：

- `backend/app/cli.py`

### 创建邀请

```bash
python3 cli.py create-invite --max-uses 1 --expires-in 7d --note "给朋友A"
```

### 查看邀请

```bash
python3 cli.py list-invites
```

### 撤销邀请

```bash
python3 cli.py revoke-invite <invite_id>
```

### 手动触发课表刷新

```bash
python3 cli.py enqueue-schedule-refresh --user-id <user_id>
```

### 手动触发成绩检查

```bash
python3 cli.py enqueue-grade-check --user-id <user_id>
```

## API

### 认证

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/invite/verify`
- `GET /api/auth/me`

### 教务账号

- `GET /api/account/portal`
- `POST /api/account/portal`

### 课表

- `GET /api/schedule`
- `POST /api/schedule/refresh`

### 成绩

- `GET /api/grades`
- `POST /api/grades/check-now`

### 设置

- `GET /api/settings`
- `POST /api/settings`

统一返回格式：

```json
{
  "ok": true,
  "code": "OK",
  "message": "ok",
  "data": {}
}
```

## 解析器说明

### 登录页

`backend/app/portal/parsers.py` 已实现：

- 登录表单提取
- 隐藏字段提取
- 验证码图片地址提取
- 登录页识别
- 登录错误信息提取

### 课表页

已实现双通道解析：

- 解析上方周课表格子，拿到周次、星期、大节块
- 解析下方明细表，补课程号、学分、地点和时间文本

### 成绩页

已解析：

- 学期
- 课程编号
- 课程名称
- 成绩
- 学分
- 总学时
- 考核方式
- 课程属性
- 课程性质

并基于稳定字段生成 `record_key` 做去重和变更检测。
