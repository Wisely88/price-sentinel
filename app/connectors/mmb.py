"""
MMB Connector / 全网好价连接器
Provides multi-page Next.js push hydration stream parsing, mall mapping, and promo extraction.
解析全网好价 Next.js push 数据流，支持跨电商商城归属映射与实时优惠解析。
"""

import httpx
import asyncio
import re
import json
from typing import List
from urllib.parse import quote
from .base import BaseConnector, SearchResult
from config import DEFAULT_TIMEOUT, USER_AGENT

class MMBConnector(BaseConnector):
    name = "全网好价"
    platform_key = "mmb"

    BASE_URL = "https://s.manmanbuy.com/Default.aspx?key={keyword}"
    PAGE_URL = "https://s.manmanbuy.com/pc/search/result?keyword={keyword}&c=discount&pageId={page}"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://s.manmanbuy.com/",
    }

    def _extract_price(self, raw_price_str: str) -> float:
        if not raw_price_str:
            return 0.0
        # Check "后xxx" or "到手价xxx"
        match_after = re.search(r"(?:补贴后|券后|折后|到手|到手价|实付|低至)\s*[:：]?\s*[¥￥]?\s*(\d+(?:\.\d+)?)", raw_price_str)
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
            return mall or "电商正品", "other", False

    async def search(self, query: str, limit: int = 50) -> List[SearchResult]:
        results: List[SearchResult] = []
        clean_kw = query.strip()
        if not clean_kw:
            return results

        # Construct target URLs across pages and variations
        target_urls = [
            self.PAGE_URL.format(keyword=quote(clean_kw), page=1)
        ]
        if limit > 20:
            target_urls.append(self.PAGE_URL.format(keyword=quote(clean_kw), page=2))
        if " " in clean_kw:
            no_space_kw = clean_kw.replace(" ", "")
            target_urls.append(self.PAGE_URL.format(keyword=quote(no_space_kw), page=1))
        target_urls.append(self.BASE_URL.format(keyword=quote(clean_kw)))

        seen_hrefs = set()

        try:
            async with httpx.AsyncClient(headers=self.HEADERS, timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
                tasks = [client.get(u) for u in target_urls]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                for resp in responses:
                    if isinstance(resp, Exception) or resp.status_code != 200:
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
                            h_m = re.search(r"\"href\":\"(https://[^\"]+)\"", raw)
                            href = h_m.group(1) if h_m else ""
                            if href and href in seen_hrefs:
                                continue
                            if href:
                                seen_hrefs.add(href)

                            t_m = re.search(r"DiscountItemPC_itemTitle.*?\"title\":\"(.*?)\"", raw)
                            raw_title = t_m.group(1) if t_m else ""
                            title = self.clean_title(raw_title)
                            
                            # 1. 检测是否为已结束活动（保留近期好价作为比价基准参考，避免0搜索结果）
                            is_ended = ("DiscountItemPC_itemOver" in raw or "已结束" in raw or "已失效" in raw or "已售罄" in raw)
                            if not title or "广告" in title:
                                continue
                            if title.startswith("促销活动") or "速抢" in title or "会场" in title:
                                continue

                            # 2. 过滤配件陷阱
                            if self.is_accessory_trap(title, clean_kw):
                                continue

                            # 3. 价格提取与格式验证
                            p_m = re.search(r"DiscountItemPC_itemSubTitle.*?children\":\"(.*?)\"", raw)
                            price_str = p_m.group(1) if p_m else ""
                            price = self._extract_price(price_str)
                            if price <= 0:
                                continue

                            # 价格下限保护（主设备不应低于50元）
                            main_indicators = ["iphone", "ipad", "手机", "相机", "显卡", "笔记本", "电视", "冰箱", "洗衣机"]
                            if any(m in clean_kw.lower() for m in main_indicators) and price < 50:
                                continue

                            # 4. 商城归属
                            m_m = re.search(r"DiscountItemPC_itemMall.*?children\":\"(.*?)\"", raw)
                            raw_mall = m_m.group(1) if m_m else "电商正品"
                            platform_name, platform_key, is_official = self._map_platform(raw_mall)

                            # 5. 版本与换新检测 (美版/海外版/以旧换新/二手)
                            is_trade_in, is_overseas, is_refurbished, version_badge = self.detect_version(title + " " + price_str + " " + raw, clean_kw)

                            # 6. SKU 规格提取
                            spec = self.extract_spec(title) or self.extract_spec(price_str)

                            # 7. 价格生效条件/优惠说明提取
                            notes = []
                            if is_ended:
                                notes.append("近期好价(活动已结束)")
                            if is_trade_in:
                                notes.append("需以旧换新")
                            if is_overseas:
                                notes.append("海外/美版")
                            if is_refurbished:
                                notes.append("二手官翻")
                            if "国补" in price_str or "国家补贴" in price_str:
                                notes.append("含国补")
                            elif "补贴" in price_str:
                                notes.append("含补贴")
                            if "淘金币" in price_str:
                                notes.append("需淘金币")
                            if "需用券" in price_str or "券后" in price_str or "用券" in price_str:
                                notes.append("需领券")
                            if "晒单返" in price_str or "返卡" in price_str:
                                notes.append("含晒单返")
                            if spec:
                                notes.append(f"{spec}规格")
                            else:
                                notes.append("配置实选为准")
                            price_note = " · ".join(notes)

                            # 8. 标签与链接
                            tag_m = re.search(r"DiscountItemPC_itemTag.*?children\":\"(.*?)\"", raw)
                            tag = tag_m.group(1) if tag_m else price_str
                            if is_ended:
                                tag = tag or "历史特惠参考"

                            time_m = re.search(r"DiscountItemPC_itemTime.*?children\":\"(.*?)\"", raw)
                            pub_time = time_m.group(1) if time_m else ""

                            img_m = re.search(r"\"src\":\"(.*?)\"", raw)
                            img_url = img_m.group(1) if img_m else ""

                            h_m = re.search(r"\"href\":\"(https://[^\"]+)\"", raw)
                            href = h_m.group(1) if h_m else ""

                            platform_search_url = self.get_platform_search_url(platform_key, title)

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

                    if results:
                        break
        except Exception as e:
            print(f"[MMBConnector] Search error for '{query}': {e}")

        return results
