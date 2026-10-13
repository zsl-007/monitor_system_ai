# Monitor System AI — 智能服务器监控平台

## 项目简介

**Monitor System AI** 是一个基于 FastAPI 构建的服务器综合监控平台，旨在为运维团队提供一站式的服务器健康状态可视化、阈值报警与 AI 运维数据服务能力。

该项目解决以下核心问题：

- **多维度监控**：统一管理 CPU、内存、磁盘、网络、SSL 证书、API 接口、基础组件（Redis / RabbitMQ）七类监控项
- **自动化报警**：基于可配置阈值自动触发报警，通过邮件通知运维人员
- **AI 运维赋能**：为 AI Agent（如 Hermes）提供结构化的服务器运维数据 API，支持健康评分、趋势分析等智能运维场景
- **Web 管理界面**：提供配置管理、实时状态、报警记录、历史数据等可视化页面

---

## 功能特性

### 监控能力

| 监控类型 | 说明 | 监控器类 |
|---------|------|---------|
| CPU | CPU 使用率监控，支持阈值告警 | `SystemMonitor` |
| 内存 | 内存使用率监控，支持阈值告警 | `SystemMonitor` |
| 磁盘 | 磁盘分区使用率监控，支持多分区 | `SystemMonitor` |
| 网络 | 网络接口流量与状态监控 | `SystemMonitor` |
| SSL | SSL 证书有效期监控，提前预警过期 | `SSLMonitor` |
| API | HTTP/HTTPS 接口可用性与响应时间监控 | `APIMonitor` |
| 组件 | Redis、RabbitMQ 等基础组件连通性监控 | `ComponentMonitor` |

### 系统功能

- **任务调度**：基于 APScheduler 的异步定时任务调度，支持动态加载/更新监控配置，并发控制（最大同时执行 5 个任务）
- **阈值报警**：灵活的 JSON 格式阈值配置，支持多级告警（warning / critical），报警去重（5 分钟内相同报警不重复发送）
- **邮件通知**：SMTP 邮件报警通知，支持 HTML 邮件格式、多收件人、SSL 加密
- **JWT 认证**：基于 JWT Token 的用户认证体系，支持验证码登录、密码修改、Token 黑名单（登出）
- **数据导出**：支持报警数据和历史数据导出为 CSV 格式
- **AI 运维 API**：为 AI Agent 提供专用数据接口，含服务器概况、健康评分、趋势分析、组件状态等
- **License 授权**：基于机器码的授权验证机制，保障部署安全

---

## 技术栈

| 类别 | 技术 / 库 | 说明 |
|------|----------|------|
| Web 框架 | FastAPI 0.122 | 异步 Web 框架，提供 API 路由与页面渲染 |
| ASGI 服务器 | Uvicorn 0.38 | 高性能 ASGI 服务器 |
| 任务调度 | APScheduler 3.11 | 异步定时任务调度 |
| 数据库 | SQLite | 轻量级嵌入式数据库，连接池管理 |
| 数据验证 | Pydantic 2.12 | 请求/响应数据模型验证 |
| 模板引擎 | Jinja2 3.1 | HTML 页面模板渲染 |
| 认证 | PyJWT 2.10 | JWT Token 生成与验证 |
| 系统指标 | psutil 7.1 | CPU/内存/磁盘/网络等系统指标采集 |
| SSL | pyOpenSSL 25.3 | SSL 证书信息解析 |
| Redis | redis 7.0 | Redis 组件连通性检测 |
| RabbitMQ | pika 1.3 | RabbitMQ 组件连通性检测 |
| 日志 | loguru 0.7 | 统一日志管理 |
| 授权加密 | cryptography 46.0 / cryptocode | License 授权验证与加密 |
| 前端 | Bootstrap + Chart.js | 响应式 UI 与数据可视化图表 |

---

## 项目结构

