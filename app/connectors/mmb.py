import httpx
import re
import json
from typing import List
from urllib.parse import quote
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT, USER_AGENT

class MMBConnector(BaseConnector):
    name = "全网好价"
    platform_key = "mmb"

    BASE_URL = "http://s.manmanbuy.com/Default.aspx?key={keyword}"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "http://s.manmanbuy.com/",
    }

    def _extract_price(self, raw_price_str: str) -> float:
        if not raw_price_str:
            return 0.0
        match_after = re.search(r"(?:补贴后|券后|折后|到手价)\s*[:：]?\s*(\d+(?:\.\d+)?)", raw_price_str)
        if match_after:
            return float(match_after.group(1))
        match_num = re.search(r"(\d+(?:\.\d+)?)", raw_price_str)
        if match_num:
            return float(match_num.group(1))
        return 0.0

    def _map_platform(self, mall: str):
        if "京东" in mall:
            return "京东", "jd", "自营" in mall
        elif "天猫" in mall or "淘宝" in mall:
            return "天猫/淘宝", "taobao", "官旗" in mall or "官方" in mall
        elif "拼多多" in mall:
            return "拼多多", "pdd", "百亿补贴" in mall
        elif "唯品会" in mall:
            return "唯品会", "vip", True
        elif "苏宁" in mall:
            return "苏宁易购", "suning", False
        else:
            return mall or "电商直营", "other", False

    async def search(self, query: str, limit: int = 15) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        if not clean_kw:
            return results

        # Try search terms: original and without spaces
        terms = [clean_kw]
        if " " in clean_kw:
            terms.append(clean_kw.replace(" ", ""))

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                for term in terms:
                    url = self.BASE_URL.format(keyword=quote(term))
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    pushes = re.findall(r"self\.__next_f\.push\(\[1,\s*\"(.*?)\"\s*\]\)", resp.text)
                    for p in pushes:
                        if len(results) >= limit:
                            break
                        try:
                            raw = json.loads("\"" + p + "\"")
                        except Exception:
                            raw = p.replace("\\\"", "\"")

                        if "DiscountItemPC_itemTitle" in raw:
                            t_m = re.search(r"DiscountItemPC_itemTitle.*?\"title\":\"(.*?)\"", raw)
                            raw_title = t_m.group(1) if t_m else ""
                            title = self.clean_title(raw_title)
                            if not title or "广告" in title:
                                continue

                            # 1. 过滤配件陷阱
                            if self.is_accessory_trap(title, clean_kw):
                                continue

                            # 2. 价格提取
                            p_m = re.search(r"DiscountItemPC_itemSubTitle.*?children\":\"(.*?)\"", raw)
                            price_str = p_m.group(1) if p_m else ""
                            price = self._extract_price(price_str)
                            if price <= 0:
                                continue

                            # 3. 商城归属
                            m_m = re.search(r"DiscountItemPC_itemMall.*?children\":\"(.*?)\"", raw)
                            raw_mall = m_m.group(1) if m_m else "电商正品"
                            platform_name, platform_key, is_official = self._map_platform(raw_mall)

                            # 4. 标签与链接
                            tag_m = re.search(r"DiscountItemPC_itemTag.*?children\":\"(.*?)\"", raw)
                            tag = tag_m.group(1) if tag_m else price_str

                            img_m = re.search(r"\"src\":\"(.*?)\"", raw)
                            img_url = img_m.group(1) if img_m else ""

                            h_m = re.search(r"\"href\":\"(https://[^\"]+)\"", raw)
                            href = h_m.group(1) if h_m else ""

                            results.append(SearchResult(
                                title=title,
                                platform=platform_name,
                                platform_key=platform_key,
                                item_id="",
                                price=price,
                                final_price=price,
                                discount_tag=tag or "平台优惠活动",
                                url=href or f"https://search.jd.com/Search?keyword={quote(title)}&enc=utf-8",
                                image_url=img_url,
                                shop_name=raw_mall,
                                is_official=is_official
                            ))

                    if results:
                        break
        except Exception as e:
            print(f"[MMBConnector] Search error for '{query}': {e}")

        return results
