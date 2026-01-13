import streamlit as st
import twstock
import yfinance as yf
import pandas as pd
import time

# --- 頁面基本設定 ---
st.set_page_config(page_title="全台股篩選器", layout="wide")
st.title("📈 台股強力篩選器 (上市+上櫃)")
st.markdown("策略：**成交量 > 500 張**、均線多頭排列、測底完成")

# --- 1. 核心篩選邏輯 ---
def check_strategy(ticker):
    try:
        # 下載資料 (近 1 年)
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 200:
            return None

        # 資料整理：處理 Series/DataFrame 格式差異
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        
        vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
        curr_vol = df[vol_col].iloc[-1]
        
        # 確保成交量是數值
        if isinstance(curr_vol, pd.Series): curr_vol = float(curr_vol.iloc[0])
        else: curr_vol = float(curr_vol)
        
        curr_vol_sheets = curr_vol / 1000

        # 🔥 [修改點] 條件 1: 成交量 > 500 張
        if curr_vol_sheets < 500: return None

        # 計算均線
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma200 = close.rolling(200).mean()
        curr_price = float(close.iloc[-1])

        # 條件 2: 均線多頭排列 (現價 > 5日 > 20日 > 60日)
        cond_trend = (curr_price > ma5.iloc[-1]) and \
                     (curr_price > ma20.iloc[-1]) and \
                     (curr_price > ma60.iloc[-1])
        if not cond_trend: return None

        # 條件 3: 測底完成 (20日內最低價 < 20日均線最低點，簡單過濾剛起漲)
        # 這裡保留原本邏輯，若不需要可註解掉
        min_price_20 = close.tail(20).min()
        min_ma20_20 = ma20.tail(20).min()
        if min_price_20 >= min_ma20_20: return None

        # 條件 4: 乖離率控制 (避免追高)
        if curr_price >= (ma200.iloc[-1] * 1.4): return None

        # 條件 5: 年線趨勢向上 (近10天)
        ma200_recent = ma200.tail(11)
        if not all(ma200_recent.diff().dropna() > 0): return None

        # 取得名稱 (處理 twstock 可能的報錯)
        stock_id = ticker.split('.')[0]
        try:
            if stock_id in twstock.codes:
                stock_name = twstock.codes[stock_id].name
            else:
                stock_name = stock_id
        except:
            stock_name = stock_id

        return {
            "代號": stock_id,
            "名稱": stock_name,
            "收盤價": round(curr_price, 2),
            "成交量(張)": int(curr_vol_sheets),
            "市場": "上市" if ".TW" in ticker else "上櫃"
        }
    except Exception as e:
        # print(e) # 除錯用
        return None

# --- 2. 側邊欄控制 ---
st.sidebar.header("⚙️ 篩選設定")

# 🔥 [修改點] 增加模式選擇
scan_mode = st.sidebar.radio(
    "選擇掃描範圍：",
    ("快速測試 (前 100 檔)", "全台股掃描 (約 1800 檔)")
)

st.sidebar.info("💡 提示：全台股掃描因為資料量大，可能需要 15 分鐘以上，請耐心等候。若 Streamlit 雲端超時斷線，建議縮小範圍或分批執行。")

# --- 3. 執行按鈕 ---
if st.sidebar.button("🚀 開始執行"):
    st.write("正在取得最新的股票清單...")
    
    # 取得清單
    try:
        # 上市
        twse_codes = [f"{c}.TW" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上市']
        # 上櫃
        tpex_codes = [f"{c}.TWO" for c in twstock.codes.keys() if twstock.codes[c].type == '股票' and twstock.codes[c].market == '上櫃']
        
        all_stocks = twse_codes + tpex_codes
        
        # 根據模式決定掃描數量
        if scan_mode == "快速測試 (前 100 檔)":
            target_list = all_stocks[:100]
            st.warning(f"目前為測試模式，僅掃描前 100 檔 (共 {len(all_stocks)} 檔)。")
        else:
            target_list = all_stocks
            st.success(f"已啟動全台股模式，共 {len(target_list)} 檔，請稍候...")
            
    except Exception as e:
        st.error(f"無法取得股票清單: {e}")
        st.stop()

    results = []
    
    # 進度條設定
    progress_text = "掃描進行中...請勿關閉視窗"
    my_bar = st.progress(0, text=progress_text)
    status_box = st.empty()
    
    start_time = time.time()
    total_stocks = len(target_list)

    # 開始迴圈
    for i, stock in enumerate(target_list):
        # 顯示即時進度 (每 5 檔更新一次介面，避免拖慢速度)
        if i % 5 == 0:
            pct = (i + 1) / total_stocks
            my_bar.progress(pct, text=f"正在分析: {stock} ({i+1}/{total_stocks})")
        
        res = check_strategy(stock)
        
        if res:
            results.append(res)
            # 即時顯示找到的股票 (使用 Toast 彈出訊息)
            st.toast(f"🎯 發現: {res['代號']} {res['名稱']} (量:{res['成交量(張)']})")

    # 掃描結束
    end_time = time.time()
    duration = end_time - start_time
    my_bar.progress(1.0, text="掃描完成！")
    st.success(f"✅ 執行完畢！耗時 {int(duration // 60)} 分 {int(duration % 60)} 秒")

    # --- 4. 顯示結果表格 ---
    if results:
        st.subheader(f"🏆 篩選結果：共 {len(results)} 檔")
        df_results = pd.DataFrame(results)
        
        # 讓表格依照成交量排序 (由大到小)
        df_results = df_results.sort_values(by="成交量(張)", ascending=False).reset_index(drop=True)
        
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("⚠️ 在掃描範圍內，沒有發現符合「所有條件」的股票。")