```
monitor_system_ai/
├── main.py                 # FastAPI 主应用，Web 界面 + API 路由
├── run.py                  # 启动脚本，含 License 授权验证
├── __init__.py
├── requirements.txt        # Python 依赖清单
├── Dockerfile              # Docker 容器构建文件
├── modules/                # 核心功能模块
│   ├── config.py           # 配置管理器（监控配置、邮箱配置、项目名称）
│   ├── database.py         # 数据库连接管理与表结构初始化
│   ├── scheduler.py        # 任务调度器（APScheduler 异步调度）
│   ├── alert.py            # 报警管理器（阈值判断、邮件发送、报警去重）
│   ├── auth.py             # 认证管理器（JWT、验证码、密码哈希）
│   ├── logger.py           # 统一日志配置（loguru）
│   ├── license.py          # License 授权验证（机器码 + RSA）
│   └── installdb.py        # 数据库安装辅助工具
├── monitors/               # 监控器实现
│   ├── base.py             # 监控器抽象基类 BaseMonitor
│   ├── system.py           # 系统资源监控（CPU/内存/磁盘/网络）
│   ├── ssl.py              # SSL 证书监控
│   ├── api.py              # API 接口监控
│   └── component.py        # 组件监控（Redis/RabbitMQ）
├── routers/                # 路由模块
│   └── ops.py              # AI 运维 API 路由
├── ops/                    # AI 运维服务
│   ├── service.py          # 运维数据服务（为 AI Agent 提供结构化数据）
│   ├── health.py           # 服务器健康评分计算
│   ├── formatter.py        # 数据格式化工具
│   └── ops_auth.py         # AI 运维 API Token 认证
├── templates/              # Jinja2 HTML 模板
│   ├── base.html           # 基础模板（导航栏、布局）
│   ├── login.html          # 登录页面
│   ├── config.html         # 监控配置管理页面
│   ├── status.html         # 实时状态页面
│   ├── alerts.html         # 报警记录页面
│   └── history.html        # 历史数据页面
├── static/                 # 静态资源
│   ├── css/                # 样式文件（Bootstrap、自定义样式）
│   └── js/                 # 脚本文件（Bootstrap、Chart.js、业务逻辑）
└── utils/                  # 工具脚本
    ├── generate_secret.py  # 密钥生成工具
    └── ResetPassword.py    # 密码重置工具
```

---

## 安装与部署

### 方式一：本地运行

**环境要求**：Python 3.9+

```bash
# 1. 克隆仓库
git clone https://github.com/zsl-007/monitor_system_ai.git
cd monitor_system_ai

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python run.py
```

服务默认启动在 `http://0.0.0.0:18770`。

> **注意**：首次启动需要有效的 License 授权文件。将授权文件放置在 `modules/` 目录下（与 `license.py` 同级），或通过 `utils/generate_secret.py` 生成机器码后联系授权方获取授权文件。

### 方式二：Docker 部署

```bash
# 1. 构建镜像
docker build -t monitor-system-ai .

# 2. 运行容器
docker run -d \
  --name monitor-system \
  -p 18771:18771 \
  -v $(pwd)/data:/monitor_system/monitor_system/data \
  -v $(pwd)/license:/monitor_system/monitor_system/license \
  monitor-system-ai
```

Docker 容器内服务运行在端口 `18771`，可通过 `-p` 参数映射到宿主机端口。

### 首次使用

1. **初始化数据库**：首次启动时系统自动创建 SQLite 数据库（`data/monitor_system.db`）及所有表结构
2. **登录系统**：使用默认管理员账号登录（可通过 `utils/ResetPassword.py` 重置密码）
3. **配置监控项**：在配置页面添加需要监控的项目（CPU、磁盘、API 等）
4. **配置邮箱**：设置 SMTP 邮箱信息，用于接收报警通知

---

## 使用说明

### Web 界面

| 页面 | 路径 | 说明 |
|------|------|------|
| 登录 | `/login` | 用户登录页面，支持验证码 |
| 实时状态 | `/status` | 各监控项最新状态、运行中任务、当日报警统计 |
| 配置管理 | `/config` | 监控项的增删改查、邮箱配置、项目名称设置 |
| 报警记录 | `/alerts` | 报警历史记录，支持日期筛选、分页、CSV 导出 |
| 历史数据 | `/history` | 监控数据历史记录，支持图表展示、筛选、分页、CSV 导出 |

### 监控配置

在配置页面可创建以下类型的监控项：

- **CPU 监控**：设置 CPU 使用率阈值（如 warning: 80%, critical: 90%）
- **内存监控**：设置内存使用率阈值
- **磁盘监控**：选择磁盘分区，设置使用率阈值
- **网络监控**：选择网络接口，监控流量状态
- **SSL 监控**：输入域名，设置证书过期预警天数
- **API 监控**：输入 API URL，设置响应时间阈值和状态码期望
- **组件监控**：选择组件类型（Redis/RabbitMQ），输入连接地址

每个监控项可独立配置：
- **监测间隔**：单位为秒，默认 60 秒
- **启用/禁用**：可随时切换监控状态
- **阈值配置**：JSON 格式的多级阈值
- **额外配置**：JSON 格式的扩展参数

---

## 配置说明

### 数据库配置

- **数据库类型**：SQLite
- **数据库路径**：`data/monitor_system.db`（自动创建）
- **连接池**：最大连接数 5，线程本地存储隔离

### 数据库表结构

