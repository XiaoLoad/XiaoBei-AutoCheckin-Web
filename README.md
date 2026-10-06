<div align="center">

[![小北自动打卡](frontend/public/favicon-256x256.png)](frontend/public/favicon-256x256.png)

**寝室 / 活动签到，交给后台自动跑。**

前后端分离的自动签到管理平台：后端 Flask 编排小北学生平台签到链路与课表驱动调度，前端 Vue 3 提供管理员 / 普通用户双视角控制台。

[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](backend/requirements.txt)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask&logoColor=white)](backend/requirements.txt)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)](frontend/package.json)
[![Tests](https://img.shields.io/badge/tests-399%20passed-brightgreen)](backend/tests)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[功能特性](#功能特性) · [快速开始](#快速开始) · [配置](#配置) · [生产部署](#生产部署) · [使用指南](#使用指南) · [常见问题](#常见问题)

</div>

> 当前功能针对强智教务系统与本校小北学生平台接口实测开发；教务对接部分适配本校地址，其他学校的平台如接口一致亦可复用。

## 功能特性

* **双视角控制台** —— 管理员（用户 / 账号 / 定时任务 / 配置套 / 全站签到记录巡检 / 仪表盘 / 系统设置）与普通用户（我的资源 / 任务配置 / 签到记录 / 仪表盘）按角色分发。
* **自动签到链路** —— 找进行中任务 → 平台时间窗校验 → 定位（位置池坐标 + 随机偏移 / 围栏中心回退）→ 围栏拦截 → 认领图库图片 → 提交小北学生平台 → 落库推送；含演练开关与诊断脚本。
* **课表驱动调度** —— 对接教务系统，按课表展开当日时间窗低频轮询；跨时段课程自动拆分窗口，避免午休后发布的签到漏签。
* **资源池体系** —— 位置池（高德地图拾取）、图库、凭证池（Server 酱 / PushPlus / 邮箱）、UA 模板。
* **配置套** —— 寝室 / 活动类型化配置快照，支持批量套用与漂移检测；任务实例自持配置。
* **多通道推送** —— 邮件 / Server 酱 / PushPlus / QQ 群摘要；凭证可按配置套共享或按账号自带，落库推送结果。
* **调度可靠性** —— 连接池对齐并发、网络重试与窗口内补跑、启动漏跑对账；单实例部署约束。
* **多主题与响应式** —— 六套主题色 + GSAP 色彩补间；桌面端应用框式布局，移动端文档流自然滚动。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.13 · Flask 3 · Flask-SQLAlchemy · Flask-Migrate (Alembic) · PyJWT · APScheduler · bcrypt · Pillow |
| 前端 | Vue 3 · Vite · TailwindCSS · Pinia · Vue Router · ECharts · GSAP · axios |
| 数据库 | MySQL 8 |
| 部署 | gunicorn（单实例）· systemd / docker 均可 |

## 快速开始

### 环境要求

- Python 3.13（开发实测版本）
- Node.js ≥ 18
- MySQL 8，且已创建数据库：

```sql
CREATE DATABASE xiaobei_auto DEFAULT CHARACTER SET utf8mb4;
```

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env

# 开发库初始化：建表 + 种子账号（admin / user01，随机密码仅终端打印一次）
python scripts/init_db.py

python run.py                    # http://127.0.0.1:5000
```

表结构以 `backend/migrations/` 迁移链为唯一事实源，应用启动时自动对齐：

- 空库 → 从 baseline 全量建表；
- 历史方式建的既有库（无 `alembic_version` 表）→ 自动 stamp 收编纳管，不改结构；
- 已纳管库 → 应用尚未执行的迁移。

日常改 models 后生成迁移（backend 目录下）：

```bash
export FLASK_APP=app.py
flask db migrate -m "说明变更内容"    # 对比 models 与数据库，生成迁移脚本
flask db upgrade                     # 应用到本地库（应用启动时也会自动执行）
```

### 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173，/api 由 Vite 代理转发到后端 5000
```

开发环境无需处理跨域；可直接验证后端接口：

```bash
curl http://127.0.0.1:5000/api/health
```

## 配置

后端环境变量通过 `backend/.env` 加载（复制 `.env.example` 修改；该文件已 gitignore）。systemd / docker 注入的环境变量优先于 `.env`。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FLASK_ENV` | `development` | 运行环境；生产入口缺省以 `production` 启动 |
| `SECRET_KEY` / `JWT_SECRET_KEY` | 开发默认值 | 生产环境仍为开发默认值时**拒绝启动**（安全守护） |
| `JWT_EXPIRES_HOURS` | `12` | 登录凭证有效期（小时） |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的跨域来源列表；生产环境含 `*` 拒绝启动 |
| `SQLALCHEMY_DATABASE_URI` | 开发默认库 | 连接串格式 `mysql+pymysql://<user>:<password>@<host>:3306/<dbname>?charset=utf8mb4` |
| `SCHEDULER_ENABLED` | `1` | 调度器开关；横向扩容 Web 时 Web 进程置 `0` |
| `SCHEDULER_MAX_WORKERS` | `30` | 签到并发线程池大小，按峰值任务量调大 |
| `SCHEDULER_MISFIRE_GRACE` | `600` | 错过触发时刻的补跑宽限秒数 |
| `SCHEDULER_RECONCILE_SAME_DAY` | `1` | 启动对账仅补跑计划时刻在当天的错过任务 |
| `SCHEDULER_TZ` | `Asia/Shanghai` | 调度时区 |
| `CHECKIN_DRYRUN` | 未设置 | 置 `1` 进入演练模式（见下文） |
| `PUSH_VERIFY_SSL` | `1` | 推送通道 TLS 校验；仅部署机信任库确有缺陷时置 `0` |
| `BP_VERIFY_SSL` | `0` | 小北学生平台 TLS 校验；校园服务器证书已失效，保持关闭 |
| `UPLOAD_DIR` | `backend/uploads` | 图库上传目录 |

## 生产部署

```bash
gunicorn -w 1 --threads 8 "app:create_app()"    # 或 python app.py
```

> **单实例约束（重要）**：定时任务调度器随 Web 进程启动且任务存于内存，全系统只允许一个进程运行调度器。
> 多 worker 会各自注册同一批 cron 任务，导致同一账号重复打卡。未来横向扩容 Web 时，
> 先将 Web 进程置 `SCHEDULER_ENABLED=0`，由独立常驻进程接管调度。

生产环境安全守护：`SECRET_KEY` / `JWT_SECRET_KEY` 仍为开发默认值、`CORS_ORIGINS` 含 `*`、数据库连接串为开发默认值时，应用启动即拒绝，避免带弱配置上线。

**首次启动引导**：全新部署首次启动时（系统中无任何账号），应用自动创建管理员 `admin` 并生成随机密码，仅在启动日志（stderr 与 `backend/logs/app.log`）打印一次——请立即登录并修改密码。错过打印时，删除该账号记录后重启可重新引导，或使用 `scripts/create_admin.py` 手动创建。

### Docker Compose 部署

三个服务（nginx 前端 / backend 后端 / mysql 数据库）一键拉起，适合换机迁移：

```bash
git clone https://github.com/XiaoLoad/XiaoBei-AutoCheckin-Web.git
cd XiaoBei-AutoCheckin-Web
cp backend/.env.example backend/.env    # 按文件内 [Compose 必改] 注释逐项修改
docker compose up -d --build
docker compose logs backend | grep 首次启动引导    # 取 admin 初始密码（仅打印一次）
```

要点（均已内置于 compose 文件注释）：

- **单实例铁律**：backend 服务 `replicas` 恒为 1，`gunicorn -w 1` 写死在镜像内——多实例会重复打卡；
- **持久化卷**：`mysql-data`（数据库）、`app-uploads`（图库文件，在磁盘不在库里）、`app-logs`；重建容器不丢数据；
- **健康检查与启动顺序**：MySQL 通过 healthcheck 后 backend 才启动（启动时自动执行数据库迁移）；
- **时区**：三个容器均注入 `TZ=Asia/Shanghai`；
- **`.env` 关键项**：`FLASK_ENV=production`、随机 `SECRET_KEY` / `JWT_SECRET_KEY`、连接串 host 写服务名 `mysql`、`CORS_ORIGINS` 为对外地址；
- **HTTPS**：nginx 容器默认只监听 80，生产建议自行追加 443 监听与证书挂载，或在前置宿主机代理上终结 TLS。

日常更新与回滚：

```bash
git fetch --tags && git checkout v1.0.2   # 建议按 tag 更新，不用 main
docker compose up -d --build              # 更新前建议先 mysqldump 备份
```

## 使用指南

### 自动签到链路

调度器到点执行时的完整链路：**找进行中任务（`know/list` / `sign/list`，提交只能用进行中任务的 id）→ 平台时间窗校验 → 定位 → 围栏拦截（可选）→ 认领图库图片 → 提交 → 落库推送**。

| 场景 | 结果 |
| --- | --- |
| 无进行中任务（如寒暑假） | 记 `skip`：「当前无进行中的签到任务」 |
| 当前时间不在平台任务时间窗内 | 记 `skip` |
| 任务需要图片但配置套未启用图库或图库为空 | 记 `fail`，提示去配置 |
| 提交后平台返回 `msg=="302"` | 记 `fail`：触发风控行为验证码，需人工处理 |
| 提交时 token 失效 | 自动重登并整体重试一次 |
| 网络异常 | 指数退避重试 ≤3 次 |
| 成功判定 | `code==200 && msg=="操作成功"` 或 `code==6111` |

- **定位来源**：位置池配置坐标 + `offset_m` 随机偏移（默认 10 米，模拟 GPS 抖动）；未配置位置时回退任务围栏中心 ±10 米；均无则提交空定位。
- **围栏拦截**（默认开）：提交前校验所选位置是否落在任务围栏半径内，超出则本地拒绝并给出距离提示；关闭后不校验照常提交。
- **图片约束**：JPEG、≤180KB、最长边 ≤1920px（上传时自动归一化）；有图提交为双文件部分，无图为 JSON 空数组。

### 演练模式 `CHECKIN_DRYRUN`

在 `backend/.env` 加 `CHECKIN_DRYRUN=1` 后重启后端，签到链路照常完整执行（登录 → 找任务 → 定位 → 取图 → 构造提交），**但最后一步不发送请求**：日志打印本来要提交的内容，任务日志落一条 `skip` 记录。

用途：开学后首次验证时先空跑确认链路解析正确（任务 id / 定位 / 备注是否符合配置），确认后删除该变量重启即进入真实提交模式。

### 手动诊断脚本

不等定时器，直接手动驱动一次完整链路（backend 目录下）：

```bash
# 只查看：登录 → 打印进行中任务 / 围栏 / 将要提交的字段（不提交）
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm

# 真实提交（无图）：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm --submit

# 真实提交（带图）：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm --submit --image 某图.jpg

# 活动签到：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type activity --submit
```

可选参数：`--lat/--lng/--address/--remark` 覆盖提交字段。

### 开学后首次启用 checklist

1. 保持 `CHECKIN_DRYRUN=1`（或先用诊断脚本只查模式）等辅导员下发任务；
2. 跑诊断脚本（不加 `--submit`）核对任务 id、围栏、提交字段是否符合预期；
3. 跑诊断脚本加 `--submit` 手动真实提交一次寝室签到，确认平台记录成功；
4. 同法跑一次 `--type activity --submit` 核准活动签到契约；
5. 删除 `.env` 中的 `CHECKIN_DRYRUN`（或置 0）重启，进入自动模式；
6. 观察几天任务日志的 `fail_reason` 分布，确认无系统性失败。

### 活动签到课表驱动调度

活动签到除固定时刻单次查询外，支持按教务课表展开的当日时间窗内低频轮询：有课日子在课程前后自动开窗查活动并签到，无课日零查询（寝室签到链路不受影响）。

- **教务对接**（`backend/app/services/jwxt/`，本校强智系统实测口径）：解析课表页与教学周历，多账号串行同步队列（间隔随机 3-8s、连续 3 次失败隔离降级）；登录仅用 encoded 字段、默认当前学期；读取超时 20s 且网络类失败重试一次。
- **时段制窗口**：作息表按相邻间隔 ≥60min 切上午 / 下午 / 晚上，当天有课的每个时段生成覆盖整段窗口，各时段独立「命中即完成」；默认提前量 60 分钟。跨时段课程（如 1-8 节）拆分为多个独立窗口。
- **调度**：每日 00:10 展开当日窗口，30s 心跳内窗口轮询；绑定 / 换绑 / 批量启用对 course 策略做教务绑定前置校验（先验证后落库）。
- **课表抽屉**：账号任务 → 活动签到 →「按课表自动」，提供周课表视图、周次导航、块级排除与当日窗口预览。

## 接口约定

前后端统一响应格式，`code === 0` 表示成功，前端 axios 拦截器据此自动解包 `data`：

```json
{ "code": 0, "message": "success", "data": {} }
```

## 目录结构

```
Web端/
├── frontend/                # 前端（Vue 3 + Vite + TailwindCSS）
│   └── src/
│       ├── router/          # 路由（按页面划分）
│       ├── stores/          # 状态管理（Pinia，按业务域拆分）
│       ├── api/             # 接口层（axios 封装 + 模块接口）
│       ├── components/      # 公共组件
│       ├── views/           # 页面
│       └── layouts/         # 布局模板
├── backend/
│   ├── app.py               # 生产入口（gunicorn / python app.py）
│   ├── run.py               # 本地开发启动
│   ├── requirements.txt
│   ├── .env.example         # 环境变量示例
│   ├── migrations/          # 表结构迁移链（唯一事实源）
│   ├── scripts/             # init_db / create_admin / diag_bp_checkin 等工具脚本
│   ├── tests/               # 后端测试（pytest）
│   ├── config/              # 配置层（按环境切换）
│   └── app/
│       ├── __init__.py      # 应用工厂
│       ├── routes/          # 蓝图（按业务模块划分）
│       ├── services/        # 业务服务（调度、签到链路、教务对接、推送…）
│       ├── models/          # 数据模型
│       └── utils/           # 统一返回格式、鉴权、校验器
├── scripts/                 # version_bump 等仓库级脚本
├── CHANGELOG.md
└── VERSION
```

## 测试

```bash
cd backend
.venv/Scripts/python -m pytest -q        # Windows；Linux/macOS: python -m pytest -q
```

当前 399 条用例全部通过，覆盖签到链路、调度、教务解析、推送、权限与安全守护等模块。

## 常见问题

**全新生产库如何创建第一个管理员？**
无需手动操作：首次启动时应用检测到系统中无任何账号，会自动创建管理员 `admin` 并把随机密码打印到启动日志（仅一次），登录后请立即修改密码。

错过日志的恢复方式（二选一）：

```bash
# ① 删除 users 表中该账号记录后重启应用，重新触发引导
# ② 手动创建（系统中已有任何账号时脚本会拒绝执行）：
cd backend
python scripts/create_admin.py admin
```

`scripts/init_db.py` 仅用于开发库初始化（生产环境或非开发默认库一律拒绝执行），种子密码随机生成且仅终端打印一次。

**为什么小北学生平台默认关闭 TLS 校验？**
小北学生平台为校园服务器，证书链已失效，开启校验即无法通信（`BP_VERIFY_SSL=0` 为默认）；推送通道为公共服务，默认开启校验（`PUSH_VERIFY_SSL=1`）。

**多实例 / 横向扩容？**
当前架构为单实例设计（调度器内存态）。扩容方案见「生产部署」一节：Web 进程多副本 + `SCHEDULER_ENABLED=0`，由独立常驻进程接管调度。

## 版本与变更

版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)，见根目录 `VERSION` 文件与 [CHANGELOG.md](CHANGELOG.md)；提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)。

