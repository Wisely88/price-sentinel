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
        limit_per_platform: int = 15
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
                "direct_channels": []
            }

        # 1. Concurrently query real price sources
        tasks = [
            self.smzdm.search(clean_kw, limit=limit_per_platform),
            self.mmb.search(clean_kw, limit=limit_per_platform),
            self.jd.search(clean_kw, limit=5),
            self.taobao.search(clean_kw, limit=5),
            self.pdd.search(clean_kw, limit=5)
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: List[SearchResult] = []
        platform_counts: Dict[str, int] = {"jd": 0, "taobao": 0, "pdd": 0, "other": 0}

        # Deduplication tracker by normalized title
        seen_titles = set()

        for res in raw_results:
            if isinstance(res, list):
                for item in res:
                    if item.final_price <= 0:
                        continue
                    # Deduplicate closely matching titles
                    norm_title = "".join(item.title.split())[:25].lower()
                    if norm_title in seen_titles:
                        continue
                    seen_titles.add(norm_title)

                    # Filter by requested platforms if specified
                    if platforms:
                        # Allow matching if platform_key is in requested platforms
                        if item.platform_key not in platforms and "other" not in platforms:
                            # If user selected jd and item is jd
                            continue

                    all_items.append(item)
                    key = item.platform_key if item.platform_key in platform_counts else "other"
                    platform_counts[key] = platform_counts.get(key, 0) + 1

        # Sort strictly by final price ascending (cheapest first)
        all_items.sort(key=lambda x: (x.final_price, not x.is_official))

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

        return {
            "query": clean_kw,
            "total_count": len(all_items),
            "min_price": min_price,
            "max_price": max_price,
            "max_savings": max_savings,
            "platform_counts": platform_counts,
            "direct_channels": direct_channels,
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
            "is_lowest": item.is_lowest
        }
