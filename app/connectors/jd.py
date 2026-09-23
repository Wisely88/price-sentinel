import httpx
from bs4 import BeautifulSoup
from typing import List
import re
from urllib.parse import quote
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT, USER_AGENT

class JDConnector(BaseConnector):
    name = "京东"
    platform_key = "jd"

    SEARCH_URL = "https://search.jd.com/Search?keyword={keyword}&enc=utf-8"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.jd.com/",
    }

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        encoded_kw = quote(clean_kw)
        url = self.SEARCH_URL.format(keyword=encoded_kw)

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return results
                
                soup = BeautifulSoup(resp.text, "html.parser")
                goods_list = soup.select("#J_goodsList .gl-item, .goods-list-v2 .gl-item")
                
                for item in goods_list:
                    if len(results) >= limit:
                        break

                    # 1. 过滤广告 (Filter Ad flags)
                    if item.get("data-ad") == "1" or item.select_one(".p-promo-flag, .spu-ad, .ad-mark"):
                        continue
                    
                    sku = item.get("data-sku") or item.get("data-spu") or ""
                    if not sku:
                        continue

                    # 2. 标题提取与清洗
                    title_elem = item.select_one(".p-name em") or item.select_one(".p-name a")
                    if not title_elem:
                        continue
                    raw_title = title_elem.get_text(separator=" ", strip=True)
                    title = self.clean_title(raw_title)

                    # 排除明确包含“广告”的项
                    if "广告" in raw_title:
                        continue

                    # 3. 过滤配件引流坑
                    if self.is_accessory_trap(title, clean_kw):
                        continue

                    # 4. 价格提取
                    price_elem = item.select_one(".p-price i, .p-price em + i, [data-price]")
                    price_str = price_elem.get_text(strip=True) if price_elem else ""
                    try:
                        price = float(re.sub(r"[^\d.]", "", price_str))
                    except (ValueError, TypeError):
                        continue

                    if price <= 0:
                        continue

                    # 5. 优惠活动标签解析 (满减、优惠券、秒杀)
                    discount_tags = []
                    promo_elems = item.select(".p-icons i, .p-tag")
                    for p in promo_elems:
                        txt = p.get_text(strip=True)
                        if txt and txt not in ["关注", "对比"]:
                            discount_tags.append(txt)
                    
                    discount_info = " / ".join(discount_tags) if discount_tags else "日常在售"

                    # 6. 店铺与自营标签
                    shop_elem = item.select_one(".p-shop .curr-shop, .hd-shopname a")
                    shop_name = shop_elem.get_text(strip=True) if shop_elem else "京东商家"
                    is_official = bool("自营" in discount_info or "自营" in shop_name or "官方" in shop_name)

                    # 7. 预估到手价计算 (若有满减券标签，尝试粗估折后价)
                    final_price = price
                    match_reduce = re.search(r"满(\d+)减(\d+)", discount_info)
                    if match_reduce:
                        threshold = float(match_reduce.group(1))
                        reduction = float(match_reduce.group(2))
                        if price >= threshold:
                            final_price = max(0.01, round(price - reduction, 2))

                    # 8. 图片
                    img_elem = item.select_one(".p-img img")
                    img_url = ""
                    if img_elem:
                        img_url = img_elem.get("data-lazy-img") or img_elem.get("src") or ""
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url

                    # 纯净直达链接
                    direct_url = f"https://item.jd.com/{sku}.html"

                    results.append(SearchResult(
                        title=title,
                        platform=self.name,
                        platform_key=self.platform_key,
                        item_id=sku,
                        price=price,
                        final_price=final_price,
                        discount_tag=discount_info,
                        url=direct_url,
                        image_url=img_url,
                        shop_name=shop_name,
                        is_official=is_official
                    ))

        except Exception as e:
            # Graceful logging, do not fail entire comparison pipeline
            print(f"[JDConnector] Search error for '{query}': {e}")

        return results
