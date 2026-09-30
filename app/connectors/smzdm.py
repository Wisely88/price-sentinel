"""
SMZDM Connector / 什么值得买连接器
Features concurrent multi-offset pagination, real-time discount parsing, and coupon extraction.
具备并发多偏移量深度分页拉取、实时折扣与优惠券条件解析功能。
"""

import httpx
import asyncio
import re
from typing import List
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT

class SMZDMConnector(BaseConnector):
    name = "什么值得买"
    platform_key = "smzdm"

    API_URL = "https://api.smzdm.com/v1/youhui/articles?search={keyword}&limit=50&offset={offset}"

    HEADERS = {
        "User-Agent": "smzdm/10.4.26 (iPhone; iOS 17.4)",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def _extract_price(self, raw_price_str: str) -> float:
        if not raw_price_str:
            return 0.0
        # Check "后xxx" or "到手价xxx"
        match_after = re.search(r"(?:补贴后|券后|折后|到手价|实付|单件|低至)\s*[:：]?\s*[¥￥]?\s*(\d+(?:\.\d+)?)", raw_price_str)
        if match_after:
            return float(match_after.group(1))
        # Number explicitly marked with 元
        match_yuan = re.search(r"(\d+(?:\.\d+)?)\s*元", raw_price_str)
        if match_yuan:
            return float(match_yuan.group(1))
        # Currency symbol ¥ / ￥
        match_symbol = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", raw_price_str)
        if match_symbol:
            return float(match_symbol.group(1))
        return 0.0

    def _map_platform(self, mall: str):
        mall_lower = mall.lower()
        if "京东" in mall:
            return "京东", "jd", "自营" in mall
        elif "天猫" in mall or "淘宝" in mall:
            return "天猫/淘宝", "taobao", "官旗" in mall or "超市" in mall or "官方" in mall
        elif "拼多多" in mall:
            return "拼多多", "pdd", "百亿补贴" in mall or "官方" in mall
        elif "唯品会" in mall:
            return "唯品会", "vip", True
        elif "抖音" in mall:
            return "抖音商城", "douyin", False
        else:
            return mall or "电商精选", "other", False

    async def search(self, query: str, limit: int = 50) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        if not clean_kw:
            return results

        # Determine how many pages to fetch based on requested limit
        offsets = [0, 50] if limit > 20 else [0]
        if limit > 60:
            offsets.append(100)

        seen_article_ids = set()

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                tasks = [
                    client.get(self.API_URL.format(keyword=clean_kw, offset=off))
                    for off in offsets
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                for resp in responses:
                    if isinstance(resp, Exception) or resp.status_code != 200:
                        continue

                    try:
                        data = resp.json().get("data", {}).get("rows", [])
                    except Exception:
                        continue

                    for row in data:
                        if len(results) >= limit:
                            break

                        article_id = str(row.get("article_id", ""))
                        if article_id and article_id in seen_article_ids:
                            continue
                        if article_id:
                            seen_article_ids.add(article_id)

                        # 1. 标记是否已结束或售罄（保留近期历史底价作为参考基准，避免0搜索结果）
                        is_timeout = row.get("article_is_timeout") in (1, "1", True)
                        is_sold_out = row.get("article_is_sold_out") in (1, "1", True)
                        is_ended = bool(is_timeout or is_sold_out)

                        raw_title = row.get("article_title", "")
                        title = self.clean_title(raw_title)
                        if not title or "广告" in title:
                            continue

                        # 2. 过滤配件低价陷阱
                        if self.is_accessory_trap(title, clean_kw):
                            continue

                        # 3. 价格提取与常识保护
                        raw_price = row.get("article_price", "")
                        price = self._extract_price(raw_price)
                        if price <= 0:
                            continue

                        # 若搜索主设备但价格荒谬（<50元），判定为伪配件或非实物券
                        main_indicators = ["iphone", "ipad", "手机", "相机", "显卡", "笔记本", "电视", "冰箱", "洗衣机"]
                        if any(m in clean_kw.lower() for m in main_indicators) and price < 50:
                            continue

                        # 4. 平台映射
                        raw_mall = row.get("article_mall", "电商平台")
                        platform_name, platform_key, is_official = self._map_platform(raw_mall)

                        # 5. 版本与换新检测 (美版/海外版/以旧换新/二手)
                        is_trade_in, is_overseas, is_refurbished, version_badge = self.detect_version(title + " " + raw_price + " " + str(row), clean_kw)

                        # 6. SKU 规格提取
                        spec = self.extract_spec(raw_title) or self.extract_spec(raw_price)

                        # 7. 价格生效条件/优惠说明
                        notes = []
                        if is_ended:
                            notes.append("近期好价(活动已结束)")
                        if is_trade_in:
                            notes.append("需以旧换新")
                        if is_overseas:
                            notes.append("海外/美版")
                        if is_refurbished:
                            notes.append("二手官翻")
                        if "需用券" in raw_price or "需领券" in raw_price:
                            notes.append("需领券")
                        if "国补" in raw_price or "国家补贴" in raw_price:
                            notes.append("含国补")
                        elif "补贴" in raw_price:
                            notes.append("含补贴")
                        if "需买" in raw_price or re.search(r"\d+件", raw_price):
                            notes.append("多件优惠")
                        if "淘金币" in raw_price:
                            notes.append("需淘金币")
                        if "返" in raw_price and ("返卡" in raw_price or "返利" in raw_price or "晒单" in raw_price):
                            notes.append("含返卡")
                        if spec:
                            notes.append(f"{spec}规格")
                        else:
                            notes.append("配置实选为准")
                        price_note = " · ".join(notes)

                        # 8. 优惠标签与链接
                        direct_url = row.get("article_link") or row.get("article_url") or f"http://www.smzdm.com/p/{article_id}"
                        img_url = row.get("article_pic", "")
                        pub_time = row.get("article_format_date") or row.get("article_date", "")

                        discount_tag = raw_price
                        if is_ended:
                            discount_tag = "历史特惠参考 / 已结束"
                        elif "需用券" in raw_price:
                            discount_tag = "需用券 / 领券直减"
                        elif "需用国补" in raw_price or "补贴" in raw_price:
                            discount_tag = "国家补贴 / 平台限时补贴"

                        platform_search_url = self.get_platform_search_url(platform_key, title)

                        results.append(SearchResult(
                            title=title,
                            platform=platform_name,
                            platform_key=platform_key,
                            item_id=article_id,
                            price=price,
                            final_price=price,
                            discount_tag=discount_tag,
                            url=direct_url,
                            image_url=img_url,
                            shop_name=raw_mall,
                            is_official=is_official,
                            spec=spec,
                            price_note=price_note,
                            publish_time=pub_time,
                            platform_search_url=platform_search_url,
                            is_trade_in=is_trade_in,
                            is_overseas=is_overseas,
                            is_refurbished=is_refurbished,
                            version_badge=version_badge,
                            is_ended=is_ended
                        ))
        except Exception as e:
            print(f"[SMZDMConnector] Search error for '{query}': {e}")

        return results
