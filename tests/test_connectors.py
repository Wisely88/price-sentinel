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
