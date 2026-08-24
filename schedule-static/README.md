# Cat Schedule Static

把手动保存的教务处课表 HTML 转换成结构化 JSON 和一个可直接交给 Nginx 托管的 `index.html`。

这个工具是完全独立的离线 CLI，只处理课表。它不连接教务系统，不读取账号、密码或 Cookie，也不包含登录、数据库、成绩、考试、邮件和通知功能。生成的 HTML 已内嵌数据、样式和脚本，不会发起网络请求。

## 安装

需要 Python 3.9 或更新版本。

```bash
cd schedule-static
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

也可以在开发期间安装可编辑版本：

```bash
python3 -m pip install -e .
```

## 保存课表页面

1. 在浏览器中手动登录教务系统。
2. 打开课表页面并切换到需要导出的学期。
3. 等待课表完整显示。
4. 使用“网页，仅 HTML”保存页面。

首版支持 `.html`/`.htm` 内容，不支持“单个文件/MHTML（`.mhtml`）”。即使选择“网页，全部”，CLI 也只需要其中的主 HTML 文件，不会读取旁边的资源目录。

## 使用

先检查页面是否能正确识别：

```bash
cat-schedule-static inspect ~/Downloads/课表.html
```

生成单文件页面：

```bash
cat-schedule-static build ~/Downloads/课表.html \
  --output dist/index.html \
  --term-start 2026-09-07
```

`--term-start` 是第一周的周一；提供后，周选择器、星期标题和移动端日期按钮都会显示对应日期。默认页面标题保持为英文 `C.A.T. Schedule`。

同时保留结构化 JSON：

```bash
cat-schedule-static build ~/Downloads/课表.html \
  --output dist/index.html \
  --data-output dist/schedule.json \
  --term-start 2026-09-07
```

如果浏览器保存的 HTML 没有记录当前选中学期，可以显式指定：

```bash
cat-schedule-static build 课表.html -o index.html --term 2026-2027-1
```

其他选项：

- `--encoding gb18030`：页面乱码或编码检测错误时强制指定编码。
- `--title "我的课表"`：修改页面标题。
- `--force`：覆盖已经存在的输出文件。
- `--allow-empty`：确认没有课程时仍生成空页面。
- `--allow-incomplete`：把未识别周次的课程放入单独的“周次未识别”视图。

## Nginx

把生成的 `index.html` 复制到站点目录即可：

```bash
sudo mkdir -p /srv/cat-schedule
sudo cp dist/index.html /srv/cat-schedule/index.html
```

课表通常包含个人课程、教师和教室信息。若服务器可以从公网访问，建议额外使用 Basic Auth、VPN 或其他访问控制。

## 数据格式

结构化 JSON 使用 `schema_version: 1`，主要包含：

- 生成器版本和生成时间；
- 输入文件 SHA-256 与识别出的字符编码；
- 当前学期和可选的第一周日期；
- 规范化课程条目；
- 按周、星期组织的页面数据。


JSON 和 HTML 都不会保存原始教务处 HTML、隐藏表单字段、脚本或 Cookie。单个输入文件只包含当前页面实际展示的一个学期；教务页面下拉框里的其他学期不会被错误标记为已有课表。
