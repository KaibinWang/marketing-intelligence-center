# 营销情报中心

自动化采集上市公司公告、政府采购中标信息、投融资快讯，通过 DeepSeek AI 提取结构化情报，经地域过滤后推送至企业微信，并提供 Web 管理后台。

## 功能特性

- **多数据源采集** — 巨潮资讯网（上市公司公告）、36氪融资快报、广东省政府采购中心
- **AI 智能抽取** — 基于 DeepSeek 大模型，自动提取公司名、金额、地区、事件类型等结构化字段
- **营销建议生成** — 每条情报自动生成营销切入建议
- **地域过滤** — 支持配置包含省份、排除城市、额外包含城市
- **企业微信推送** — Markdown 格式推送到群机器人
- **Web 管理后台** — Vue 3 + Element Plus SPA，支持情报检索、统计看板、数据源管理、推送记录

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3, FastAPI, SQLite |
| AI | DeepSeek API |
| 前端 | Vue 3, Element Plus, Vite |
| 推送 | 企业微信机器人 Webhook |

## 快速开始

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装前端依赖（可选，仅开发前端时需要）

```bash
cd frontend && npm install
```

### 3. 配置

编辑 `config.json`：

```json
{
    "deepseek_api_key": "sk-你的DeepSeek API Key",
    "deepseek_api_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-v4-flash",
    "wecom_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的机器人key",
    "data_dir": "./data",
    "db_path": "./data/intelligence.db"
}
```

> **注意**：`config.json` 中包含了 API Key 和 Webhook URL，上传到 GitHub 前请先将其加入 `.gitignore` 或替换为占位值。

### 4. 运行 CLI 采集

```bash
# 测试模式（只采集不推送）
python main.py --test

# 正式运行（采集+推送）
python main.py

# 控制每个关键词处理条数
python main.py --max 10

# 只搜索指定关键词
python main.py --keyword 中标
```

### 5. 启动 Web 管理端

```bash
# 生产模式（后端直接 serve 编译后的 SPA）
python web.py

# 或开发模式（前后端分离，有热更新）
# 终端 1：
python web.py
# 终端 2：
cd frontend && npm run dev
```

访问 `http://localhost:8000` 即可打开管理后台。

> 开发模式下前端访问 `http://localhost:5173`，Vite 自动代理 `/api` 到后端。

## Web 管理页面

| 页面 | 路由 | 功能 |
|---|---|---|
| 情报列表 | `/` | 多维筛选、分页、查看详情、标记手动推送、清空数据 |
| 情报详情 | `/event/:id` | 完整情报信息、AI 营销建议、原文链接、原文内容 |
| 统计看板 | `/stats` | 今日新增、情报总数、推送率、类型分布、来源分布、7 日趋势 |
| 数据源管理 | `/sources` | 数据源状态、最近采集记录、立即采集（含关键词勾选 + 进度） |
| 完整采集 | `/pipeline` | 一键触发全量采集流水线、查看最近结果和采集历史 |
| 推送记录 | `/push-logs` | 状态筛选、分页查看 |
| 系统设置 | `/settings` | 地域过滤规则、DeepSeek 密钥配置、企业微信 Webhook |

## REST API

```
GET   /api/events                  # 分页情报列表（支持 event_type/company/date/source/status 筛选）
GET   /api/events/:id              # 单条情报详情
POST  /api/events/:id/mark-sent    # 标记为已推送
POST  /api/events/clear            # 清空全部情报
GET   /api/stats                   # 统计数据
GET   /api/push-logs               # 推送记录
GET   /api/sources                 # 数据源状态 + 采集历史
POST  /api/crawl/:source           # 触发单数据源采集（支持 keywords 参数）
GET   /api/crawl-status/:id        # 查询采集进度
POST  /api/crawl-cancel/:id        # 取消采集
POST  /api/run-pipeline            # 触发完整采集流水线
GET   /api/pipeline-latest         # 最近一次流水线结果
GET   /api/pipeline-runs           # 流水线历史
GET   /api/settings                # 获取设置
PUT   /api/settings                # 更新设置
GET   /api/health                  # 健康检查
```

## 数据源

| 数据源 | 类型 | 范围 | 频次 |
|---|---|---|---|
| **巨潮资讯网** (cninfo) | 上市公司公告 API | 深交所、上交所、北交所 | 可按关键词搜索 |
| **36氪融资快报** (pitchhub) | 快讯 API | 投融资事件 | 实时快讯流 |
| **广东省政府采购中心** (gdgov) | HTML 页面解析 | 广东省政府采购公告 | 约 400 条公告 |

巨潮资讯网支持关键词选择（中标、成交、融资、对外投资、扩产、并购、政府补助），在前端「立即采集」时可自由勾选。

## 项目结构

```
intelligence-center/
├── main.py                 # CLI 入口（单次采集+推送）
├── web.py                  # FastAPI Web 服务（API + SPA）
├── config.py               # 配置加载
├── config.json             # 配置文件
│
├── crawler_cninfo.py       # 巨潮资讯网爬虫
├── crawler_36kr_pitchhub.py # 36氪融资快报爬虫
├── crawler_gdgov.py        # 广东省政府采购中心爬虫
├── ai_extractor.py         # DeepSeek AI 抽取 + 营销建议
├── notifier.py             # 企业微信推送
├── database.py             # SQLite 基础操作
├── dashboard_db.py         # 数据库扩展（统计、设置、推送日志）
│
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── api/index.js        # API 客户端
│   │   ├── router/index.js     # 路由配置
│   │   └── views/              # 7 个页面组件
│   ├── dist/               # 编译后的静态文件
│   └── vite.config.js      # Vite 配置（/api 代理）
│
├── requirements.txt
├── data/
│   └── intelligence.db     # SQLite 数据库
└── templates/              # 旧版 Jinja2 模板（仅 /crawl/:id 在用）
```

## 工作流程

```
爬虫采集 → AI 抽取（公司名/金额/地区/事件类型）
              ↓
         地域过滤（配置的省份/城市规则）
              ↓
         营销建议生成（DeepSeek）
              ↓
         企业微信推送 + SQLite 存储
              ↓
         Web 管理后台展示
```

## 地域过滤规则

在「设置」页面可配置：

- **包含省份** — 只采集这些省份的情报，多个用逗号分隔（默认：广东）
- **排除城市** — 从包含省份中排除以下城市（默认：深圳）
- **额外包含城市** — 不限省份，这些城市的情报都采集

## 注意事项

- 首次运行建议 `--test` 模式验证
- DeepSeek API Key 需保证余额充足
- 数据自动去重（基于 source_url），不会重复推送
- 上传 GitHub 前确保 `config.json` 中的敏感信息已脱敏
