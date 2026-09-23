import pytest
import asyncio
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_settings_flow():
    res = client.get("/api/settings")
    assert res.status_code == 200
    settings = res.json()
    assert "enable_mac_notify" in settings

    # Post update
    res_update = client.post("/api/settings", json={"check_interval_hours": "2"})
    assert res_update.status_code == 200
    assert res_update.json()["settings"]["check_interval_hours"] == "2"

def test_favorites_api():
    # Create favorite
    fav_payload = {
        "title": "索尼 WH-1000XM5 无线降噪耳机 黑色",
        "platform": "京东",
        "url": "https://item.jd.com/100021674211.html",
        "current_price": 2299.00,
        "target_price": 1999.00,
        "discount_info": "满2000减200"
    }
    create_res = client.post("/api/favorites", json=fav_payload)
    assert create_res.status_code == 200
    fav_id = create_res.json()["id"]

    # List favorites
    list_res = client.get("/api/favorites")
    assert list_res.status_code == 200
    favs = list_res.json()["items"]
    assert any(f["id"] == fav_id for f in favs)

    # Test notify test endpoint
    notify_res = client.post("/api/notify/test")
    assert notify_res.status_code == 200

    # Clean up favorite
    del_res = client.delete(f"/api/favorites/{fav_id}")
    assert del_res.status_code == 200

def test_search_api_structure():
    # Test search endpoint returns expected data structures
    res = client.get("/api/search?q=iPhone&only_national=true")
    assert res.status_code == 200
    data = res.json()
    assert "total_count" in data
    assert "items" in data
    assert "available_specs" in data
    assert "direct_channels" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["available_specs"], list)