| 表名 | 说明 |
|------|------|
| `monitor_configs` | 监控配置表（名称、类型、目标、阈值、间隔等） |
| `monitor_data` | 监控数据记录表（监控值、状态、是否正常、详情） |
| `alert_data` | 报警记录表（报警信息、时间、是否已发送、接收人） |
| `email_config` | 邮箱配置表（SMTP 服务器、端口、账号、收件人） |
| `system_config` | 系统配置表（键值对存储，如项目名称） |
| `users` | 用户表（用户名、密码哈希、激活状态） |
| `token_blacklist` | JWT Token 黑名单表（用于登出失效） |

### 邮箱配置

通过 Web 界面的配置页面设置，或调用 `PUT /api/email-config` 接口：

```json
{
  "smtp_server": "smtp.example.com",
  "smtp_port": 465,
  "username": "user@example.com",
  "password": "password",
  "sender": "monitor@example.com",
  "receivers": ["admin1@example.com", "admin2@example.com"],
  "ssl_enabled": true
}
```

### AI 运维 API 认证

通过环境变量 `OPS_API_TOKEN` 设置 AI 运维 API 的访问 Token。客户端请求时需在 Header 中携带 `X-Ops-Token`。未设置环境变量时，开发环境允许无 Token 访问。

### License 授权

- 授权文件放置在 `modules/` 目录下（`private_key.pem` 和授权文件）
- 使用 `utils/generate_secret.py` 生成机器码
- 授权验证基于 RSA 非对称加密和机器码绑定

---

## 架构说明

### 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Web 浏览器                        │
│    (登录 / 状态 / 配置 / 报警 / 历史)                 │
└────────────────────┬────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────┐
│              FastAPI 主应用 (main.py)                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ 页面路由  │  │ API 路由  │  │ AI 运维 API 路由  │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       │              │                  │             │
│  ┌────▼──────────────▼──────────────────▼──────────┐ │
│  │              认证中间件 (JWT)                     │ │
│  └────────────────────────────────────────────────-┘ │
└────────────────────┬────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐  ┌──────▼──────┐  ┌────▼────────┐
│ Config  │  │  Scheduler  │  │  AlertMgr   │
│ Manager │  │ (APScheduler)│  │ (阈值+邮件)  │
└────┬────┘  └──────┬──────┘  └────┬────────┘
     │               │               │
     │         ┌─────▼─────┐         │
     │         │  Monitors  │         │
     │         │ (7类监控器) │         │
     │         └─────┬─────┘         │
     │               │               │
     └───────────────▼───────────────┘
                ┌─────────┐
                │ SQLite  │
                │  DB     │
                └─────────┘
