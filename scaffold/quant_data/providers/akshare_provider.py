"""akshare 数据提供者 — 已验证可用的 A 股 + 期货数据接口"""

from datetime import date, timedelta
from typing import Optional

import pandas as pd


class AkshareProvider:
    """封装 akshare，提供统一的数据获取接口"""

    # ========== A股 ==========

    @staticmethod
    def get_stock_list() -> pd.DataFrame:
        """获取全部A股代码和名称"""
        import akshare as ak
        df = ak.stock_info_a_code_name()
        df.columns = ["code", "name"]
        return df

    @staticmethod
    def get_stock_daily(
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """
        获取A股日K线（前复权）
        adjust: qfq=前复权, hfq=后复权, bfq=不复权
        """
        import akshare as ak

        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date or "19900101",
            end_date=end_date or date.today().strftime("%Y%m%d"),
            adjust=adjust,
        )
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.rename(columns={
            "日期": "date",
            "股票代码": "code",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover",
        })
        return df.sort_values("date")

    @staticmethod
    def get_index_daily(
        symbol: str = "sh000300",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取指数日K线。symbol: sh000300=沪深300, sh000001=上证, sz399001=深证"""
        import akshare as ak

        df = ak.stock_zh_index_daily_em(symbol=symbol)
        df["date"] = pd.to_datetime(df["date"])
        if start_date:
            df = df[df["date"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["date"] <= pd.Timestamp(end_date)]
        return df.sort_values("date").reset_index(drop=True)

    # ========== 期货 ==========

    @staticmethod
    def get_futures_daily(symbol: str) -> pd.DataFrame:
        """
        获取期货主力连续日K线。
        symbol: RB0=螺纹钢, I0=铁矿石, FG0=玻璃, MA0=甲醇, etc.
        """
        import akshare as ak

        df = ak.futures_main_sina(symbol=symbol)
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.rename(columns={
            "日期": "date",
            "开盘价": "open",
            "最高价": "high",
            "最低价": "low",
            "收盘价": "close",
            "成交量": "volume",
            "持仓量": "open_interest",
            "动态结算价": "settle",
        })
        return df.sort_values("date")

    # ========== 基本面 ==========

    @staticmethod
    def get_financial_summary(code: str) -> pd.DataFrame:
        """获取同花顺财务摘要"""
        import akshare as ak
        return ak.stock_financial_abstract_ths(symbol=code)

    # ========== 工具方法 ==========

    @staticmethod
    def classify_exchange(code: str) -> str:
        """根据代码判断交易所"""
        code = str(code).zfill(6)
        if code.startswith(("600", "601", "603", "605")):
            return "SH"  # 上交所主板
        if code.startswith("688"):
            return "SH_STAR"  # 科创板
        if code.startswith(("000", "001", "002", "003")):
            return "SZ"  # 深交所主板
        if code.startswith(("300", "301")):
            return "SZ_GEM"  # 创业板
        if code.startswith(("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920")):
            return "BJ"  # 北交所
        return "OTHER"
