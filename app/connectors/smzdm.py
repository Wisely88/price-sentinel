import httpx
import re
from typing import List
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT

class SMZDMConnector(BaseConnector):
    name = "什么值得买"
    platform_key = "smzdm"

    API_URL = "https://api.smzdm.com/v1/youhui/articles?search={keyword}"

    HEADERS = {
        "User-Agent": "smzdm/10.4.26 (iPhone; iOS 17.4)",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    def _extract_price(self, raw_price_str: str) -> float:
        if not raw_price_str:
            return 0.0
        # Check "后xxx" or "到手价xxx"
        match_after = re.search(r"(?:补贴后|券后|折后|到手价)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw_price_str)
        if match_after:
            return float(match_after.group(1))
        # First number
        match_num = re.search(r"(\d+(?:\.\d+)?)", raw_price_str)
        if match_num:
            return float(match_num.group(1))
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

    async def search(self, query: str, limit: int = 15) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        if not clean_kw:
            return results

        url = self.API_URL.format(keyword=clean_kw)
        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return results

                data = resp.json().get("data", {}).get("rows", [])
                for row in data:
                    if len(results) >= limit:
                        break

                    raw_title = row.get("article_title", "")
                    title = self.clean_title(raw_title)
                    if not title or "广告" in title:
                        continue

                    # 1. 过滤配件低价陷阱
                    if self.is_accessory_trap(title, clean_kw):
                        continue

                    # 2. 价格提取
                    raw_price = row.get("article_price", "")
                    price = self._extract_price(raw_price)
                    if price <= 0:
                        continue

                    # 3. 平台映射
                    raw_mall = row.get("article_mall", "电商平台")
                    platform_name, platform_key, is_official = self._map_platform(raw_mall)

                    # 4. 优惠标签与链接
                    article_id = str(row.get("article_id", ""))
                    # Direct purchase link: prefers article_link, fallbacks to article_url
                    direct_url = row.get("article_link") or row.get("article_url") or f"http://www.smzdm.com/p/{article_id}"
                    img_url = row.get("article_pic", "")

                    discount_tag = raw_price
                    if "需用券" in raw_price:
                        discount_tag = "需用券 / 领券直减"
                    elif "需用国补" in raw_price or "补贴" in raw_price:
                        discount_tag = "国家补贴 / 平台限时补贴"

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
                        is_official=is_official
                    ))
        except Exception as e:
            print(f"[SMZDMConnector] Search error for '{query}': {e}")

        return results
