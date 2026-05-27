"""
自选股收藏模块
==============
使用 SQLite 本地存储，文件位于 ~/.quant-favorites.db。
提供添加、删除、查询自选股功能，支持获取实时的最新价和涨跌幅。
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from screener.hikyuu_adapter import sm, Query

DB_PATH = os.path.join(str(Path.home()), ".quant-favorites.db")


def _get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接，自动建表。"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


def add_favorite(code: str, name: str) -> bool:
    """
    添加自选股。

    Parameters
    ----------
    code : str
        股票代码，如 'SZ000001'。
    name : str
        股票名称。

    Returns
    -------
    bool
        成功返回 True，已存在返回 False。
    """
    try:
        conn = _get_connection()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT OR IGNORE INTO favorites (code, name, added_at) VALUES (?, ?, ?)",
            (code, name, now),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def remove_favorite(code: str) -> bool:
    """
    移除自选股。

    Parameters
    ----------
    code : str
        股票代码。

    Returns
    -------
    bool
        成功返回 True。
    """
    try:
        conn = _get_connection()
        conn.execute("DELETE FROM favorites WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def is_favorite(code: str) -> bool:
    """
    检查股票是否在自选列表中。

    Parameters
    ----------
    code : str
        股票代码。

    Returns
    -------
    bool
    """
    try:
        conn = _get_connection()
        cursor = conn.execute("SELECT 1 FROM favorites WHERE code = ?", (code,))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    except Exception:
        return False


def get_favorites() -> list[dict]:
    """
    获取所有自选股列表，含最新价和涨跌幅。

    Returns
    -------
    list[dict]
        [{
            "code": str, "name": str, "added_at": str,
            "latest_price": float, "pct_change": float, "volume": int
        }, ...]
    """
    try:
        conn = _get_connection()
        cursor = conn.execute("SELECT code, name, added_at FROM favorites ORDER BY added_at DESC")
        rows = cursor.fetchall()
        conn.close()
    except Exception:
        return []

    results = []
    for row in rows:
        code = row["code"]
        info = _fetch_live_info(code)
        results.append({
            "code": code,
            "name": row["name"],
            "added_at": row["added_at"],
            "latest_price": info["latest_price"] if info else None,
            "pct_change": info["pct_change"] if info else None,
            "volume": info["volume"] if info else None,
        })
    return results


def _fetch_live_info(code: str) -> Optional[dict]:
    """
    获取单只股票的最新价格、涨跌幅、成交量。

    Parameters
    ----------
    code : str
        股票代码。

    Returns
    -------
    dict or None
        {"latest_price": float, "pct_change": float, "volume": int}
    """
    try:
        s = sm[code]
    except Exception:
        return None

    if s is None or not s.valid:
        return None

    try:
        k = s.get_kdata(Query(-2))
    except Exception:
        return None

    if len(k) < 1:
        return None

    cur = float(k[-1].close)
    volume = int(k[-1].volume)

    pct_change = 0.0
    if len(k) >= 2:
        prev = float(k[0].close)
        if prev > 0:
            pct_change = round((cur / prev - 1.0) * 100.0, 2)

    return {
        "latest_price": round(cur, 2),
        "pct_change": pct_change,
        "volume": volume,
    }
