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
│       ├── store/           # 状态管理（Pinia）
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
- 每次「提交版本」流程：我先 `git add` + 拟定 commit message 草案交你审核，你说「确认提交」才真正 `git commit`；`VERSION` 与 `CHANGELOG.md` 一并纳入。
- 递增版本：`python scripts/version_bump.py minor`（或 `major`）。
- 提交信息遵循 Conventional Commits，type 用英文、subject/body 用中文祈使句，风格务实不堆砌术语。
