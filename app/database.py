"""
Database Layer / 数据库持久化层
Manages SQLite storage for monitored favorites, historical price tracking, and system alert settings.
管理 SQLite 数据库存储，包含商品降价监控清单、历史价格走势记录及系统告警通知配置。
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from config import DB_PATH

def get_db():
    """Get database connection with dict-like row access / 获取支持字典式访问的数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables / 初始化数据库数据表结构"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Favorites Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                platform TEXT NOT NULL,
                item_id TEXT,
                url TEXT NOT NULL,
                image_url TEXT,
                initial_price REAL NOT NULL,
                target_price REAL,
                current_price REAL NOT NULL,
                discount_info TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Price History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                favorite_id INTEGER NOT NULL,
                price REAL NOT NULL,
                discount_info TEXT DEFAULT '',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (favorite_id) REFERENCES favorites (id) ON DELETE CASCADE
            )
        """)
        
        # 3. Settings Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Default Settings
        default_settings = {
            "check_interval_hours": "4",
            "bark_key": "",
            "webhook_url": "",
            "enable_mac_notify": "1",
            "price_drop_only": "1"  # 1: 仅降价推送, 0: 每次巡检若有优惠都推送
        }
        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
            
        conn.commit()

# --- Favorite Operations ---

def add_favorite(
    title: str,
    platform: str,
    url: str,
    current_price: float,
    target_price: Optional[float] = None,
    item_id: Optional[str] = None,
    image_url: Optional[str] = None,
    discount_info: str = ""
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO favorites (title, platform, item_id, url, image_url, initial_price, target_price, current_price, discount_info, is_active, created_at, updated_at, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (title, platform, item_id or "", url, image_url or "", current_price, target_price, current_price, discount_info, now, now, now))
        fav_id = cursor.lastrowid
        
        # Record initial price in history
        cursor.execute("""
            INSERT INTO price_history (favorite_id, price, discount_info, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (fav_id, current_price, discount_info, now))
        conn.commit()
        return fav_id

def get_favorites(active_only: bool = False) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM favorites"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id DESC"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_favorite_by_id(fav_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM favorites WHERE id = ?", (fav_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_favorite_price(fav_id: int, new_price: float, discount_info: str = ""):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE favorites 
            SET current_price = ?, discount_info = ?, updated_at = ?, last_checked_at = ?
            WHERE id = ?
        """, (new_price, discount_info, now, now, fav_id))
        
        # Append to price history
        cursor.execute("""
            INSERT INTO price_history (favorite_id, price, discount_info, recorded_at)
            VALUES (?, ?, ?, ?)
        """, (fav_id, new_price, discount_info, now))
        conn.commit()

def update_favorite_target_price(fav_id: int, target_price: Optional[float]):
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE favorites SET target_price = ?, updated_at = ? WHERE id = ?
        """, (target_price, now, fav_id))
        conn.commit()

def toggle_favorite_active(fav_id: int, is_active: bool):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE favorites SET is_active = ? WHERE id = ?", (1 if is_active else 0, fav_id))
        conn.commit()

def delete_favorite(fav_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
        cursor.execute("DELETE FROM price_history WHERE id = ?", (fav_id,))
        conn.commit()

def get_price_history(favorite_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT price, discount_info, recorded_at 
            FROM price_history 
            WHERE favorite_id = ? 
            ORDER BY recorded_at ASC LIMIT ?
        """, (favorite_id, limit))
        return [dict(row) for row in cursor.fetchall()]

# --- Settings Operations ---

def get_all_settings() -> Dict[str, str]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}

def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

def update_settings(settings: Dict[str, str]):
    with get_db() as conn:
        cursor = conn.cursor()
        for k, v in settings.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        conn.commit()
