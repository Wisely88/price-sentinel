import pytest
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.connectors.base import BaseConnector, SearchResult
from app.services.searcher import SearchService

def test_clean_url_strips_tracking():
    connector = BaseConnector()
    dirty_url = "https://item.jd.com/1000123.html?spm=123.456&utm_source=cps&ref=ad"
    clean = connector.clean_url(dirty_url)
    assert "spm" not in clean
    assert "utm_source" not in clean
    assert "ref" not in clean
    assert clean == "https://item.jd.com/1000123.html"

def test_accessory_trap_detection():
    connector = BaseConnector()
    
    # User searches for iPhone 16 -> accessory should be filtered
    assert connector.is_accessory_trap("Apple iPhone 16 磨砂防摔手机壳", "iPhone 16") is True
    assert connector.is_accessory_trap("iPhone 16 全屏钢化膜超清", "iPhone 16") is True
    assert connector.is_accessory_trap("Apple iPhone 16 128G 全新国行正品", "iPhone 16") is False

    # User intentionally searches for phone case -> should NOT be filtered
    assert connector.is_accessory_trap("iPhone 16 手机壳", "iPhone 16 手机壳") is False

def test_title_cleaning():
    connector = BaseConnector()
    raw = "<font color='red'>【官方直营包邮】</font> 索尼 WH-1000XM5 无线降噪耳机   "
    clean = connector.clean_title(raw)
    assert "<font" not in clean
    assert clean == "索尼 WH-1000XM5 无线降噪耳机"

def test_search_service_aggregation():
    service = SearchService()
    res = asyncio.run(service.search_all("iPad Air 6"))
    
    assert res is not None
    assert "items" in res
    assert "min_price" in res
    assert "max_savings" in res
    
    items = res["items"]
    if items:
        # Check that items are sorted in ascending order of final_price
        for i in range(len(items) - 1):
            assert items[i]["final_price"] <= items[i+1]["final_price"]
        # Lowest item should be marked
        assert items[0]["is_lowest"] is True

def test_spec_extraction():
    connector = BaseConnector()
    assert connector.extract_spec("Apple iPhone 18 Pro 256GB 勃艮第酒红色") == "256GB"
    assert connector.extract_spec("Apple iPhone 18 Pro 512G 冰川蓝") == "512GB"
    assert connector.extract_spec("Apple iPhone 18 Pro Max 1TB 黑色") == "1TB"
    assert connector.extract_spec("Apple iPhone 18 Pro 256手机") == "256GB"
    assert connector.extract_spec("iPhone 16 官方标配 全新国行") == "官方标配"
    assert connector.extract_spec("普通无规格描述商品") == ""

def test_platform_search_url_generation():
    connector = BaseConnector()
    jd_url = connector.get_platform_search_url("jd", "Apple iPhone 18 Pro 256GB")
    assert "search.jd.com" in jd_url
    assert "iPhone" in jd_url

    tb_url = connector.get_platform_search_url("taobao", "Apple iPhone 18 Pro 256GB")
    assert "s.taobao.com" in tb_url

    pdd_url = connector.get_platform_search_url("pdd", "Apple iPhone 18 Pro 256GB")
    assert "yangkeduo.com" in pdd_url

def test_price_extraction_not_tricked_by_installments():
    from app.connectors.smzdm import SMZDMConnector
    from app.connectors.mmb import MMBConnector
    
    smzdm = SMZDMConnector()
    mmb = MMBConnector()

    # Installment strings without currency unit should NEVER be parsed as price
    assert smzdm._extract_price("白条12期免息") == 0.0
    assert mmb._extract_price("白条12期免息 无需抢") == 0.0

    # Proper price patterns should be parsed accurately
    assert smzdm._extract_price("8949元") == 8949.0
    assert smzdm._extract_price("券后8949元") == 8949.0
    assert smzdm._extract_price("到手价8949") == 8949.0
    assert mmb._extract_price("9299.02元+199.98元淘金币（含国补，晒单返20元后到手9279.02元）") == 9279.02

def test_version_detection():
    connector = BaseConnector()
    
    # Trade-in
    is_ti, is_os, is_rf, badge = connector.detect_version("Apple iPhone 18 Pro 以旧换新立减800")
    assert is_ti is True
    assert badge == "需以旧换新"

    # Overseas / US
    is_ti, is_os, is_rf, badge = connector.detect_version("Apple iPhone 17 Pro 美版无锁 256G")
    assert is_os is True
    assert badge == "海外/美版"

    # Refurbished
    is_ti, is_os, is_rf, badge = connector.detect_version("Apple iPhone 16 Pro 99新 官翻二手")
    assert is_rf is True
    assert badge == "二手官翻"

    # Pure National Retail (Digital product)
    is_ti, is_os, is_rf, badge = connector.detect_version("Apple iPhone 18 Pro 256GB 勃艮第酒红色 国行正品双卡", "iPhone 18 Pro")
    assert is_ti is False
    assert is_os is False
    assert is_rf is False
    assert badge == "国行全新"

    # Non-digital regular product (e.g. coffee beans, tissue paper, shampoo) -> should NOT be 国行全新
    is_ti, is_os, is_rf, badge = connector.detect_version("菲诺 花魁SOE埃塞俄比亚日晒G1咖啡豆200g", "咖啡豆")
    assert badge == ""

    # Non-digital imported product -> should be 原装进口
    is_ti, is_os, is_rf, badge = connector.detect_version("A2 澳大利亚原装进口全脂纯牛奶 1L*6箱装", "纯牛奶")
    assert badge == "原装进口"

def test_search_result_is_ended_field():
    item = SearchResult(
        title="Apple iPhone 16 Pro Max 256GB",
        platform="京东自营",
        platform_key="jd",
        item_id="10001",
        price=8999.0,
        final_price=7999.0,
        discount_tag="历史特惠参考",
        url="https://item.jd.com/10001.html",
        image_url="",
        shop_name="京东自营",
        is_ended=True
    )
    assert item.is_ended is True
    service = SearchService()
    serialized = service._serialize_result(item)
    assert serialized["is_ended"] is True
    assert serialized["final_price"] == 7999.0


