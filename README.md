# 小北寝室自动打卡 - Web 端基础框架

前后端分离的基础项目骨架，仅搭建可运行框架与示例模块，未实现具体业务逻辑。

## 目录结构

```
Web端/
├── frontend/                # 前端（Vue 3 + Vite + TailwindCSS）
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js       # 含 /api 代理到后端 5000
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.js          # 入口
│       ├── App.vue
│       ├── router/          # 路由（按页面划分）
│       ├── stores/          # 状态管理（Pinia，按业务域拆分）
│       ├── api/             # 接口层（axios 封装 + 模块接口）
│       ├── utils/           # 通用工具
│       ├── components/      # 公共组件
│       ├── views/           # 页面
│       ├── layouts/         # 布局模板
│       └── assets/          # 静态资源与全局样式
└── backend/                 # 后端（Python + Flask）
    ├── app.py               # 生产入口
    ├── run.py               # 本地开发启动
    ├── requirements.txt
    ├── config/__init__.py   # 配置层（按环境切换）
    └── app/
        ├── __init__.py      # 应用工厂
        ├── extensions.py    # 扩展挂载点
        ├── utils/           # 统一返回格式 response.py
        ├── routes/          # 蓝图（按业务模块划分）
        └── models/          # 数据模型（预留）
```

## 运行方式

### 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py                 # http://127.0.0.1:5000
```

> **部署约束（单实例）**：定时任务调度器随 Web 进程启动且 job 存于内存，全系统只允许一个进程运行调度器。
> 上线请使用 `gunicorn -w 1 --threads 8 "app:create_app()"` 或直接 `python run.py`；
> 多 worker 会各自注册同一批 cron 任务，导致同一账号重复打卡。未来横向扩容 Web 时，
> 先将 Web 进程置 `SCHEDULER_ENABLED=0`，由独立常驻进程接管调度。
> 调度相关环境变量（并发线程池 / 补跑宽限等）见 `backend/.env.example` 的「定时任务调度器」段。

### 数据库迁移

表结构以 `backend/migrations/` 迁移链为唯一事实源（Alembic / Flask-Migrate），应用启动时自动对齐：

- 空库 → 执行 `upgrade` 从 baseline 全量建表；
- 历史 `create_all` 建的既有库（无 `alembic_version` 表）→ 自动 `stamp head` 收编纳管，不改结构；
- 已纳管库 → 应用尚未执行的迁移。

日常改 models 后生成迁移（backend 目录下）：

```bash
export FLASK_APP=app.py
flask db migrate -m "说明变更内容"    # 对比 models 与数据库，生成迁移脚本
flask db upgrade                     # 应用到本地库（应用启动时也会自动执行）
```

### 自动签到（模块 E）：提交链路与启用流程

调度器到点执行时的完整链路：**找进行中任务（`know/list` / `sign/list`，提交只能用进行中任务的 id）→ 平台时间窗校验 → 定位 → 围栏拦截（可选）→ 认领图库图片 → 提交 → 落库推送**。

#### 行为约定

| 场景 | 结果 |
| --- | --- |
| 无进行中任务（如寒暑假） | 记 `skip`：「当前无进行中的签到任务」 |
| 当前时间不在平台任务时间窗内（任务 startTime~endTime） | 记 `skip` |
| 任务需要图片（`isPicture==0`）但配置套未启用图库或图库为空 | 记 `fail`，提示去配置 |
| 提交后平台返回 `msg=="302"` | 记 `fail`：触发风控行为验证码，需人工处理 |
| 提交时 token 失效 | 自动重登并整体重试一次 |
| 网络异常 | 指数退避重试 ≤3 次 |
| 成功判定 | `code==200 && msg=="操作成功"` 或 `code==6111`（旧版生产实证） |

- **定位来源**：位置池配置坐标 + `offset_m` 随机偏移（默认 10 米，模拟 GPS 抖动）；未配置位置时回退任务围栏中心 ±10 米；均无则提交空定位（与旧版一致）。
- **围栏拦截**（配置套「位置配置」区开关，默认开）：提交前校验所选位置是否落在任务围栏半径内，超出则本地拒绝并给出距离提示（B 平台已确认仅客户端校验距离、服务端不校验；开关用于防止异常位置暴露）。关闭后不校验照常提交。
- **图片约束**：JPEG、≤180KB、最长边 ≤1920px（`prepare_submit_image` 已自动满足）；有图提交为 `photo`+`file0` 同图双文件部分，无图为 JSON `photo:[]`。
- **活动签到（sign）提交接口为镜像推断**（仅任务 id 字段名与 know 不同），待真机抓包核准；失败原因会透传平台 `msg`。

#### 演练模式 `CHECKIN_DRYRUN`

环境变量安全开关（默认关）。在 `backend/.env` 加 `CHECKIN_DRYRUN=1` 后重启后端，签到链路照常完整执行（登录→找任务→定位→取图→构造提交），**但最后一步不发送请求**：日志打印本来要提交的内容，任务日志落一条 `skip` 记录（原因「演练：已构造提交未发送」）。用途：开学后首次验证时先空跑确认链路解析正确（任务 id / 定位 / 备注是否符合配置），确认后删掉该变量重启即进入真实提交模式。

#### 手动诊断脚本（推荐首次验证用它）

不等定时器，直接手动驱动一次完整链路（backend 目录下）：

```bash
# 只查看：登录 → 打印进行中任务 / 围栏 / 将要提交的字段（不提交）
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm

