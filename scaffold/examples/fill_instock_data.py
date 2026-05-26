#!/usr/bin/env python3
"""用 akshare 数据填充 myhhub/stock 数据库，使用项目自身的 insert_db_from_df 建表后写入"""

import sys
import os
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_DIR = os.environ.get("INSTOCK_PROJECT_DIR", os.path.expanduser("~/project/quant-research/repos/stock"))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "instock", "job"))

import instock.lib.database as mdb
import instock.core.tablestructure as tbs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quant_data.providers.akshare_provider import AkshareProvider

provider = AkshareProvider()
TODAY = date.today().strftime("%Y-%m-%d")


def fill_stock_spot(limit: int = 500):
    """填充 cn_stock_spot 表 — A股日行情快照"""
    print("获取A股列表...")
    stocks = provider.get_stock_list()
    if limit:
        stocks = stocks.head(limit)
    total = len(stocks)
    print(f"逐只获取 {total} 只股票今日行情...")

    rows = []
    for i, (_, row) in enumerate(stocks.iterrows()):
        code = row["code"]
        name = row["name"]
        if i % 100 == 0:
            print(f"  进度: {i}/{total}")

        try:
            df = provider.get_stock_daily(code, end_date=TODAY.replace("-", ""))
            if df.empty:
                continue
            latest = df.iloc[-1]
            prev_close = df.iloc[-2]["close"] if len(df) > 1 else latest["close"]
            rows.append({
                "date": TODAY,
                "code": code,
                "name": name,
                "new_price": float(latest["close"]),
                "change_rate": float(latest.get("pct_change", 0) or 0),
                "ups_downs": float(latest.get("change", 0) or 0),
                "volume": int(latest.get("volume", 0) or 0),
                "deal_amount": int(latest.get("amount", 0) or 0),
                "amplitude": float(latest.get("amplitude", 0) or 0),
                "turnoverrate": float(latest.get("turnover", 0) or 0),
                "open_price": float(latest["open"]),
                "high_price": float(latest["high"]),
                "low_price": float(latest["low"]),
                "pre_close_price": float(prev_close),
            })
        except Exception:
            continue

    data_df = pd.DataFrame(rows)
    if data_df.empty:
        print("⚠️ 没有获取到任何数据")
        return

    table_info = tbs.TABLE_CN_STOCK_SPOT
    mdb.insert_db_from_df(data_df, table_info["name"], cols_type=None,
                          write_index=False, primary_keys="`date`,`code`")
    print(f"✅ cn_stock_spot: {len(data_df)} 条")


def fill_stock_selection():
    """填充 cn_stock_selection"""
    print("\n生成综合选股数据...")
    query = """
        SELECT code, name, new_price, change_rate, volume, deal_amount,
               turnoverrate, high_price, low_price, pre_close_price
        FROM cn_stock_spot WHERE date = :d
        ORDER BY change_rate DESC LIMIT 100
    """
    from sqlalchemy import text
    with mdb.engine().connect() as conn:
        result = conn.execute(text(query), {"d": TODAY})
        rows = result.fetchall()

    if not rows:
        print("⚠️ cn_stock_spot 中无数据")
        return

    data = [{
        "date": TODAY,
        "code": r[0], "name": r[1], "new_price": float(r[2] or 0),
        "change_rate": float(r[3] or 0), "volume": int(r[4] or 0),
        "deal_amount": int(r[5] or 0), "turnoverrate": float(r[6] or 0),
        "high_price": float(r[7] or 0), "low_price": float(r[8] or 0),
        "pre_close_price": float(r[9] or 0),
    } for r in rows]

    data_df = pd.DataFrame(data)
    table_info = tbs.TABLE_CN_STOCK_SELECTION
    mdb.insert_db_from_df(data_df, table_info["name"], cols_type=None,
                          write_index=False, primary_keys="`date`,`code`")
    print(f"✅ cn_stock_selection: {len(data_df)} 条")


if __name__ == "__main__":
    fill_stock_spot(limit=500)
    fill_stock_selection()
    print("\n🎉 完成！启动 web: python instock/web/web_service.py")
