from dataclasses import dataclass
from typing import Optional, List
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

@dataclass
class SearchResult:
    title: str
    platform: str
    platform_key: str
    item_id: str
    price: float
    final_price: float
    discount_tag: str
    url: str
    image_url: str
    shop_name: str
    is_official: bool = False
    is_lowest: bool = False

class BaseConnector:
    name: str = "Base"
    platform_key: str = "base"

    # Common words used to scam/trap search results with cheap accessories
    ACCESSORY_TRAPS = [
        "手机壳", "保护套", "钢化膜", "水凝膜", "贴膜", "防窥膜", 
        "镜头膜", "保护壳", "防摔壳", "转接头", "数据线", "充电器", 
        "耳机包", "防尘塞", "收纳盒", "支架", "定金", "专拍", "补差价", 
        "样品", "配件", "体验装", "零件", "内胆包", "快充线", "抗菌壳",
        "支点壳", "磁吸壳", "素皮壳", "保护膜", "壳", "膜", "套", "线"
    ]

    # Tracking parameters to strip from URLs
    TRACKING_PARAMS = {
        "spm", "scm", "pvid", "source", "utm_source", "utm_medium", 
        "utm_campaign", "union_id", "cps", "cps_id", "click_id",
        "tag", "ref", "ali_trackid", "pos", "p_pos", "ad_id"
    }

    def clean_url(self, raw_url: str) -> str:
        """Strip tracking and marketing parameters, leaving a pure direct link."""
        if not raw_url:
            return ""
        if raw_url.startswith("//"):
            raw_url = "https:" + raw_url
        try:
            parsed = urlparse(raw_url)
            query_dict = parse_qs(parsed.query)
            clean_query = {k: v for k, v in query_dict.items() if k.lower() not in self.TRACKING_PARAMS}
            new_query = urlencode(clean_query, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))
        except Exception:
            return raw_url

    def is_accessory_trap(self, title: str, query: str) -> bool:
        """
        Check if the item is an accessory trick.
        If user explicitly asks for '壳' or '膜', don't filter.
        Otherwise, if the user searched for a main device, filter out accessories.
        """
        query_lower = query.lower()
        title_lower = title.lower()

        # If user intentionally searched for an accessory, do not drop
        for trap in ["壳", "膜", "套", "线", "包", "支架", "充电器"]:
            if trap in query_lower:
                return False

        # If query seems to be a main product (e.g. phone, pad, camera, appliance)
        main_indicators = ["iphone", "ipad", "手机", "相机", "显卡", "笔记本", "电视", "冰箱", "洗衣机", "耳机", "手表", "音箱", "air", "pro"]
        is_query_main_device = any(ind in query_lower for ind in main_indicators)
        
        if is_query_main_device:
            for trap in self.ACCESSORY_TRAPS:
                if trap in title_lower:
                    return True
        return False

    def clean_title(self, raw_title: str) -> str:
        """Strip HTML tags and excessive promotional noise."""
        clean = re.sub(r"<[^>]+>", "", raw_title)
        clean = re.sub(r"【[^】]*包邮[^】]*】", "", clean)
        clean = re.sub(r"【[^】]*爆款[^】]*】", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        raise NotImplementedError
