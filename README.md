# PriceSentinel (价格哨兵) · 纯净全网比价与降价提醒平台

这是一个专为追求**真实底价、零广告营销偏见**的用户打造的私有化比价与降价监控平台。

---

## 核心特性

- **彻底剔除竞价广告**：自动识别并过滤京东、淘宝、天猫、拼多多搜索中的 `HOT`、`直通车`、`商智推广`、`广告` 标签商品。
- **杜绝配件引流陷阱**：自动识别“低价手机壳/钢化膜冒充真机”的阴阳标价陷阱。
- **客观到手价排序**：不接入任何 CPS 商业返利，仅按 `[原始标价 - 活动满减 - 平台券]` 计算出的实际到手底价从低到高排列。
- **纯净直达链接**：彻底剥离追踪参数（`spm`、`cps`、`utm_source` 等），支持一键直达或复制。
- **多端降价推送**：
  - **macOS 原生通知**：降价时直接在 Mac 屏幕右上角弹出系统通知横幅。
  - **iPhone 实时推送 (Bark)**：支持配置专属 Bark Key，降价直接推送至 iPhone，点击通知直达商品详情。
  - **自定义 Webhook**：支持配置企业微信、飞书、钉钉机器人或 Server酱。
- **全自动后台巡检**：内置 APScheduler 周期性巡检已收藏监控的商品，发现破价或新优惠时自动触发提醒。

---

## 极速启动

进入项目根目录：

```bash
cd /Users/wisely/.gemini/antigravity/scratch/price-sentinel

# 启动服务
.venv/bin/python run.py
```

终端将打印访问地址：
- **Mac 浏览器访问**：`http://127.0.0.1:8765`
- **局域网内 iPhone 访问**：`http://<局域网IP>:8765`

---

## 架构概览

```
price-sentinel/
├── run.py                 # 一键启动脚本
├── config.py              # 服务端口与系统默认参数
├── requirements.txt       # Python 依赖清单
├── app/
│   ├── main.py            # FastAPI 应用与 REST 路由
│   ├── database.py        # SQLite 数据库模型 (收藏表、价格历史、系统设置)
│   ├── connectors/        # 平台抓取与去广告引擎
│   │   ├── base.py        # 基类、广告清洗与配件陷阱识别
│   │   ├── jd.py          # 京东自营/旗舰店抓取与解析
│   │   ├── taobao.py      # 淘宝/天猫商品搜索与解析
│   │   └── pdd.py         # 拼多多百亿补贴与解析
│   ├── services/
│   │   ├── searcher.py    # 并发聚合搜索、SKU 排序与价差统计
│   │   ├── scheduler.py   # 后台定时巡检器 (APScheduler)
│   │   └── notifier.py    # 多通道通知服务 (macOS / Bark / Webhook)
│   └── static/
│       ├── index.html     # Apple 极简风格 Web Dashboard
│       └── app.js         # 前端响应式交互逻辑 (Vue 3 + Tailwind)
└── tests/                 # 单元测试与端到端测试套件 (12 个测试全部通过)
```

---

## 运行测试

```bash
.venv/bin/pytest tests
```