# 真实提交（无图）：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm --submit

# 真实提交（带图）：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm --submit --image 某图.jpg

# 活动签到（sign 镜像契约核准用）：
python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type activity --submit
```

可选参数：`--lat/--lng/--address/--remark` 覆盖提交字段。

#### 开学后首次启用 checklist

1. 保持 `CHECKIN_DRYRUN=1`（或先用诊断脚本只查模式）等辅导员下发任务；
2. 跑诊断脚本（不加 `--submit`）核对任务 id、围栏、提交字段是否符合预期；
3. 跑诊断脚本加 `--submit` 手动真实提交一次寝室签到，确认平台记录成功；
4. 同法跑一次 `--type activity --submit` 核准活动签到镜像契约（如有出入改 `real.py` 的 `_MODULES` 一处即可）；
5. 删除 `.env` 中的 `CHECKIN_DRYRUN`（或置 0）重启，进入自动模式；
6. 观察几天任务日志的 `fail_reason` 分布，确认无系统性失败。

### 前后端联通

开发环境下，前端通过 Vite 代理将 `/api` 请求转发到后端 `5000` 端口，无需额外处理跨域。
打开前端首页点击「调用示例接口」，即可看到来自后端 `/api/example` 的数据。

可直接验证后端接口：

```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/example
```

## 接口返回格式

前后端统一约定：

```json
{ "code": 0, "message": "success", "data": {} }
```

`code === 0` 表示成功，前端 axios 拦截器据此自动解包 `data`。

## 版本管理

- 仅本地管理，不推送远程仓库；初始分支 `main`。
- 版本号唯一来源为仓库根目录 `VERSION` 文件，开发阶段为 `0.x.x`，上线后为 `1.x.x`。
- 版本递增遵循 SemVer，**仅在你说「提交版本」（功能新增 / 开发结束）时触发**：
  - 功能新增 / 开发结束 → minor +1（`0.y.z` → `0.y+1.0`）
  - 上线 / 破坏性变更 → major +1（`0.y.z` → `1.0.0`）
  - 修复 BUG 不单独增加版本号，仅并入当前功能提交
- 每次「提交版本」流程：分析本次改动后，由助手给出 commit 文案草案与按规范递增的版本号（`VERSION` 与 `CHANGELOG.md` 一并更新），**由你手动执行 git 提交**；助手不代跑 git 指令。
- 递增版本：`python scripts/version_bump.py minor`（或 `major`）。
- 提交信息遵循 Conventional Commits，type 用英文、subject/body 用中文祈使句，风格务实不堆砌术语。
