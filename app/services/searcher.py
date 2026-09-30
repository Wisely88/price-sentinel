"""
Search Aggregator Service / 比价聚合检索服务
Coordinates concurrent connectors, conducts anomaly baseline price checks,
filters trade-in and grey-market lures, and performs smart multi-platform deduplication.
并发调用多源比价连接器，执行官方自营基准价异常校验、以旧换新/水货诱导拦截，并实现跨平台多规格智能保留去重。
"""

import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from app.connectors.base import SearchResult
from app.connectors.smzdm import SMZDMConnector
from app.connectors.mmb import MMBConnector
from app.connectors.jd import JDConnector
from app.connectors.taobao import TaobaoConnector
from app.connectors.pdd import PDDConnector

class SearchService:
    def __init__(self):
        self.smzdm = SMZDMConnector()
        self.mmb = MMBConnector()
        self.jd = JDConnector()
        self.taobao = TaobaoConnector()
        self.pdd = PDDConnector()

    async def search_all(
        self, 
        query: str, 
        platforms: Optional[List[str]] = None,
        limit_per_platform: int = 50,
        only_national_retail: bool = True
    ) -> Dict[str, Any]:
        clean_kw = query.strip()
        if not clean_kw:
            return {
                "query": "",
                "total_count": 0,
                "min_price": 0.0,
                "max_price": 0.0,
                "max_savings": 0.0,
                "items": [],
                "platform_counts": {},
                "direct_channels": [],
                "available_specs": [],
                "only_national_retail": only_national_retail
            }

        # User explicit intent flags
        want_trade_in = any(k in clean_kw.lower() for k in ["以旧换新", "换新", "回收"])
        want_overseas = any(k in clean_kw.lower() for k in ["美版", "美行", "日版", "日行", "港版", "港行", "海外", "水货", "卡贴"])
        want_refurbished = any(k in clean_kw.lower() for k in ["二手", "官翻", "99新", "95新", "拆封"])

        import re
        main_indicators = ["iphone", "ipad", "mac", "手机", "笔记本", "电脑", "相机", "显卡", "电视", "华为", "小米", "荣耀", "vivo", "oppo"]
        is_main_device = any(m in clean_kw.lower() for m in main_indicators)
        has_capacity = bool(re.search(r"\b(128|256|512|1t|1tb|64)\b", clean_kw, re.IGNORECASE))

        # 1. Concurrently query real price sources
        tasks = [
            self.smzdm.search(clean_kw, limit=limit_per_platform),
            self.mmb.search(clean_kw, limit=limit_per_platform),
            self.jd.search(clean_kw, limit=5),
            self.taobao.search(clean_kw, limit=5),
            self.pdd.search(clean_kw, limit=5)
        ]

        # 数码大件在未指定规格时，并发扩展搜索主力容量规格（如 256），绕过配件刷屏并提升有效商品条数
        if is_main_device and not has_capacity:
            tasks.append(self.smzdm.search(f"{clean_kw} 256", limit=limit_per_platform))
            tasks.append(self.mmb.search(f"{clean_kw} 256", limit=limit_per_platform))

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: List[SearchResult] = []
        platform_counts: Dict[str, int] = {"jd": 0, "taobao": 0, "pdd": 0, "other": 0}

        # Smart deduplication: never drop different platforms, different specs, or different prices
        seen_urls = set()
        seen_listing_keys = set()

        for res in raw_results:
            if isinstance(res, list):
                for item in res:
                    if item.final_price <= 0:
                        continue

                    # 1. Deduplicate identical clean URL
                    clean_u = item.url.split("?")[0].rstrip("/").lower() if item.url else ""
                    if clean_u and clean_u in seen_urls:
                        continue

                    # 2. Deduplicate exact same listing from same platform & shop with same price and spec
                    shop_clean = (item.shop_name or "").strip()
                    spec_clean = (item.spec or "").strip().upper()
                    price_rounded = round(item.final_price, 0)
                    listing_key = (item.platform_key, shop_clean, spec_clean, price_rounded)
                    if listing_key in seen_listing_keys:
                        continue

                    # Filter by requested platforms if specified
                    if platforms:
                        if item.platform_key not in platforms and "other" not in platforms:
                            continue

                    if clean_u:
                        seen_urls.add(clean_u)
                    seen_listing_keys.add(listing_key)

                    all_items.append(item)
                    key = item.platform_key if item.platform_key in platform_counts else "other"
                    platform_counts[key] = platform_counts.get(key, 0) + 1

        # 2. 旗舰大件数码官方基准价与非国行/换新异常偏离拦截
        is_main_device = any(m in clean_kw.lower() for m in ["iphone", "ipad", "mac", "手机", "笔记本", "电脑", "相机", "显卡", "电视"])
        if is_main_device:
            official_prices = [it.final_price for it in all_items if it.is_official and it.final_price > 1000]
            if official_prices:
                official_baseline = min(official_prices)
                for it in all_items:
                    # 若第三方非官方专营店价格大幅低于自营基准价 (>15%)，且标题无明确国行/双卡保证，自动打标为疑似海外版/需换新
                    if not it.is_official and it.final_price < official_baseline * 0.85:
                        if "国行" not in it.title and "双卡" not in it.title:
                            it.is_overseas = True
                            it.version_badge = "⚠️专营店低价(疑似美版/需换新)"
                            if "疑似美版" not in it.price_note:
                                it.price_note = ("⚠️远低于自营/疑似美版或需换新 · " + it.price_note).strip(" · ")

        # 3. 全新国行直购模式过滤 (纯净模式)
        if only_national_retail:
            filtered_items = []
            for it in all_items:
                if not want_trade_in and it.is_trade_in:
                    continue
                if not want_overseas and it.is_overseas:
                    continue
                if not want_refurbished and it.is_refurbished:
                    continue
                filtered_items.append(it)
            # 若全部过滤空了，降级保留全部并展示预警
            if filtered_items:
                all_items = filtered_items

        # 4. 排序规则：排除换新/海外后，按最终到手价由低到高排列（同价位官方自营优先）
        all_items.sort(key=lambda x: (
            x.is_trade_in,
            x.is_overseas,
            x.is_refurbished,
            x.final_price,
            not x.is_official
        ))

        min_price = all_items[0].final_price if all_items else 0.0
        max_price = max((it.final_price for it in all_items), default=0.0)
        max_savings = round(max(0.0, max_price - min_price), 2)

        if all_items:
            all_items[0].is_lowest = True

        # Generate official direct channels for quick jump
        enc = quote(clean_kw)
        direct_channels = [
            {
                "platform": "京东自营",
                "tag": "自营官方检索通道",
                "url": f"https://search.jd.com/Search?keyword={enc}&enc=utf-8"
            },
            {
                "platform": "天猫官方",
                "tag": "品牌官方旗舰店通道",
                "url": f"https://s.taobao.com/search?q={enc}"
            },
            {
                "platform": "拼多多百亿补贴",
                "tag": "百亿补贴品牌通道",
                "url": f"https://mobile.yangkeduo.com/search_result.html?search_key={enc}"
            }
        ]

        # Collect available specs for frontend filtering
        specs_set = set()
        for it in all_items:
            if it.spec:
                specs_set.add(it.spec.upper())
        # Sort specs (e.g. 128G < 256G < 512G < 1TB)
        available_specs = sorted(list(specs_set))

        return {
            "query": clean_kw,
            "total_count": len(all_items),
            "min_price": min_price,
            "max_price": max_price,
            "max_savings": max_savings,
            "platform_counts": platform_counts,
            "direct_channels": direct_channels,
            "available_specs": available_specs,
            "only_national_retail": only_national_retail,
            "is_digital_search": is_main_device,
            "items": [self._serialize_result(item) for item in all_items]
        }

    def _serialize_result(self, item: SearchResult) -> Dict[str, Any]:
        return {
            "title": item.title,
            "platform": item.platform,
            "platform_key": item.platform_key,
            "item_id": item.item_id,
            "price": item.price,
            "final_price": item.final_price,
            "discount_tag": item.discount_tag,
            "url": item.url,
            "image_url": item.image_url,
            "shop_name": item.shop_name,
            "is_official": item.is_official,
            "is_lowest": item.is_lowest,
            "spec": item.spec,
            "price_note": item.price_note,
            "publish_time": item.publish_time,
            "platform_search_url": item.platform_search_url,
            "is_trade_in": item.is_trade_in,
            "is_overseas": item.is_overseas,
            "is_refurbished": item.is_refurbished,
            "version_badge": item.version_badge,
            "is_ended": item.is_ended
        }
