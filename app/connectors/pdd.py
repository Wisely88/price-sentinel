import httpx
from typing import List
import re
from urllib.parse import quote
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT, USER_AGENT

class PDDConnector(BaseConnector):
    name = "拼多多"
    platform_key = "pdd"

    # PDD mobile search / public suggestion gateway
    SEARCH_URL = "https://mobile.yangkeduo.com/proxy/api/search?q={keyword}&page=1&size=20"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://mobile.yangkeduo.com/",
    }

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        encoded_kw = quote(clean_kw)
        url = self.SEARCH_URL.format(keyword=encoded_kw)

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        items = data.get("items", []) or data.get("goods_list", [])
                        for item in items:
                            if len(results) >= limit:
                                break

                            # 1. 过滤广告推广位
                            if item.get("is_ad") or item.get("ad") or item.get("p_rec"):
                                continue

                            raw_title = item.get("goods_name") or item.get("title", "")
                            title = self.clean_title(raw_title)
                            if not title or "广告" in title:
                                continue

                            # 2. 过滤配件低价引流
                            if self.is_accessory_trap(title, clean_kw):
                                continue

                            # 3. 价格提取 (拼多多价格多以分计算，如 499900 = 4999.00)
                            price_raw = item.get("price") or item.get("min_group_price") or item.get("normal_price")
                            if not price_raw:
                                continue
                            try:
                                price_val = float(price_raw)
                                # 如果大于 10000 且没有小数，通常是按分计算
                                if price_val > 1000 and isinstance(price_raw, int):
                                    price = round(price_val / 100.0, 2)
                                else:
                                    price = round(price_val, 2)
                            except (ValueError, TypeError):
                                continue

                            if price <= 0:
                                continue

                            goods_id = str(item.get("goods_id", ""))
                            # 4. 优惠标签与黑标认证
                            tags = []
                            if item.get("has_subsidy") or "补贴" in title or item.get("is_subsidy"):
                                tags.append("百亿补贴")
                            if item.get("brand_name"):
                                tags.append(f"品牌: {item.get('brand_name')}")
                            if item.get("mall_name"):
                                tags.append(item.get("mall_name"))

                            discount_info = " / ".join(tags) if tags else "拼单特惠"
                            is_official = bool("百亿补贴" in discount_info or item.get("mall_type") == 1)

                            # 5. 直达链接 (纯净无跟踪参数)
                            clean_direct_url = f"https://mobile.yangkeduo.com/goods.html?goods_id={goods_id}"
                            img_url = item.get("thumb_url") or item.get("hd_thumb_url", "")

                            results.append(SearchResult(
                                title=title,
                                platform=self.name,
                                platform_key=self.platform_key,
                                item_id=goods_id,
                                price=price,
                                final_price=price,
                                discount_tag=discount_info,
                                url=clean_direct_url,
                                image_url=img_url,
                                shop_name=item.get("mall_name", "拼多多优质店铺"),
                                is_official=is_official
                            ))
                    except Exception as json_err:
                        print(f"[PDDConnector] JSON parse err: {json_err}")

        except Exception as e:
            print(f"[PDDConnector] Search error for '{query}': {e}")

        return results
