import httpx
from bs4 import BeautifulSoup
from typing import List
import re
from urllib.parse import quote
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT, USER_AGENT

class TaobaoConnector(BaseConnector):
    name = "淘宝/天猫"
    platform_key = "taobao"

    SEARCH_URL = "https://s.taobao.com/search?q={keyword}&commend=all&search_type=item&sourceId=tb.index"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.taobao.com/",
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

                # Taobao often puts search results inside g_page_config JSON variable in the page
                json_match = re.search(r"g_page_config\s*=\s*(\{.*?\});\s*</script>", resp.text, re.DOTALL)
                if json_match:
                    import json
                    try:
                        data = json.loads(json_match.group(1))
                        items = (
                            data.get("mods", {})
                            .get("itemlist", {})
                            .get("data", {})
                            .get("auctions", [])
                        )
                        for item in items:
                            if len(results) >= limit:
                                break
                            
                            # 1. 过滤广告推广直通车
                            if item.get("isP4p") or "p4p" in str(item).lower():
                                continue
                            
                            raw_title = item.get("raw_title") or item.get("title", "")
                            title = self.clean_title(raw_title)
                            if "广告" in title:
                                continue

                            # 2. 过滤配件陷阱
                            if self.is_accessory_trap(title, clean_kw):
                                continue

                            # 3. 价格提取
                            price_val = item.get("view_price") or item.get("price", "0")
                            try:
                                price = float(price_val)
                            except ValueError:
                                continue
                            if price <= 0:
                                continue

                            item_id = str(item.get("nid", ""))
                            shop_name = item.get("nick", "淘宝商家")
                            is_tmall = bool(item.get("shopcard", {}).get("isTmall") or "tmall" in item.get("detail_url", ""))
                            is_official = is_tmall and ("官方" in shop_name or "旗舰" in shop_name)

                            # 4. 优惠标签
                            icons = item.get("icon", [])
                            tags = []
                            for ic in icons:
                                dom_title = ic.get("title") or ic.get("dom_class", "")
                                if dom_title:
                                    tags.append(dom_title)
                            
                            discount_info = " / ".join(tags) if tags else ("天猫正品" if is_tmall else "店铺在售")

                            # 5. 链接与图片
                            detail_url = item.get("detail_url", "")
                            if not detail_url and item_id:
                                detail_url = f"https://detail.tmall.com/item.htm?id={item_id}" if is_tmall else f"https://item.taobao.com/item.htm?id={item_id}"
                            
                            clean_direct_url = self.clean_url(detail_url)
                            img_url = item.get("pic_url", "")
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url

                            results.append(SearchResult(
                                title=title,
                                platform="天猫" if is_tmall else "淘宝",
                                platform_key=self.platform_key,
                                item_id=item_id,
                                price=price,
                                final_price=price,
                                discount_tag=discount_info,
                                url=clean_direct_url,
                                image_url=img_url,
                                shop_name=shop_name,
                                is_official=is_official
                            ))
                    except Exception as e:
                        print(f"[TaobaoConnector] JSON parse error: {e}")

                # Fallback: HTML parse if JSON variable not matched
                if not results:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select(".Card--doubleCardWrapper--2PClU9z, .item, .ctx-box")
                    for card in cards:
                        if len(results) >= limit:
                            break
                        # Check ad
                        if card.select_one(".icon-service-hot, .adMarker, [class*='p4p']"):
                            continue
                        title_el = card.select_one("[class*='title'], .title")
                        if not title_el:
                            continue
                        title = self.clean_title(title_el.get_text(strip=True))
                        if self.is_accessory_trap(title, clean_kw):
                            continue
                        
                        price_el = card.select_one("[class*='priceInt'], .price")
                        if not price_el:
                            continue
                        try:
                            price = float(re.sub(r"[^\d.]", "", price_el.get_text(strip=True)))
                        except ValueError:
                            continue

                        link_el = card.select_one("a[href*='item.htm'], a[href*='detail.tmall.com']")
                        href = link_el.get("href", "") if link_el else ""
                        direct_url = self.clean_url(href)
                        
                        results.append(SearchResult(
                            title=title,
                            platform=self.name,
                            platform_key=self.platform_key,
                            item_id="",
                            price=price,
                            final_price=price,
                            discount_tag="店铺优惠",
                            url=direct_url,
                            image_url="",
                            shop_name="淘宝/天猫精选",
                            is_official="官方" in title
                        ))

        except Exception as e:
            print(f"[TaobaoConnector] Search error for '{query}': {e}")

        return results
