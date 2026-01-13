import streamlit as st
import twstock
import yfinance as yf
import pandas as pd
import time

# --- 頁面基本設定 ---
st.set_page_config(page_title="台股超級選股王", layout="wide")
st.title("📈 台股超級選股王 (全台股模式)")

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ 參數設定")

# 1. 選擇策略
strategy_mode = st.sidebar.selectbox(
    "💡 選擇選股策略",
    ("量縮測底 (多頭排列+測底)", "夢想起飛 (均線全多頭+量能增溫)")
)

# 2. 基礎過濾
min_vol = st.sidebar.number_input("最低成交量過濾 (張)", value=1000, step=100)

st.sidebar.info("提示：若要取得今日 1:30 PM 收盤價，建議在下午 2:00 後執行，以確保資料已更新。")

# --- 核心邏輯 ---
def check_strategy(ticker, mode):
    try:
        # 下載資料 (抓 1.5 年)
        df = yf.download(ticker, period="18mo", progress=False)
        
        # 資料不足直接略過
        if df.empty or len(df) < 300: return None

        # --- 資料清洗 ---
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
        curr_vol = df[vol_col].iloc[-1]
        if isinstance(curr_vol, pd.Series): curr_vol = float(curr_vol.iloc[0])
        else: curr_vol = float(curr_vol)
        curr_vol_sheets = curr_vol / 1000

        # [共同基礎過濾] 成交量門檻
        if curr_vol_sheets < min_vol: return None

        # --- 取得最新資料日期與價格 ---
        # 確保抓到的是最後一筆 (即最新收盤價)
        last_date = df.index[-1].strftime('%Y-%m-%d')
        curr_price = float(close.iloc[-1])
        
        # 計算均線
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma120 = close.rolling(120).mean()
        ma200 = close.rolling(200).mean()

        # 處理成交量均線
        vol_series = df[vol_col]
        if isinstance(vol_series, pd.DataFrame): vol_series = vol_series.iloc[:, 0]
        vol_ma20 = vol_series.rolling(20).mean()

        # 取得名稱
        stock_id = ticker.split('.')[0]
        try:
            stock_name = twstock.codes[stock_id].name
        except:
            stock_name = stock_id

        # ==========================================
        # 🟢 策略 A: 量縮測底
        # ==========================================
        if mode == "量縮測底 (多頭排列+測底)":
            # 1. 均線排列 (5 > 20 > 60)
            cond_trend = (curr_price > ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1])
            if not cond_trend: return None

            # 2. 測底完成 (20日內最低價沒有破 20日均線的最低點)
            min_price_20 = close.tail(20).min()
            min_ma20_20 = ma20.tail(20).min()
            if min_price_20 >= min_ma20_20: return None

            # 3. 乖離率控制 (現價 < 年線 * 1.4)
            if curr_price >= (ma200.iloc[-1] * 1.4): return None
            
            # 4. 年線上升
            if not all(ma200.tail(11).diff().dropna() > 0): return None

            note = "量縮測底"

        # ==========================================
        # 🚀 策略 B: 夢想起飛
        # ==========================================
        elif mode == "夢想起飛 (均線全多頭+量能增溫)":
            # 1. 收盤價 > 5, 20, 60, 120日均線
            cond_price = (curr_price > ma5.iloc[-1]) and \
                         (curr_price > ma20.iloc[-1]) and \
                         (curr_price > ma60.iloc[-1]) and \
                         (curr_price > ma120.iloc[-1])
            if not cond_price: return None

            # 2. (5, 200) 乖離率 < 30
            bias_5_200 = ((ma5.iloc[-1] - ma200.iloc[-1]) / ma200.iloc[-1]) * 100
            if bias_5_200 >= 30: return None

            # 3. 連續 10 日上升 [200日收盤價平均]
            ma200_recent = ma200.tail(11) 
            if not all(ma200_recent.diff().dropna() > 0): return None

            # 4. 連續 10 日上升 [20日成交量平均]
            vol_ma20_recent = vol_ma20.tail(11)
            if not all(vol_ma20_recent.diff().dropna() > 0): return None

            note = "夢想起飛"

        # 回傳結果
        return {
            "資料日期": last_date,  # 新增這個欄位讓你檢查
            "代號": stock_id,
            "名稱": stock_name,
            "收盤價": round(curr_price, 2),
            "成交量": int(curr_vol_sheets),
            "策略": note,
            "乖離率(5-200)": round(((ma5.iloc[-1] - ma200.iloc[-1])/ma200.iloc[-1])*100, 1) if "夢想起飛" in mode else "-"
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
        # 把日期欄位放到最前面
        cols = ['資料日期', '代號', '名稱', '收盤價', '成交量', '策略', '乖離率(5-200)']
        df_res = df_res[cols]
        
        df_res = df_res.sort_values(by="成交量", ascending=False).reset_index(drop=True)
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("在此條件下未發現符合的股票。")
