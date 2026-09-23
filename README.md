# PriceSentinel (价格哨兵) 🛡️

[中文文档](#中文文档) | [English Documentation](#english-documentation)

---

<a name="中文文档"></a>
# 中文文档

> **纯净、无广告偏见的跨平台电商比价与降价监控平台**  
> 专为追求真实到手底价、杜绝电商营销套路的用户打造。

---

## 🌟 核心痛点与解决方案

在当今主流网购比价过程中，用户经常遭遇以下陷阱：
1. **虚假营销与竞价广告充斥**：大量标有 `HOT`、`直通车`、`商智推广` 的竞价位占据搜索前列。
2. **配件引流假标价**：搜索主设备（如 iPhone、相机、笔记本）时，商家以 20 元的“手机壳”、“钢化膜”挂在主商品标题下，虚标为全网最低价。
3. **以旧换新陷阱**：标价看似极低，点击进去却强制要求寄回旧机抵扣数千元，并非直接现金购买价。
4. **海外水货与国行混杂**：低价通常为美版单卡、无国内保修的机器，缺乏标识。
5. **商品量少与过度折叠**：传统聚合单页通常只有十来条商品，不同规格容量（如 256GB vs 512GB vs 1TB）常被粗暴算法去重过滤。

**PriceSentinel** 针对上述问题构建了纯净比价引擎：
- 🛡️ **彻底剔除竞价广告**：自动识别并过滤各电商推广广告。
- 🔍 **配件陷阱自动识别**：智能校验主品类关键词与价格常识保护，彻底过滤搭售配件。
- 🇨🇳 **全新国行直购保障**：数码家电大件自动启用全新国行保护，隔离以旧换新抵扣及美版水货。
- 🎯 **品类智能感知**：数码类严格标注版本，日用百货食品（如咖啡豆、纸巾、牛奶）保持极简清爽，不乱打标签。
- ⚡ **并发多页深度挖掘**：多平台并发拉取 100+ 原始数据，经清洗后呈现 40～80+ 条真实促销，支持按容量规格（256GB/512GB/1TB）一键筛选。
- 🔗 **纯净直达链接**：彻底剥离追踪参数（`spm`、`cps`、`utm_source`、`union_id`），支持直达购买与一键复制。
- 🔔 **多端降价自动巡检**：后台常驻定时巡检，破价时自动触发 **macOS 原生通知**、**iPhone 实时推送 (Bark)** 或 **企业微信/钉钉/飞书 Webhook**。

---

## 🏗️ 架构概览

```
price-sentinel/
├── run.py                 # 服务一键启动脚本 (自动识别局域网 IP 与端口)
├── config.py              # 全局配置 (服务端口、超时时间、UA 伪装)
├── requirements.txt       # Python 依赖列表
├── app/
│   ├── main.py            # FastAPI 应用与 RESTful API 端点
│   ├── database.py        # SQLite 持久化 (商品监控表、价格走势、系统设置)
│   ├── connectors/        # 电商平台接入与数据清洗引擎
│   │   ├── base.py        # 基类、纯净 URL 清洗、配件陷阱识别、品类感知算法
│   │   ├── smzdm.py       # 什么值得买并发多分页深度优惠连接器
│   │   ├── mmb.py         # 全网好价 Next.js push 数据流解析连接器
│   │   ├── jd.py          # 京东自营与官方搜索通道
│   │   ├── taobao.py      # 淘宝/天猫官方搜索通道
│   │   └── pdd.py         # 拼多多百亿补贴搜索通道
│   ├── services/
│   │   ├── searcher.py    # 聚合检索、基准价偏离校验、跨平台智能去重与规格提取
│   │   ├── scheduler.py   # APScheduler 异步后台降价巡检器
│   │   └── notifier.py    # 多通道通知分发器 (macOS / Bark / Webhook)
│   └── static/
│       ├── index.html     # Apple 极简响应式 Web 控制台 (适配手机/平板/PC)
│       └── app.js         # 前端 Vue 3 + Tailwind 响应式逻辑 (规格筛选/分页加载)
└── tests/                 # 单元测试与端到端自动化测试套件 (17 项测试)
```

---

## 🚀 快速启动

### 1. 环境准备
需要 Python 3.10 或更高版本：
```bash
# 克隆仓库
git clone https://github.com/Wisely88/price-sentinel.git
cd price-sentinel

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动服务
```bash
python run.py
```

启动后终端将打印访问地址：
- **本机电脑访问**：`http://127.0.0.1:8765`
- **局域网手机/平板访问**：`http://<局域网IP>:8765`

### 3. 运行自动化测试
```bash
pytest tests/
```

---

## 📡 RESTful API 说明

| 请求方法 | 路径 | 说明 |
| :--- | :--- | :--- |
| `GET` | `/api/health` | 服务健康检查 |
| `GET` | `/api/search?q={query}&platforms={jd,taobao,pdd}&only_national=true` | 全网纯净比价检索 |
| `GET` | `/api/favorites` | 获取降价监控商品清单 |
| `POST` | `/api/favorites` | 添加商品至降价监控清单 |
| `DELETE` | `/api/favorites/{id}` | 从监控清单中移除商品 |
| `POST` | `/api/favorites/{id}/check` | 手动触发单品即时价格巡检 |
| `GET` | `/api/settings` | 读取系统推送与巡检配置 |
| `POST` | `/api/settings` | 更新系统推送配置 (Bark Key, Webhook 等) |
| `POST` | `/api/notify/test` | 触发多通道测试通知 |

---

<br><br>

---

<a name="english-documentation"></a>
# English Documentation

> **Ad-Free, Unbiased Cross-Platform Price Comparison & Sentinel Platform**  
> Built for users seeking authentic net prices free from affiliate bias and deceptive e-commerce marketing tactics.

---

## 🌟 Problems & Solutions

Modern online shopping platforms frequently employ deceptive marketing tricks:
1. **Ad-Loaded Search Results**: Sponsored listings, bidding spots, and promoted banners dominate the top results.
2. **Accessory Bait-and-Switch**: Searching for high-value devices (e.g., iPhone, cameras, laptops) often displays \$3 phone cases or screen protectors disguised as the actual device.
3. **Trade-in Traps**: Displaying an artificially low price that requires mailing in an old device for trade-in valuation rather than representing a direct cash purchase price.
4. **Overseas / Grey-Market Confusion**: Unofficial imported versions (e.g., US single-SIM models lacking domestic warranty) are intermingled without clear warnings.
5. **Result Truncation & Over-Deduplication**: Typical scrapers return only ~10 items and naively truncate titles, wiping out different storage configurations (256GB vs 512GB vs 1TB).

**PriceSentinel** solves these challenges with a dedicated consumer-first engine:
- 🛡️ **Commercial Ad Removal**: Automatically identifies and eliminates paid promotional entries.
- 🔍 **Accessory Trap Detection**: Uses category-specific keywords and sensible price thresholds to filter out cheap accessories.
- 🇨🇳 **National Bank & Direct Purchase Guarantee**: Filters out trade-in deductions and unauthorized grey-market variants for electronics.
- 🎯 **Category-Aware Tagging**: Enforces strict version badges (`National Retail`, `Overseas`, `Trade-In`) for electronics, while keeping everyday consumables (coffee, paper, food) clean and uncluttered.
- ⚡ **Deep Concurrent Multi-Page Retrieval**: Concurrently fetches 100+ raw entries across platforms, delivering 40–80+ validated promotions with dynamic spec filtering (`256GB`, `512GB`, `1TB`).
- 🔗 **Pure Direct Links**: Strips marketing tracking parameters (`spm`, `cps`, `utm_source`, `union_id`) for clean navigation.
- 🔔 **Automated Sentinel Monitoring**: Background periodic scheduler triggers **native macOS notifications**, **iOS Bark push alerts**, or **custom Webhooks** whenever a price drop is detected.

---

## 🏗️ Project Architecture

```
price-sentinel/
├── run.py                 # One-click server launcher with LAN IP auto-detection
├── config.py              # Global settings (ports, timeouts, user agents)
├── requirements.txt       # Python dependencies
├── app/
│   ├── main.py            # FastAPI RESTful web service and routing
│   ├── database.py        # SQLite storage (favorites, price history, settings)
│   ├── connectors/        # E-commerce scrapers and data sanitization
│   │   ├── base.py        # Base connector, URL cleaner, accessory detector, category logic
│   │   ├── smzdm.py       # High-yield multi-offset concurrent deals connector
│   │   ├── mmb.py         # Multi-page Next.js hydration stream connector
│   │   ├── jd.py          # JD self-operated and official search fallback
│   │   ├── taobao.py      # Taobao / Tmall flagship search fallback
│   │   └── pdd.py         # PDD Brand Subsidy search fallback
│   ├── services/
│   │   ├── searcher.py    # Search aggregation, anomaly baseline checks, smart dedup
│   │   ├── scheduler.py   # APScheduler background periodic price watcher
│   │   └── notifier.py    # Multi-channel notification dispatcher (macOS / Bark / Webhook)
│   └── static/
│       ├── index.html     # Apple-inspired responsive dashboard (Mobile/Tablet/PC)
│       └── app.js         # Vue 3 + Tailwind frontend logic (spec filter, progressive load)
└── tests/                 # Automated unit and integration test suite (17 passed)
```

---

## 🚀 Quick Start

### 1. Prerequisites
Requires Python 3.10+:
```bash
# Clone the repository
git clone https://github.com/Wisely88/price-sentinel.git
cd price-sentinel

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Launch the Service
```bash
python run.py
```

Access URLs will be displayed in the terminal:
- **Local Machine**: `http://127.0.0.1:8765`
- **LAN Mobile / Tablet**: `http://<LAN_IP>:8765`

### 3. Run Automated Tests
```bash
pytest tests/
```

---

## 📡 RESTful API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/search?q={query}&platforms={jd,taobao,pdd}&only_national=true` | Ad-free multi-platform price query |
| `GET` | `/api/favorites` | Retrieve list of monitored products |
| `POST` | `/api/favorites` | Add product to price drop monitor |
| `DELETE` | `/api/favorites/{id}` | Remove product from monitoring |
| `POST` | `/api/favorites/{id}/check` | Manually trigger price inspection for an item |
| `GET` | `/api/settings` | Get alert and notification settings |
| `POST` | `/api/settings` | Update settings (Bark Key, Webhook, interval) |
| `POST` | `/api/notify/test` | Trigger multi-channel test notification |

---

## 📄 License

MIT License © 2026 Wisely88.
