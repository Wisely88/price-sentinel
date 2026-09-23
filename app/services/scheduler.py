"""
Background Price Sentinel Scheduler / 后台降价巡检调度器
Periodically checks monitored items via APScheduler and triggers multi-channel alerts upon price drops.
使用 APScheduler 定时自动轮询监控列表中的商品，并在检测到破价或新优惠时触发多通道推送。
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from typing import Dict, Any

from app.database import (
    get_favorites, 
    get_favorite_by_id, 
    update_favorite_price, 
    get_setting,
    get_all_settings
)
from app.services.notifier import NotifierService
from app.connectors.jd import JDConnector
from app.connectors.taobao import TaobaoConnector
from app.connectors.pdd import PDDConnector

class PriceSchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.connectors = {
            "jd": JDConnector(),
            "taobao": TaobaoConnector(),
            "pdd": PDDConnector()
        }
        self.is_running = False

    def start(self):
        """Start the background scheduler."""
        if not self.is_running:
            interval_hours = int(get_setting("check_interval_hours", "4"))
            self.scheduler.add_job(
                self.check_all_favorites,
                trigger=IntervalTrigger(hours=max(1, interval_hours)),
                id="price_check_job",
                replace_existing=True
            )
            self.scheduler.start()
            self.is_running = True
            print(f"[Scheduler] Started with check interval: {interval_hours} hours")

    def update_interval(self, hours: int):
        """Update job interval dynamically."""
        if self.scheduler.get_job("price_check_job"):
            self.scheduler.reschedule_job(
                "price_check_job",
                trigger=IntervalTrigger(hours=max(1, hours))
            )
            print(f"[Scheduler] Rescheduled to every {hours} hours")

    async def check_single_favorite(self, fav: Dict[str, Any]) -> Dict[str, Any]:
        """Check price for a single favorite item and trigger notification if dropped."""
        fav_id = fav["id"]
        title = fav["title"]
        current_price = fav["current_price"]
        target_price = fav.get("target_price")
        platform_key = fav.get("platform")
        if platform_key in ["京东", "jd"]:
            connector = self.connectors.get("jd")
        elif platform_key in ["淘宝", "天猫", "taobao"]:
            connector = self.connectors.get("taobao")
        else:
            connector = self.connectors.get("pdd") or self.connectors.get("jd")

        if not connector:
            return {"status": "error", "message": "Unknown connector"}

        try:
            # Query the platform with item title
            items = await connector.search(title, limit=3)
            if not items:
                return {"status": "skipped", "message": "No search results"}

            best_match = items[0]
            new_price = best_match.final_price
            discount_tag = best_match.discount_tag

            price_dropped = new_price < current_price
            target_reached = bool(target_price and new_price <= target_price)

            # Update DB with latest price
            update_favorite_price(fav_id, new_price, discount_tag)

            # Trigger notification
            should_notify = price_dropped or target_reached
            if should_notify:
                diff = round(current_price - new_price, 2)
                diff_str = f"降价 ¥{diff}" if price_dropped else f"达到期望心理价 (¥{target_price})"
                body = (
                    f"【{fav['platform']}】当前最新到手价: ¥{new_price} ({diff_str})\n"
                    f"活动优惠: {discount_tag or '官方优惠'}"
                )
                await NotifierService.notify_all(
                    title=title,
                    body=body,
                    url=fav.get("url") or best_match.url
                )

            return {
                "status": "success",
                "old_price": current_price,
                "new_price": new_price,
                "notified": should_notify
            }
        except Exception as e:
            print(f"[Scheduler] Error checking favorite #{fav_id} ({title}): {e}")
            return {"status": "error", "message": str(e)}

    async def check_all_favorites(self):
        """Scheduled task to inspect all active favorites."""
        print(f"[Scheduler] Running price inspection: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        favorites = get_favorites(active_only=True)
        for fav in favorites:
            await self.check_single_favorite(fav)
            # Gentle delay between requests to avoid burst rate
            await asyncio.sleep(2)

# Global singleton
scheduler_service = PriceSchedulerService()
