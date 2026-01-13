import streamlit as st
import twstock
import yfinance as yf
import pandas as pd
import time

# --- 頁面基本設定 ---
st.set_page_config(page_title="台股超級選股王", layout="wide")
st.title("📈 台股超級選股王 (4大策略)")

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ 參數設定")

# 1. 選擇策略 (新增第五個選項)
strategy_mode = st.sidebar.selectbox(
    "💡 選擇選股策略",
    (
        "A.量縮測底 (多頭排列+測底)", 
        "B.夢想起飛 (均線全多頭+量能增溫)",
        "C.糾結後往上 (均線密集糾結+準備突破)",
        "D.神秘右上角 (強勢創高+均線多排)"
    )
)

# 2. 基礎過濾
min_vol = st.sidebar.number_input("最低成交量過濾 (張)", value=1000, step=100)

st.sidebar.info("提示：策略運算較複雜，全台股掃描約需 15-20 分鐘，請耐心等候。")

# --- 核心邏輯 ---
def check_strategy(ticker, mode):
    try:
        # 下載資料 (抓 1.5 年以確保長天期均線資料足夠)
        df = yf.download(ticker, period="18mo", progress=False)
        
        # 資料不足直接略過
        if df.empty or len(df) < 300: return None

        # --- 資料清洗 ---
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        high = df['High'] 
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]

        vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
        curr_vol = df[vol_col].iloc[-1]
        if isinstance(curr_vol, pd.Series): curr_vol = float(curr_vol.iloc[0])
        else: curr_vol = float(curr_vol)
        curr_vol_sheets = curr_vol / 1000

        # [共同基礎過濾] 今日成交量門檻
        if curr_vol_sheets < min_vol: return None

        # --- 取得最新資料日期與價格 ---
        last_date = df.index[-1].strftime('%Y-%m-%d')
        curr_price = float(close.iloc[-1])
        
        # 計算均線
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma120 = close.rolling(120).mean() # 半年線
        ma200 = close.rolling(200).mean() # 年線

        # 處理成交量 (換算成張數)
        vol_sheets_series = df[vol_col] / 1000
        if isinstance(vol_sheets_series, pd.DataFrame): vol_sheets_series = vol_sheets_series.iloc[:, 0]
        
        # 成交量均線
        vol_ma5 = vol_sheets_series.rolling(5).mean()
        vol_ma20 = vol_sheets_series.rolling(20).mean()

        # 取得名稱
        stock_id = ticker.split('.')[0]
        try:
            stock_name = twstock.codes[stock_id].name
        except:
            stock_name = stock_id

        note = ""
        bias_val = "-"

        # ==========================================
        # 🟢 策略 A: 量縮測底
        # ==========================================
        if mode == "量縮測底 (多頭排列+測底)":
            cond_trend = (curr_price > ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
            if not cond_trend: return None

            min_price_20 = close.tail(20).min()
            min_ma20_20 = ma20.tail(20).min()
            if min_price_20 >= min_ma20_20: return None

            if curr_price >= (ma200.iloc[-1] * 1.4): return None
            if not all(ma200.tail(11).diff().dropna() > 0): return None
            note = "量縮測底"

        # ==========================================
        # 🚀 策略 B: 夢想起飛
        # ==========================================
        elif mode == "夢想起飛 (均線全多頭+量能增溫)":
            cond_price = (curr_price > ma5.iloc[-1]) and \
                         (curr_price > ma20.iloc[-1]) and \
                         (curr_price > ma60.iloc[-1]) and \
                         (curr_price > ma120.iloc[-1])
            if not cond_price: return None

            bias_5_200 = ((ma5.iloc[-1] - ma200.iloc[-1]) / ma200.iloc[-1]) * 100
            if bias_5_200 >= 30: return None
            bias_val = round(bias_5_200, 1)

            ma200_recent = ma200.tail(11) 
            if not all(ma200_recent.diff().dropna() > 0): return None

            vol_ma20_recent = vol_ma20.tail(11)
            if not all(vol_ma20_recent.diff().dropna() > 0): return None
            note = "夢想起飛"

        # ==========================================
        # 🌪️ 策略 C: 糾結後往上
        # ==========================================
        elif mode == "糾結後往上 (均線密集糾結+準備突破)":
            max_high_200 = high.rolling(200).max().iloc[-1]
            if ma5.iloc[-1] <= (max_high_200 * 0.9): return None

            diff_20_60 = (abs(ma20 - ma60) / ma60) * 100
            if not (diff_20_60.tail(10) < 10).all(): return None

            diff_60_120 = (abs(ma60 - ma120) / ma120) * 100
            if not (diff_60_120.tail(10) < 5).all(): return None

            ma200_recent = ma200.tail(11)
            if not all(ma200_recent.diff().dropna() > 0): return None
            note = "均線糾結突破"

        # ==========================================
        # ✨ 策略 D: 神秘右上角 
        # ==========================================
        elif mode == "神秘右上角 (強勢創高+均線多排)":
            # 1. 10日最大收盤價 > 200日最大收盤價 * 0.95
            max_close_10 = close.rolling(10).max().iloc[-1]
            max_close_200 = close.rolling(200).max().iloc[-1]
            if max_close_10 <= (max_close_200 * 0.95): return None

            # 2. 連續3日上升 [20日收盤價平均] (MA20趨勢向上)
            ma20_diff = ma20.diff().tail(3)
            if not all(ma20_diff > 0): return None

            # 3. 5日成交量平均 > 1000 (張)
            if vol_ma5.iloc[-1] <= 1000: return None

            # 4. 連續5日上升 [200日收盤價平均] (年線趨勢向上)
            ma200_diff = ma200.diff().tail(5)
            if not all(ma200_diff > 0): return None

            # 5. 收盤價 > 5日收盤價平均 (站上週線)
            if curr_price <= ma5.iloc[-1]: return None

            note = "神秘右上角"

        # 回傳結果
        return {
            "資料日期": last_date,
            "代號": stock_id,
            "名稱": stock_name,
            "收盤價": round(curr_price, 2),
            "成交量": int(curr_vol_sheets),
            "策略": note,
            "乖離率(5-200)": bias_val
        }

    except Exception:
        return None

# --- 執行按鈕 ---
if st.sidebar.button("🚀 開始掃描"):
    
    # 取得清單
    try:
        twse_codes = [f"{c}.TW" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上市']
        tpex_codes = [f"{c}.TWO" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上櫃']
        target_list = twse_codes + tpex_codes
        
        st.success(f"✅ 已啟動全台股模式：準備掃描 {len(target_list)} 檔股票。")
            
    except:
        st.error("無法取得股票清單。")
        st.stop()

    # 介面準備
    st.subheader(f"📊 執行策略：{strategy_mode}")
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    start_time = time.time()

    # 迴圈掃描
    for i, stock in enumerate(target_list):
        if i % 10 == 0: 
            status_text.text(f"⏳ 分析中: {stock} ({i+1}/{len(target_list)})")
            progress_bar.progress((i + 1) / len(target_list))
        
        res = check_strategy(stock, strategy_mode)
        
        if res:
            results.append(res)
            st.toast(f"🎯 抓到了！{res['代號']} {res['名稱']}")

    # 結束
    duration = time.time() - start_time
    progress_bar.progress(1.0)
    status_text.success(f"掃描完成！耗時 {int(duration // 60)} 分 {int(duration % 60)} 秒")

    # 顯示表格
    if results:
        df_res = pd.DataFrame(results)
        cols = ['資料日期', '代號', '名稱', '收盤價', '成交量', '策略', '乖離率(5-200)']
        df_res = df_res[cols]
        df_res = df_res.sort_values(by="成交量", ascending=False).reset_index(drop=True)
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("在此條件下未發現符合的股票。")
