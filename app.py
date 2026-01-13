import streamlit as st
import twstock
import yfinance as yf
import pandas as pd
import time

# 設定網頁標題
st.set_page_config(page_title="台股自動篩選器", layout="wide")
st.title("📈 台股多頭排列篩選器")

# --- 1. 定義篩選函數 (與原本邏輯相同，增加穩定性) ---
def check_strategy(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 200:
            return None

        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]

        vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
        curr_vol = df[vol_col].iloc[-1]
        curr_vol_sheets = float(curr_vol) / 1000

        # [條件 1] 成交量 > 1000 張
        if curr_vol_sheets <= 1000: return None

        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma200 = close.rolling(200).mean()
        curr_price = float(close.iloc[-1])

        # [條件 2] 均線多頭排列
        cond_trend = (curr_price > ma5.iloc[-1]) and \
                     (curr_price > ma20.iloc[-1]) and \
                     (curr_price > ma60.iloc[-1])
        if not cond_trend: return None

        # [條件 3] 測底完成
        min_price_20 = close.tail(20).min()
        min_ma20_20 = ma20.tail(20).min()
        if min_price_20 >= min_ma20_20: return None

        # [條件 4] 乖離率控制
        if curr_price >= (ma200.iloc[-1] * 1.4): return None

        # [條件 5] 年線上升
        ma200_recent = ma200.tail(11)
        if not all(ma200_recent.diff().dropna() > 0): return None

        stock_id = ticker.split('.')[0]
        stock_name = twstock.codes[stock_id].name

        return {
            "代號": ticker,
            "名稱": stock_name,
            "股價": round(curr_price, 2),
            "成交量(張)": int(curr_vol_sheets)
        }
    except:
        return None

# --- 2. 側邊欄設定 ---
st.sidebar.header("篩選設定")
scan_range = st.sidebar.slider("掃描前幾檔 (測試用)", 10, 2000, 100)

if st.sidebar.button("開始掃描"):
    # 取得清單
    twse_codes = [f"{c}.TW" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上市']
    tpex_codes = [f"{c}.TWO" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上櫃']
    all_stocks = (twse_codes + tpex_codes)[:scan_range]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 執行掃描
    for i, stock in enumerate(all_stocks):
        status_text.text(f"正在檢查: {stock} ({i+1}/{len(all_stocks)})")
        res = check_strategy(stock)
        if res:
            results.append(res)
        progress_bar.progress((i + 1) / len(all_stocks))
    
    status_text.success(f"✅ 掃描完成！共找到 {len(results)} 檔符合條件。")
    
    # 顯示結果
    if results:
        df_res = pd.DataFrame(results)
        st.dataframe(df_res, use_container_width=True)
    else:
        st.info("目前沒有符合所有條件的股票。")