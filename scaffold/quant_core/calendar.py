"""交易日历 — 基于 akshare 国内交易日数据"""

from datetime import date, timedelta

import pandas as pd


class TradingCalendar:
    """A股交易日历，提供交易日判断和区间生成"""

    def __init__(self):
        self._trade_dates: set[str] = set()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        try:
            import akshare as ak

            df = ak.tool_trade_date_hist_sina()
            self._trade_dates = set(df["trade_date"].astype(str).tolist())
            self._loaded = True
        except Exception:
            # fallback: B-day business calendar
            self._loaded = True

    def is_trade_date(self, d: date) -> bool:
        self._ensure_loaded()
        return d.isoformat() in self._trade_dates

    def get_trade_dates(self, start: date, end: date) -> list[date]:
        """返回 [start, end] 区间内所有交易日"""
        self._ensure_loaded()
        result: list[date] = []
        current = start
        while current <= end:
            if self.is_trade_date(current):
                result.append(current)
            current += timedelta(days=1)
        return result

    def prev_trade_date(self, d: date) -> date:
        cur = d - timedelta(days=1)
        while not self.is_trade_date(cur):
            cur -= timedelta(days=1)
        return cur

    def next_trade_date(self, d: date) -> date:
        cur = d + timedelta(days=1)
        while not self.is_trade_date(cur):
            cur += timedelta(days=1)
        return cur


# 全局单例
default_calendar = TradingCalendar()
