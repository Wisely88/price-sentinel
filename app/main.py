from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from pathlib import Path

from config import BASE_DIR
from app.database import (
    init_db,
    add_favorite,
    get_favorites,
    get_favorite_by_id,
    update_favorite_target_price,
    toggle_favorite_active,
    delete_favorite,
    get_price_history,
    get_all_settings,
    update_settings
)
from app.services.searcher import SearchService
from app.services.scheduler import scheduler_service
from app.services.notifier import NotifierService

search_service = SearchService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and start scheduler
    init_db()
    scheduler_service.start()
    yield
    # Shutdown
    if scheduler_service.scheduler.running:
        scheduler_service.scheduler.shutdown()

app = FastAPI(
    title="PriceSentinel API",
    description="Ad-free Cross-Platform Price Comparison & Sentinel Service",
    version="1.0.0",
    lifespan=lifespan
)

# --- Pydantic Request Models ---

class AddFavoriteRequest(BaseModel):
    title: str = Field(..., description="商品名称")
    platform: str = Field(..., description="平台名称，如 京东、天猫、拼多多")
    url: str = Field(..., description="商品直达购买链接")
    current_price: float = Field(..., description="当前检测价格")
    target_price: Optional[float] = Field(None, description="期望降价通知心理价")
    item_id: Optional[str] = Field(None, description="商品SKU/ID")
    image_url: Optional[str] = Field(None, description="商品缩略图")
    discount_info: Optional[str] = Field("", description="优惠活动标签")

class UpdateFavoriteRequest(BaseModel):
    target_price: Optional[float] = None
    is_active: Optional[bool] = None

class SettingsUpdateRequest(BaseModel):
    check_interval_hours: Optional[str] = None
    bark_key: Optional[str] = None
    webhook_url: Optional[str] = None
    enable_mac_notify: Optional[str] = None
    price_drop_only: Optional[str] = None

# --- API Endpoints ---

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "PriceSentinel", "version": "1.0.0"}

@app.get("/api/search")
async def search(
    q: str = Query(..., description="搜索关键词"),
    platforms: Optional[str] = Query(None, description="逗号分隔的平台列表: jd,taobao,pdd")
):
    target_platforms = [p.strip() for p in platforms.split(",")] if platforms else None
    results = await search_service.search_all(query=q, platforms=target_platforms)
    return results

@app.get("/api/favorites")
def list_favorites():
    return {"items": get_favorites()}

@app.post("/api/favorites")
def create_favorite(req: AddFavoriteRequest):
    fav_id = add_favorite(
        title=req.title,
        platform=req.platform,
        url=req.url,
        current_price=req.current_price,
        target_price=req.target_price,
        item_id=req.item_id,
        image_url=req.image_url,
        discount_info=req.discount_info or ""
    )
    return {"status": "success", "id": fav_id}

@app.put("/api/favorites/{fav_id}")
def modify_favorite(fav_id: int, req: UpdateFavoriteRequest):
    fav = get_favorite_by_id(fav_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    if req.target_price is not None:
        update_favorite_target_price(fav_id, req.target_price)
    if req.is_active is not None:
        toggle_favorite_active(fav_id, req.is_active)
    
    return {"status": "success"}

@app.delete("/api/favorites/{fav_id}")
def remove_favorite(fav_id: int):
    fav = get_favorite_by_id(fav_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    delete_favorite(fav_id)
    return {"status": "success"}

@app.post("/api/favorites/{fav_id}/check")
async def check_favorite(fav_id: int):
    fav = get_favorite_by_id(fav_id)
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    res = await scheduler_service.check_single_favorite(fav)
    return res

@app.get("/api/favorites/{fav_id}/history")
def favorite_history(fav_id: int):
    return {"history": get_price_history(fav_id)}

@app.get("/api/settings")
def read_settings():
    return get_all_settings()

@app.post("/api/settings")
def save_settings(req: SettingsUpdateRequest):
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    update_settings(update_data)
    
    if "check_interval_hours" in update_data:
        try:
            scheduler_service.update_interval(int(update_data["check_interval_hours"]))
        except Exception:
            pass

    return {"status": "success", "settings": get_all_settings()}

@app.post("/api/notify/test")
async def test_notify():
    results = await NotifierService.notify_all(
        title="PriceSentinel 测试通知",
        body="恭喜！您的降价提醒通道已成功联通。当收藏商品发生降价或满减时，您将第一时间收到提醒！",
        url="http://127.0.0.1:8765"
    )
    return {"status": "success", "results": results}

# --- Static Frontend Serving ---
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    return FileResponse(str(static_dir / "index.html"))
