"""
Base Connector & Defense Engine / 基础连接器与防坑引擎
Provides pure URL cleaning, accessory trap detection, category-aware version tagging,
and SKU spec extraction.
提供纯净直达链接清洗、配件低价陷阱识别、品类感知版本标注及 SKU 规格解析。
"""

from dataclasses import dataclass
from typing import Optional, List
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

@dataclass
class SearchResult:
    """Standardized cross-platform item model / 标准化跨平台商品模型"""
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
    spec: str = ""
    price_note: str = ""
    publish_time: str = ""
    platform_search_url: str = ""
    is_trade_in: bool = False
    is_overseas: bool = False
    is_refurbished: bool = False
    version_badge: str = ""

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

    def extract_spec(self, text: str) -> str:
        """Extract SKU specs such as capacity, memory, color, or bundle model."""
        if not text:
            return ""
        # 1. Capacity / RAM pattern: e.g. 128GB, 256GB, 512GB, 1TB, 16G+512G, 8+256
        cap_match = re.search(r"(\b\d{1,2}\s*(?:\+\s*\d{2,4})?\s*(?:GB|G|TB|T)\b)", text, re.IGNORECASE)
        if cap_match:
            return cap_match.group(1).upper().replace(" ", "")
        
        # 2. Chinese spec notations: e.g. 128G, 256G, 512G, 1T
        cn_cap_match = re.search(r"((?:128|256|512)\s*[Gg]|\b[12]\s*[Tt]\b)", text)
        if cn_cap_match:
            val = cn_cap_match.group(1).upper().replace(" ", "")
            return val if "B" in val else val + "B"

        # 3. Plain storage numbers followed by spec keywords, avoiding price/installment collisions
        num_cap_match = re.search(r"\b(128|256|512|1024)\s*(?:GB|G|TB|T|手机|机型|版本|内存|配置|国行|标配)(?![元块期折人天点倍])", text, re.IGNORECASE)
        if num_cap_match and num_cap_match.group(1):
            val = num_cap_match.group(1)
            return "1TB" if val == "1024" else f"{val}GB"

        if "官方标配" in text:
            return "官方标配"
        return ""

    def get_platform_search_url(self, platform_key: str, title: str) -> str:
        """Generate platform-specific direct search URL for live in-stock verification."""
        from urllib.parse import quote
        # Clean title to extract key product name for searching
        clean_kw = re.sub(r"【.*?】", " ", title)
        clean_kw = re.sub(r"\[.*?\]", " ", clean_kw)
        clean_kw = " ".join(clean_kw.split()[:4])
        enc = quote(clean_kw)

        if platform_key == "jd":
            return f"https://search.jd.com/Search?keyword={enc}&enc=utf-8"
        elif platform_key == "taobao":
            return f"https://s.taobao.com/search?q={enc}"
        elif platform_key == "pdd":
            return f"https://mobile.yangkeduo.com/search_result.html?search_key={enc}"
        elif platform_key == "vip":
            return f"https://category.vip.com/suggest.php?keyword={enc}"
        else:
            return f"https://search.jd.com/Search?keyword={enc}&enc=utf-8"

    def clean_title(self, raw_title: str) -> str:
        """Strip HTML tags and excessive promotional noise."""
        clean = re.sub(r"<[^>]+>", "", raw_title)
        # Strip marketing prefixes
        clean = re.sub(r"^闭眼买[、，]?再降价[：:]\s*", "", clean)
        clean = re.sub(r"^再降价[：:]\s*", "", clean)
        clean = re.sub(r"^降价[：:]\s*", "", clean)
        clean = re.sub(r"^爆料[：:]\s*", "", clean)
        clean = re.sub(r"【[^】]*包邮[^】]*】", "", clean)
        clean = re.sub(r"【[^】]*爆款[^】]*】", "", clean)
        clean = re.sub(r"【[^】]*需当面签收[^】]*】", "", clean)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    DIGITAL_KEYWORDS = [
        "iphone", "ipad", "mac", "apple", "watch", "airpods", "手机", "平板", 
        "笔记本", "电脑", "主机", "显卡", "cpu", "主板", "相机", "镜头", "无人机", 
        "耳机", "音箱", "音响", "电视", "冰箱", "洗衣机", "空调", "switch", "ps5", 
        "xbox", "掌机", "投影", "显示器", "华为", "小米", "oppo", "vivo", "荣耀", 
        "三星", "索尼", "大疆", "华硕", "联想", "戴尔", "惠普", "宏碁", "微星", "佳能", "尼康", "富士"
    ]

    def is_digital_product(self, text: str) -> bool:
        if not text:
            return False
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.DIGITAL_KEYWORDS)

    def detect_version(self, text: str, query: str = "") -> tuple[bool, bool, bool, str]:
        """
        Detect if an item requires trade-in, is an overseas grey-market version, or is refurbished.
        Only displays '国行全新' for digital/electronic products.
        Returns: (is_trade_in, is_overseas, is_refurbished, version_badge)
        """
        if not text:
            return False, False, False, ""
        
        text_lower = text.lower()
        is_digital = self.is_digital_product(query) or self.is_digital_product(text)

        # 1. Trade-in detection
        trade_in_keywords = ["以旧换新", "换新补贴", "旧机抵扣", "需寄回旧机", "寄旧机", "回收补贴", "回收返", "换新再补贴"]
        is_trade_in = any(kw in text_lower for kw in trade_in_keywords)

        # 2. Overseas non-national-bank detection
        overseas_keywords = [
            "美版", "美行", "日版", "日行", "港版", "港行", "韩版", "欧版", 
            "海外版", "海外购", "全球购", "水货", "卡贴", "有锁", "无锁版", 
            "att", "verizon", "t-mobile", "us版", "美版无锁"
        ]
        is_overseas = any(kw in text_lower for kw in overseas_keywords)

        # 3. Refurbished / Second-hand detection
        refurbished_keywords = [
            "二手", "官翻", "99新", "95新", "9成新", "85新", 
            "拆封机", "展示机", "资源机", "激活机", "翻新", "充新", "后压屏"
        ]
        is_refurbished = any(kw in text_lower for kw in refurbished_keywords)

        # 4. Category-aware Badge Generation
        if is_digital:
            if is_trade_in:
                badge = "需以旧换新"
            elif is_overseas:
                badge = "海外/美版"
            elif is_refurbished:
                badge = "二手官翻"
            else:
                badge = "国行全新"
        else:
            # General consumer goods (food, clothes, coffee, toiletries, etc.)
            if is_trade_in:
                badge = "需以旧换新"
            elif is_refurbished:
                badge = "二手转让"
            elif any(k in text_lower for k in ["原装进口", "海外购", "全球购", "跨境", "保税仓", "直邮", "海淘"]):
                badge = "原装进口"
            else:
                badge = ""  # Plain regular good, no version badge

        return is_trade_in, is_overseas, is_refurbished, badge

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        raise NotImplementedError
