import streamlit as st
import twstock
import yfinance as yf
import pandas as pd
import time

# --- 頁面基本設定 ---
st.set_page_config(page_title="台股超級選股王", layout="wide")
st.title("📈 台股超級選股王 (嚴謹條件版)")

# --- 側邊欄設定 ---
st.sidebar.header("⚙️ 參數設定")

# 1. 選擇策略
strategy_mode = st.sidebar.selectbox(
    "💡 選擇選股策略",
    (
        "A.量縮測底", 
        "B.夢想起飛",
        "C.多頭環境無賣壓",
        "D.糾結後往上",
        "E.神秘右上角"
    )
)

# 2. 基礎過濾 (給部分策略使用，部分策略會強制覆蓋此設定)
min_vol_input = st.sidebar.number_input("最低成交量過濾 (張) - 適用未指定量的策略", value=1000, step=100)

st.sidebar.info("⚠️ 注意：多頭環境無賣壓已更新為您指定的 Python 邏輯 (排除週轉率資料)。")

# --- 核心邏輯 ---
def check_strategy(ticker, mode):
    try:
        # 下載資料 (抓 1.5 年以確保長天期均線資料足夠)
        df = yf.download(ticker, period="18mo", progress=False)
        
        # 資料不足直接略過 (至少要有 250 天以上資料才能算年線)
        if df.empty or len(df) < 250: return None

        # --- 共用資料清洗 ---
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        high = df['High'] 
        if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]

        vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
        curr_vol = df[vol_col].iloc[-1]
        if isinstance(curr_vol, pd.Series): curr_vol = float(curr_vol.iloc[0])
        else: curr_vol = float(curr_vol)
        
        # 換算成張數 (共用)
        curr_vol_sheets = curr_vol / 1000
        
        # 取得最新日期 (共用)
        last_date = df.index[-1].strftime('%Y-%m-%d')
        curr_price = float(close.iloc[-1])
        
        # 取得名稱 (共用)
        stock_id = ticker.split('.')[0]
        try:
            stock_name = twstock.codes[stock_id].name
        except:
            stock_name = stock_id

        note = ""
        bias_val = "-"

        # ==========================================
        # 🟢 策略 1: 量縮測底
        # ==========================================
        if mode == "量縮測底":
            
            # [條件 1] 成交量 > 1000 張 (強制)
            if curr_vol_sheets <= 1000: return None

            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            ma200 = close.rolling(200).mean()

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

            note = "量縮測底"

        # ==========================================
        # 🚀 策略 2: 夢想起飛
        # ==========================================
        elif mode == "夢想起飛":
            if curr_vol_sheets < min_vol_input: return None

            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            ma120 = close.rolling(120).mean()
            ma200 = close.rolling(200).mean()

            vol_series = df[vol_col]
            if isinstance(vol_series, pd.DataFrame): vol_series = vol_series.iloc[:, 0]
            vol_ma20 = vol_series.rolling(20).mean()

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
        # 🛡️ 策略 3: 多頭環境無賣壓
        # ==========================================
        elif mode == "多頭環境無賣壓":
            # --- 1. 計算技術指標 (依照您的 Code) ---
            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            ma120 = close.rolling(120).mean()
            
            # 最高價區間
            high_max_5 = high.rolling(5).max()
            high_max_60 = high.rolling(60).max()
            
            # [條件 7-1] 成交張數 > 1000 (依照您的 Code)
            cond_volume = (curr_vol_sheets > 1000)
            if not cond_volume: return None

            # [條件 1, 2, 3] 均線多頭排列
            cond_ma_alignment = (curr_price > ma5.iloc[-1]) and \
                                (curr_price > ma20.iloc[-1]) and \
                                (curr_price > ma60.iloc[-1])
            if not cond_ma_alignment: return None

            # [條件 4] 股價在 120 日線之上
            cond_ma120_above = (curr_price > ma120.iloc[-1])
            if not cond_ma120_above: return None

            # [條件 5] 120 日線連續 3 日上升
            # 取最後 4 天的 MA120，計算差值，確認最後 3 個變動都 > 0
            ma120_recent = ma120.tail(4)
            cond_ma120_rising = all(ma120_recent.diff().dropna() > 0)
            if not cond_ma120_rising: return None

            # [條件 7-2] 位階：5日最高 > 60日最高 * 0.9
            cond_high_position = (high_max_5.iloc[-1] > (high_max_60.iloc[-1] * 0.9))
            if not cond_high_position: return None

            # [條件 6] 週轉率 < 1% (略過，因資料源無提供)
            
            note = "多頭無賣壓"

        # ==========================================
        # 🌪️ 策略 4: 糾結後往上
        # ==========================================
        elif mode == "糾結後往上":
            if curr_vol_sheets < min_vol_input: return None
            
            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma60 = close.rolling(60).mean()
            ma120 = close.rolling(120).mean()
            ma200 = close.rolling(200).mean()

            max_high_200 = high.rolling(200).max().iloc[-1]
            if ma5.iloc[-1] <= (max_high_200 * 0.9): return None

            diff_20_60 = (abs(ma20 - ma60) / ma60) * 100
            recent_diff_20_60 = diff_20_60.tail(10)
            if not (recent_diff_20_60 < 10).all(): return None

            diff_60_120 = (abs(ma60 - ma120) / ma120) * 100
            recent_diff_60_120 = diff_60_120.tail(10)
            if not (recent_diff_60_120 < 5).all(): return None

            ma200_recent = ma200.tail(11)
            if not all(ma200_recent.diff().dropna() > 0): return None
            
            note = "均線糾結"

        # ==========================================
        # ✨ 策略 5: 神秘右上角
        # ==========================================
        elif mode == "神秘右上角":
            
            ma5 = close.rolling(5).mean()
            ma20 = close.rolling(20).mean()
            ma200 = close.rolling(200).mean()
            
            max_close_10 = close.rolling(10).max().iloc[-1]
            max_close_200 = close.rolling(200).max().iloc[-1]
            if max_close_10 <= (max_close_200 * 0.95): return None

            ma20_diff = ma20.diff().tail(3)
            if len(ma20_diff.dropna()) < 3 or not all(ma20_diff > 0): return None

            vol_sheets_series = df[vol_col] / 1000
            if isinstance(vol_sheets_series, pd.DataFrame): vol_sheets_series = vol_sheets_series.iloc[:, 0]
            vol_ma5 = vol_sheets_series.rolling(5).mean()
            
            if vol_ma5.iloc[-1] <= 1000: return None

            ma200_diff = ma200.diff().tail(5)
            if len(ma200_diff.dropna()) < 5 or not all(ma200_diff > 0): return None

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
        st.warning(f"在此【嚴謹條件】下，未發現符合的股票。這代表目前市場上沒有完全滿足該策略條件的個股。")
