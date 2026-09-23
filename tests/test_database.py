import pytest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import (
    init_db,
    add_favorite,
    get_favorites,
    update_favorite_price,
    delete_favorite,
    get_price_history,
    get_all_settings,
    update_settings
)

def test_database_crud():
    init_db()
    
    # Add favorite
    fav_id = add_favorite(
        title="测试商品 iPad Pro M4",
        platform="京东",
        url="https://item.jd.com/test.html",
        current_price=8999.00,
        target_price=8500.00,
        discount_info="满8000减500"
    )
    assert fav_id is not None
    assert fav_id > 0

    # Retrieve favorites
    favs = get_favorites()
    found = [f for f in favs if f["id"] == fav_id]
    assert len(found) == 1
    assert found[0]["current_price"] == 8999.00
    assert found[0]["target_price"] == 8500.00

    # Update price
    update_favorite_price(fav_id, 8499.00, "限时降价")
    favs_updated = get_favorites()
    found_updated = [f for f in favs_updated if f["id"] == fav_id][0]
    assert found_updated["current_price"] == 8499.00

    # Check history
    history = get_price_history(fav_id)
    assert len(history) >= 2  # initial + updated
    assert history[-1]["price"] == 8499.00

    # Delete favorite
    delete_favorite(fav_id)
    favs_after_del = get_favorites()
    assert not any(f["id"] == fav_id for f in favs_after_del)

def test_settings_operations():
    init_db()
    update_settings({"test_key": "test_val", "bark_key": "my_sample_bark_key"})
    settings = get_all_settings()
    assert settings.get("test_key") == "test_val"
    assert settings.get("bark_key") == "my_sample_bark_key"