## 免责声明

在使用本项目前，请仔细阅读并理解以下内容。**下载、安装或使用本项目的任一行为，即视为您已阅读并同意本声明的全部内容。**

1. **仅供学习与技术研究**。本项目仅用于个人学习前后端开发、自动化调度等技术的目的，不得用于任何商业用途或规模化运营。

2. **第三方接口来源**。本项目对接的小北学生平台与本校教务系统接口，系开发者基于本人合法账号通过抓包分析获得，**未获得任何校方或平台方的官方授权**。教务对接部分适配的是本校教务系统地址，不适用于其他学校。相关接口随时可能变更或关闭，项目不保证持续可用；若平台方提出异议，本项目将及时停止维护并移除相关内容。

3. **自动化签到的使用风险由您自担**。自动签到功能可能违反您所在学校或平台的服务条款，由此产生的一切后果（包括但不限于账号处罚、纪律处分、数据异常等）均由使用者本人承担，与本项目开发者无关。请在使用前自行确认学校与平台的相关规定。

4. **凭据安全**。本项目需要在本地数据库存储您的平台账号密码用于自动登录。虽然项目采取了加密存储、传输脱敏等措施，但请自行评估并妥善保管凭据，建议使用独立的专用密码。开发者不对因使用不当、密钥泄露、部署缺陷等导致的任何损失负责。

5. **按现状提供**。本项目不提供任何明示或默示的担保，包括但不限于适销性、特定用途适用性与不侵权的担保。在适用法律允许的最大范围内，开发者不对任何索赔、损害或其他责任承担责任。

6. **最小影响原则**。请合理使用本项目，勿对平台服务器造成额外负载；本项目定位为个人辅助工具，请勿用于替他人批量签到等场景。

## License

MIT