```

### 核心模块协作流程

1. **启动流程**：`run.py` → License 验证 → Uvicorn 启动 `main.py` → 数据库初始化 → TaskScheduler 启动 → 加载监控配置并创建定时任务

2. **监控执行流程**：TaskScheduler 按 `interval_seconds` 定时触发 → 选择对应 Monitor（如 `SystemMonitor`）→ 执行 `_check_impl()` 采集数据 → 结果写入 `monitor_data` 表 → AlertManager 检查阈值 → 触发报警则写入 `alert_data` 表并发送邮件

3. **配置变更流程**：用户通过 Web/API 修改配置 → ConfigManager 更新数据库 → 通知 TaskScheduler 重新加载任务 → 调度器动态更新定时任务

4. **AI 运维流程**：AI Agent 调用 `/api/ops/*` 接口 → Token 认证 → OpsService 从数据库聚合数据 → formatter 格式化 → health.py 计算健康评分 → 返回结构化 JSON

### 监控器继承体系

```
BaseMonitor (ABC)
├── SystemMonitor    # CPU / 内存 / 磁盘 / 网络
├── SSLMonitor       # SSL 证书有效期
├── APIMonitor       # HTTP API 可用性
└── ComponentMonitor # Redis / RabbitMQ
```

所有监控器继承 `BaseMonitor`，实现 `_check_impl()` 方法。基类提供统一的 `check()` 入口，自动记录执行时间和异常处理。

---

## API 接口说明

### 认证相关 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 用户登录（用户名 + 密码 + 验证码），返回 JWT Token |
| POST | `/api/logout` | 用户登出，清除 Token Cookie |
| POST | `/api/change-password` | 修改当前用户密码 |
| POST | `/api/captcha` | 获取登录验证码图片 |

### 监控配置 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/monitor-configs/{config_id}` | 获取单个监控配置详情 |
| POST | `/api/monitor-configs` | 创建监控配置 |
| PUT | `/api/monitor-configs/{config_id}` | 更新监控配置 |
| DELETE | `/api/monitor-configs/{config_id}` | 删除监控配置 |
| POST | `/api/monitor-configs/{config_id}/toggle` | 启用/禁用监控配置 |

### 监控数据 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/real-time-status` | 获取所有监控项最新状态（用于 AJAX 实时刷新） |
| POST | `/api/trigger-check/{config_id}` | 立即触发指定监控项的检查 |
| GET | `/api/disk-partitions` | 获取磁盘分区列表 |
| GET | `/api/network-interfaces` | 获取网络接口列表 |

### 报警数据 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 获取报警数据（支持日期范围、分页） |
| GET | `/api/export-alerts` | 导出报警数据为 CSV 文件 |

### 历史数据 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/export-history` | 导出历史监控数据为 CSV 文件 |

### 邮箱配置 API

| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | `/api/email-config` | 更新邮箱 SMTP 配置 |
| POST | `/api/test-email` | 发送测试邮件验证邮箱配置 |

### 系统管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/database-health` | 获取数据库健康状态 |
| POST | `/api/initialize-database` | 手动重新初始化数据库 |
| GET | `/api/project-name` | 获取项目名称 |
| PUT | `/api/project-name` | 更新项目名称 |

### AI 运维 API（`/api/ops/*`）

> 需在请求 Header 中携带 `X-Ops-Token` 进行认证（环境变量 `OPS_API_TOKEN` 未设置时开发环境免认证）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ops/overview` | 获取服务器整体概况（基本信息 + 健康评分 + 资源/组件/SSL/API 汇总） |
| GET | `/api/ops/status` | 获取服务器当前详细状态 |
| GET | `/api/ops/components` | 获取所有组件状态 |
| GET | `/api/ops/components/{name}` | 获取指定组件状态 |
| GET | `/api/ops/ssl?days=30` | 获取即将过期的 SSL 证书（可指定预警天数） |
| GET | `/api/ops/apis?status=all` | 获取 API 监控状态（可按 normal/warning/critical 筛选） |
| GET | `/api/ops/alerts?hours=24&level=all&limit=50` | 获取最近报警记录 |
| GET | `/api/ops/history?config_id=&hours=24&limit=500` | 获取历史监控数据 |
| GET | `/api/ops/trend?metric=cpu&hours=24&interval=1h` | 获取指标趋势数据（支持 cpu/memory/disk/network） |
| GET | `/api/ops/configs` | 获取所有监控配置 |
| GET | `/api/ops/scheduler` | 获取调度器运行状态 |
| POST | `/api/ops/check/{config_id}` | 触发指定监控项立即检查 |

#### AI 运维 API 使用示例

```bash
# 获取服务器概况
curl -H "X-Ops-Token: your-token" http://localhost:18770/api/ops/overview

# 获取 CPU 趋势数据（最近 24 小时，1 小时间隔）
curl -H "X-Ops-Token: your-token" \
  "http://localhost:18770/api/ops/trend?metric=cpu&hours=24&interval=1h"

# 触发立即检查
curl -X POST -H "X-Ops-Token: your-token" \
  http://localhost:18770/api/ops/check/1
```

---

## 工具脚本

| 脚本 | 说明 |
|------|------|
| `utils/generate_secret.py` | 生成机器码，用于 License 授权申请 |
| `utils/ResetPassword.py` | 重置管理员密码 |

---

## 开发说明

### 日志系统

项目使用 loguru 统一管理日志，所有模块通过 `from modules.logger import logger` 引入。日志配置在 `modules/logger.py` 中统一定义。

### 数据库操作

通过 `modules/database.py` 提供的统一接口操作数据库：

- `execute_query(sql, params)` — 查询多行
- `execute_single(sql, params)` — 查询单行
- `execute_update(sql, params)` — 更新操作
- `execute_insert(sql, params)` — 插入操作
- `initialize_database()` — 初始化数据库
- `check_database_health()` — 检查数据库健康状态

DatabaseManager 采用单例模式，线程本地存储隔离连接，支持连接池复用。

### 添加自定义监控器

1. 在 `monitors/` 目录下创建新文件，继承 `BaseMonitor`
2. 实现 `_check_impl()` 方法，返回包含 `is_normal`、`message`、`value` 等字段的字典
3. 在 `modules/scheduler.py` 的 `TaskScheduler.__init__` 中注册新监控器
4. 在 `modules/config.py` 的监控类型列表中添加新类型

---

## 版本信息

- 当前版本：v1.1.1
- Python 版本：3.9+
- 默认端口：18770（本地运行）/ 18771（Docker）

## License

本项目采用基于机器码的授权验证机制，需获取授权文件后方可运行。详见 `modules/license.py`。
