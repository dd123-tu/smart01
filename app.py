import ssl
import time
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="台股優先觀察雷達｜手機電腦通用版", page_icon="📊", layout="wide")
TWSE_SSL_CONTEXT = ssl._create_unverified_context()

st.markdown("""
<style>
.main { background-color: #0e1117; }
h1, h2, h3 { color: #58a6ff; font-family: 'Segoe UI', sans-serif; }
.stButton > button { font-size: 17px; font-weight: bold; padding: 0.75rem 1rem; }
.stDataFrame { border: 1px solid #30363d; border-radius: 10px; }
.block-container { padding-top: 1rem; padding-left: 1.5rem; padding-right: 1.5rem; max-width: 1500px; }
.mobile-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 14px;
    padding: 12px 14px;
    margin: 10px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.25);
}
.mobile-title { font-size: 20px; font-weight: 800; color: #58a6ff; margin-bottom: 4px; }
.mobile-sub { font-size: 14px; color: #c9d1d9; margin-bottom: 8px; }
.mobile-tags { font-size: 13px; color: #8b949e; line-height: 1.5; }
.mobile-warn { color: #f2cc60; font-weight: 700; }
.mobile-good { color: #7ee787; font-weight: 700; }
@media (max-width: 768px) {
    .block-container { padding-left: 0.5rem; padding-right: 0.5rem; max-width: 760px; }
    h1 { font-size: 1.55rem; }
    h2 { font-size: 1.25rem; }
    h3 { font-size: 1.05rem; }
    div[data-testid="stDataFrame"] { font-size: 12px; }
}
</style>
""", unsafe_allow_html=True)

st.title("台股優先觀察雷達｜手機電腦通用版")
st.caption("同一份程式：手機看重點卡片，電腦看完整寬表格。優先觀察名單不是直接買進訊號。")

# =========================
# 參數區
# =========================
st.markdown("""
### 使用說明

這版是 **手機 / 電腦通用版**，目標是先找出值得看的股票，不是直接叫你買。

- **優先觀察名單**：最先研究，不等於一定買。
- **轉強候選**：有底部訊號，加上放量、ATR轉強、日線結構、分數或多策略其中之一。
- **底部雷達觀察**：只有底部味道，還沒轉強，先不要急。

成交量、ATR轉強、頭頭高底底高，主要是用來提醒與排序，不是硬性刪除條件。
""")

st.markdown("### 掃描設定")

view_mode = st.radio(
    "顯示模式",
    ["自動", "手機模式", "電腦模式"],
    index=0,
    horizontal=True,
    help="手機建議用手機模式；電腦建議用電腦模式；自動會同時保留重點卡片與完整表格。"
)

with st.expander("① 市場與股票", expanded=True):
    market_type = st.radio("市場類型", ["上市", "上櫃", "全部"], horizontal=True)
    scan_mode = st.radio("掃描模式", ["自訂股票名單", "全市場掃描"], horizontal=True)
    if scan_mode == "自訂股票名單":
        stock_input = st.text_area("股票代碼，一行或逗號隔開", value="2498.TW, 2330.TW, 2317.TW", height=80)
    else:
        stock_input = ""
        st.info(f"將掃描 {market_type} 股票")

with st.expander("② 雷達條件", expanded=True):
    filter_mode = st.radio(
        "篩選模式",
        ["寬鬆雷達", "標準", "嚴格"],
        index=0,
        horizontal=True,
        help="手機建議先用寬鬆雷達：先多抓股票，再人工看K線。"
    )
    holding_days = st.number_input("觀察天數", value=10, min_value=1, max_value=60)
    fresh_days = st.number_input("近期窗口", value=10, min_value=1, max_value=30)
    vol_threshold = st.number_input("放量倍數", value=1.1, min_value=0.5, max_value=5.0, step=0.1)
    min_daily_volume_lots = st.number_input("最低日成交張數", value=300, min_value=0, max_value=200000, step=100)

with st.expander("③ 日線結構提醒", expanded=False):
    use_hh_hl_bonus = st.checkbox("顯示頭頭高、底底高提醒", value=True, help="只做加分與提醒，不會把股票直接刪掉。")
    hh_hl_period = st.number_input("結構比較天數", value=5, min_value=3, max_value=20, step=1)

with st.expander("④ 策略勾選", expanded=False):
    strategy_options = ["RSI低檔", "季線負乖離", "布林下軌", "KD+RSI雙低檔", "底部背離", "ATR轉強"]
    selected_strategies = st.multiselect(
        "要掃描的策略",
        strategy_options,
        default=strategy_options,
        help="手機版改成下拉多選，避免一排勾選太擠。"
    )

with st.expander("⑤ ATR停損停利", expanded=False):
    atr_period = st.number_input("ATR週期", value=14, min_value=5, max_value=60)
    atr_stop_mult = st.number_input("ATR停損倍數", value=1.5, min_value=0.5, max_value=5.0, step=0.1)
    atr_take_mult = st.number_input("ATR停利倍數", value=2.0, min_value=0.5, max_value=10.0, step=0.1)

with st.expander("⑥ 回測基準日", expanded=False):
    use_base_date = st.checkbox("指定基準日", value=False)
    base_date = st.date_input("回測基準日", value=pd.Timestamp.today().date(), disabled=not use_base_date)

selected_base_date = base_date if use_base_date else None

analyze_btn = st.button("啟動台股雷達", use_container_width=True, type="primary")
st.markdown("---")

st.info("手機可看『重點卡片』；電腦可看『完整寬表格』。同一份程式兩邊都能用。")

# =========================
# 股票清單
# =========================
@st.cache_data(ttl=86400)
def get_tw_stock_list(market_type="全部"):
    stocks = []
    sources = []
    if market_type in ("上市", "全部"):
        sources.append(("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", ".TW"))
    if market_type in ("上櫃", "全部"):
        sources.append(("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", ".TWO"))

    try:
        orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **kw: orig_urlopen(*a, **{**kw, "context": TWSE_SSL_CONTEXT})
        try:
            for url, suffix in sources:
                table = pd.read_html(url)[0]
                table.columns = table.iloc[0]
                table = table.iloc[1:]
                for value in table["有價證券代號及名稱"].dropna():
                    code = str(value).split()[0]
                    if code.isdigit() and len(code) == 4:
                        stocks.append(f"{code}{suffix}")
        finally:
            urllib.request.urlopen = orig_urlopen
        return sorted(set(stocks))
    except Exception as e:
        st.warning(f"取得股票清單失敗，改用備用清單：{e}")
        if market_type in ("上市", "全部"):
            stocks += [f"{i:04d}.TW" for i in range(1101, 3700)]
            stocks += [f"{i:04d}.TW" for i in range(6001, 6800)]
        if market_type in ("上櫃", "全部"):
            stocks += [f"{i:04d}.TWO" for i in range(3001, 8999, 5)]
        return sorted(set(stocks))

# =========================
# 指標與策略
# =========================
def calculate_higher_high_higher_low(df, period=5):
    """
    日線頭頭高、底底高判斷。
    用最近 period 天的最高價 / 最低價，
    對比前一段 period 天的最高價 / 最低價。

    True 代表：
    1. 最近一段高點 > 前一段高點
    2. 最近一段低點 > 前一段低點
    3. 收盤價 > period 天前收盤價
    """
    if df is None or df.empty or len(df) < int(period) * 2 + 1:
        return pd.Series(False, index=df.index if df is not None else [])

    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    p = int(period)

    recent_high = high.rolling(p).max()
    previous_high = high.shift(p).rolling(p).max()
    recent_low = low.rolling(p).min()
    previous_low = low.shift(p).rolling(p).min()

    hh_hl = (recent_high > previous_high) & (recent_low > previous_low) & (close > close.shift(p))
    return hh_hl.fillna(False)


def calculate_indicators(df, vol_mult=1.2, atr_period=14):
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = true_range.rolling(int(atr_period)).mean()
    atr_ma20 = atr.rolling(20).mean()
    atr_pct = atr / close * 100

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss)))

    low_9 = low.rolling(9).min()
    high_9 = high.rolling(9).max()
    rsv = (close - low_9) / (high_9 - low_9) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()

    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    std20 = close.rolling(20).std()
    lower_band = ma20 - 2 * std20
    bias60 = (close - ma60) / ma60 * 100

    vol_ma5 = volume.rolling(5).mean()
    vol_confirm = volume > vol_ma5 * vol_mult

    kd_divergence = (k < 25) & (k > k.shift(1)) & (close < close.shift(1))
    macd_fast = close.ewm(span=12, adjust=False).mean()
    macd_slow = close.ewm(span=26, adjust=False).mean()
    macd_line = macd_fast - macd_slow
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - macd_signal
    macd_divergence = (close < close.rolling(20).min().shift(1)) & (macd_hist > macd_hist.shift(1))

    signals = {
        "RSI低檔": rsi < 35,
        "季線負乖離": bias60 < -10,
        "布林下軌": close < lower_band,
        "KD+RSI雙低檔": (k < 25) & (rsi < 35),
        "底部背離": kd_divergence | macd_divergence,
        "ATR轉強": (atr > atr_ma20) & (close > close.shift(1)) & vol_confirm,
    }

    return signals, rsi, bias60, atr, atr_pct


def quick_prefilter(stock_df, selected_strategies, vol_mult, fresh_window, base_date=None, atr_period=14):
    if stock_df.empty:
        return False
    if base_date is not None:
        stock_df = stock_df[stock_df.index <= pd.Timestamp(base_date)]
    if len(stock_df) < 80:
        return False
    signals, *_ = calculate_indicators(stock_df, vol_mult, atr_period)
    return any(signals[name].tail(int(fresh_window)).any() for name in selected_strategies if name in signals)


def backtest_stock(ticker, selected_strategies, holding_days, vol_mult, fresh_window, base_date=None, atr_period=14, atr_stop_mult=1.5, atr_take_mult=2.0, hh_hl_period=5):
    try:
        df = yf.download(ticker, period="10y", progress=False, auto_adjust=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if base_date is not None:
            df = df[df.index <= pd.Timestamp(base_date)]
        if df.empty or len(df) < max(120, int(holding_days) + 80):
            return []
    except Exception:
        return []

    close = df["Close"]
    volume = df["Volume"]
    latest_trade_date = df.index[-1].strftime("%Y-%m-%d")
    signals, rsi, bias60, atr, atr_pct = calculate_indicators(df, vol_mult, atr_period)
    hh_hl_series = calculate_higher_high_higher_low(df, hh_hl_period)
    latest_hh_hl = bool(hh_hl_series.iloc[-1]) if len(hh_hl_series) else False

    rows = []
    for signal_name in selected_strategies:
        if signal_name not in signals:
            continue
        signal = signals[signal_name]
        recent_signal = signal.tail(int(fresh_window))
        if not recent_signal.any():
            continue

        trades = []
        for i in range(60, len(df) - int(holding_days)):
            if signal.iloc[i]:
                entry = close.iloc[i]
                exit_price = close.iloc[i + int(holding_days)]
                if entry > 0:
                    trades.append((exit_price - entry) / entry)
        if len(trades) < 3:
            continue

        trades = np.array(trades)
        valid_trades = trades[np.abs(trades) >= 0.03]
        total_count = len(trades)
        valid_count = len(valid_trades)
        valid_ratio = valid_count / total_count if total_count else 0

        if valid_count > 0:
            win_rate = (valid_trades > 0).sum() / valid_count
            avg_return = valid_trades.mean()
            max_gain = valid_trades.max()
            max_loss = valid_trades.min()
            positive_count = int((valid_trades > 0).sum())
            negative_count = int((valid_trades < 0).sum())
        else:
            win_rate = avg_return = max_gain = max_loss = 0
            positive_count = negative_count = 0

        last_trigger_index = np.where(recent_signal == True)[0][-1]
        signal_date = recent_signal.index[last_trigger_index]
        if base_date is not None:
            days_ago = len(df.loc[signal_date:]) - 1
        else:
            days_ago = (pd.Timestamp.today().normalize() - pd.Timestamp(signal_date).normalize()).days

        if days_ago == 0:
            recent_text = f"🎯 {signal_date.strftime('%Y-%m-%d')} (今日)"
        elif days_ago == 1:
            recent_text = f"⚡ {signal_date.strftime('%Y-%m-%d')} (昨日)"
        else:
            recent_text = f"⚡ {signal_date.strftime('%Y-%m-%d')} ({days_ago}天前)"

        sample_score = min(total_count / 30, 1)
        freshness_score = max(0, 1 - days_ago / max(int(fresh_window), 1))
        composite_count = sum(1 for s in selected_strategies if s in signals and signals[s].tail(int(fresh_window)).any())
        composite_bonus = min(max(composite_count - 1, 0), 3) * 3
        recommendation_score = (
            win_rate * 45
            + max(avg_return, 0) * 800
            + sample_score * 15
            + freshness_score * 15
            + max(max_loss, -0.3) * 20
            + composite_bonus
        )

        latest_vol = float(volume.iloc[-1]) if not pd.isna(volume.iloc[-1]) else 0
        vol_ma5 = float(volume.rolling(5).mean().iloc[-1]) if not pd.isna(volume.rolling(5).mean().iloc[-1]) else 0
        vol_ratio = latest_vol / vol_ma5 if vol_ma5 > 0 else np.nan
        vol_status = "放量" if vol_ma5 > 0 and latest_vol >= vol_ma5 * float(vol_mult) else "量不足"

        rows.append({
            "股票代碼": ticker,
            "策略跡象": signal_name,
            "現價": round(float(close.iloc[-1]), 2),
            "最新成交量張數": round(latest_vol / 1000, 0),
            "5日均量張數": round(vol_ma5 / 1000, 0) if vol_ma5 > 0 else np.nan,
            "量比": round(float(vol_ratio), 2) if not pd.isna(vol_ratio) else np.nan,
            "量能狀態": vol_status,
            "日線結構": "頭頭高底底高" if latest_hh_hl else "未形成",
            "日線結構成立": latest_hh_hl,
            "目前ATR": round(float(atr.iloc[-1]), 2) if not pd.isna(atr.iloc[-1]) else np.nan,
            "ATR波動%": round(float(atr_pct.iloc[-1]), 2) if not pd.isna(atr_pct.iloc[-1]) else np.nan,
            "ATR停損價": round(float(close.iloc[-1] - atr.iloc[-1] * atr_stop_mult), 2) if not pd.isna(atr.iloc[-1]) else np.nan,
            "ATR停利價": round(float(close.iloc[-1] + atr.iloc[-1] * atr_take_mult), 2) if not pd.isna(atr.iloc[-1]) else np.nan,
            "資料最新交易日": latest_trade_date,
            "發生次數": total_count,
            "有效次數(±5%)": valid_count,
            "有效比例": f"{valid_ratio * 100:.1f}%",
            "獲利次數": positive_count,
            "虧損次數": negative_count,
            "歷史勝率(%)": round(win_rate * 100, 1),
            "平均報酬(%)": round(avg_return * 100, 2),
            "最大獲利(%)": round(max_gain * 100, 1),
            "最大虧損(%)": round(max_loss * 100, 1),
            "目前RSI": round(float(rsi.iloc[-1]), 1) if not pd.isna(rsi.iloc[-1]) else np.nan,
            "目前季線乖離(%)": round(float(bias60.iloc[-1]), 1) if not pd.isna(bias60.iloc[-1]) else np.nan,
            "近期訊號": recent_text,
            "推薦分數": round(recommendation_score, 1),
            "_score": recommendation_score,
            "原本績效篩選": "通過" if valid_count >= 1 and win_rate >= 0.5 and avg_return > 0 else "未通過",
        })

    return rows

# =========================
# 表格整理
# =========================
def build_strategy_summary_table(report_df):
    if report_df is None or report_df.empty:
        return pd.DataFrame()

    def join_unique(series):
        items = []
        for x in series.dropna().astype(str):
            if x and x not in items:
                items.append(x)
        return "、".join(items)

    rows = []
    for stock_code, g in report_df.groupby("股票代碼"):
        g2 = g.sort_values("_score", ascending=False)
        best = g2.iloc[0]
        strategy_count = g2["策略跡象"].nunique()
        max_score = float(g2["推薦分數"].max())
        avg_return = float(g2["平均報酬(%)"].mean())

        rows.append({
            "股票代碼": stock_code,
            "符合策略數": strategy_count,
            "符合策略列表": join_unique(g2["策略跡象"]),
            "最佳策略": best["策略跡象"],
            "最高推薦分數": round(max_score, 1),
            "總發生次數": int(g2["發生次數"].sum()),
            "平均發生次數": round(float(g2["發生次數"].mean()), 1),
            "平均歷史勝率%": round(float(g2["歷史勝率(%)"].mean()), 1),
            "平均報酬%": round(avg_return, 2),
            "最大獲利%": round(float(g2["最大獲利(%)"].max()), 1),
            "最大虧損%": round(float(g2["最大虧損(%)"].min()), 1),
            "現價": best["現價"],
            "最新成交量張數": best["最新成交量張數"],
            "5日均量張數": best["5日均量張數"],
            "量比": best["量比"],
            "量能狀態": best["量能狀態"],
            "日線結構": best.get("日線結構", ""),
            "日線結構成立": bool(best.get("日線結構成立", False)),
            "目前ATR": best["目前ATR"],
            "ATR波動%": best["ATR波動%"],
            "ATR停損價": best["ATR停損價"],
            "ATR停利價": best["ATR停利價"],
            "目前RSI": best["目前RSI"],
            "目前季線乖離%": best["目前季線乖離(%)"],
            "近期訊號": best["近期訊號"],
            "資料最新交易日": best["資料最新交易日"],
            "原本績效篩選統計": join_unique(g2["原本績效篩選"]),
            "_排序分數": strategy_count * 100 + max_score + avg_return,
        })

    summary_df = pd.DataFrame(rows)
    summary_df = summary_df.sort_values(
        ["符合策略數", "最高推薦分數", "平均歷史勝率%", "平均報酬%"],
        ascending=[False, False, False, False]
    ).reset_index(drop=True)
    summary_df.insert(0, "統計排名", range(1, len(summary_df) + 1))
    return summary_df


def build_three_tables(summary_df, min_daily_volume_lots=300, vol_threshold=1.1, use_hh_hl_bonus=True, filter_mode="寬鬆雷達"):
    if summary_df is None or summary_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = summary_df.copy()
    df["_最新成交量張數"] = pd.to_numeric(df["最新成交量張數"], errors="coerce").fillna(0)
    df["_量比"] = pd.to_numeric(df["量比"], errors="coerce").fillna(0)
    df["_最高推薦分數"] = pd.to_numeric(df["最高推薦分數"], errors="coerce").fillna(0)
    df["_平均歷史勝率"] = pd.to_numeric(df["平均歷史勝率%"], errors="coerce").fillna(0)
    df["_平均報酬"] = pd.to_numeric(df["平均報酬%"], errors="coerce").fillna(0)
    df["_符合策略數"] = pd.to_numeric(df["符合策略數"], errors="coerce").fillna(0)
    df["_平均發生次數"] = pd.to_numeric(df["平均發生次數"], errors="coerce").fillna(0)

    strategy_text = df["符合策略列表"].astype(str)
    bottom_keywords = ["RSI低檔", "季線負乖離", "布林下軌", "KD+RSI", "底部背離"]
    df["_有底部策略"] = strategy_text.apply(lambda x: any(k in x for k in bottom_keywords))
    df["_有ATR轉強"] = strategy_text.str.contains("ATR轉強", na=False)
    df["_成交量達標"] = df["_最新成交量張數"] >= float(min_daily_volume_lots)
    df["_放量"] = (df["量能狀態"].astype(str).str.contains("放量", na=False)) | (df["_量比"] >= float(vol_threshold))
    if "日線結構成立" in df.columns:
        df["_日線結構成立"] = df["日線結構成立"].astype(bool)
    else:
        df["_日線結構成立"] = False

    recent_text = df["近期訊號"].astype(str)
    df["_近期今日昨日"] = recent_text.str.contains("今日|昨日", regex=True, na=False)

    # 日線頭頭高、底底高只做加分提醒，不當硬性門檻。
    # 原本硬卡會太慢，很多剛從底部轉強的股票會被刪掉。
    df["_結構加分"] = np.where(df["_日線結構成立"] & bool(use_hh_hl_bonus), 5, 0)

    # 三種篩選強度：
    # 寬鬆雷達：成交量不再硬刪，只要有底部訊號，並且有任一轉強跡象或分數不差就列入。
    # 標準：底部 + 成交量達標 + ATR轉強或放量。
    # 嚴格：標準條件再加多策略與分數。
    mode = str(filter_mode)
    if mode == "嚴格":
        df["_轉強候選"] = (
            df["_有底部策略"]
            & df["_成交量達標"]
            & (df["_有ATR轉強"] | df["_放量"])
            & (df["_符合策略數"] >= 2)
            & (df["_最高推薦分數"] >= 50)
        )
        df["_精選買進"] = (
            df["_轉強候選"]
            & (df["_平均報酬"] > 0)
            & (df["_平均發生次數"] >= 3)
        )
    elif mode == "標準":
        df["_轉強候選"] = df["_有底部策略"] & df["_成交量達標"] & (df["_有ATR轉強"] | df["_放量"])
        df["_精選買進"] = (
            df["_轉強候選"]
            & (df["_符合策略數"] >= 1)
            & (df["_最高推薦分數"] >= 45)
            & (df["_平均報酬"] >= 0)
            & (df["_平均發生次數"] >= 2)
        )
    else:
        df["_轉強候選"] = (
            df["_有底部策略"]
            & (
                df["_放量"]
                | df["_有ATR轉強"]
                | df["_日線結構成立"]
                | (df["_最高推薦分數"] >= 40)
                | (df["_符合策略數"] >= 2)
            )
        )
        df["_精選買進"] = (
            df["_轉強候選"]
            & (df["_最高推薦分數"] >= 35)
            & (df["_平均發生次數"] >= 2)
            & ((df["_平均報酬"] >= -1.0) | (df["_平均歷史勝率"] >= 50))
        )

    df["_底部觀察"] = df["_有底部策略"] & (~df["_轉強候選"])

    def status(row):
        parts = ["成交量達標" if row["_成交量達標"] else "成交量未達標"]
        parts.append("ATR轉強" if row["_有ATR轉強"] else "未ATR轉強")
        parts.append("放量" if row["_放量"] else "未放量")
        if bool(use_hh_hl_bonus):
            parts.append("結構加分" if row["_日線結構成立"] else "結構未成形")
        return "、".join(parts)

    df["狀態"] = df.apply(status, axis=1)
    df["結構加分"] = df["_結構加分"].astype(int)
    df["操作建議"] = np.where(
        df["_精選買進"] & df["_日線結構成立"],
        "最優先觀察",
        np.where(df["_精選買進"], "優先觀察", np.where(df["_轉強候選"], "可觀察", "只觀察"))
    )

    base_cols = [
        "股票代碼", "符合策略數", "符合策略列表", "最佳策略", "操作建議", "狀態", "原本績效篩選統計",
        "最高推薦分數", "結構加分", "總發生次數", "平均發生次數", "平均歷史勝率%", "平均報酬%", "最大獲利%", "最大虧損%",
        "現價", "最新成交量張數", "5日均量張數", "量比", "量能狀態", "日線結構", "目前ATR", "ATR波動%", "ATR停損價", "ATR停利價",
        "目前RSI", "目前季線乖離%", "近期訊號", "資料最新交易日"
    ]

    def finalize(tdf, rank_col):
        if tdf.empty:
            return tdf.drop(columns=[c for c in tdf.columns if c.startswith("_")], errors="ignore")
        tdf = tdf.sort_values(
            ["_符合策略數", "_最高推薦分數", "_結構加分", "_最新成交量張數", "_平均歷史勝率"],
            ascending=[False, False, False, False, False]
        ).reset_index(drop=True)
        tdf.insert(0, rank_col, range(1, len(tdf) + 1))
        tdf = tdf.drop(columns=[c for c in tdf.columns if c.startswith("_")], errors="ignore")
        return tdf[[rank_col] + [c for c in base_cols if c in tdf.columns]]

    best_df = finalize(df[df["_精選買進"]].copy(), "觀察排名")
    buy_df = finalize(df[df["_轉強候選"]].copy(), "排名")
    watch_df = finalize(df[df["_底部觀察"]].copy(), "排名")
    return best_df, buy_df, watch_df

# =========================
# 掃描主流程
# =========================
def run_scan(stocks_list):
    results = []
    total = len(stocks_list)
    batch_size = 30
    found_count = 0

    st.subheader("即時掃描結果")
    placeholder = st.empty()
    progress = st.progress(0, text="開始掃描...")

    for i in range(0, total, batch_size):
        batch = stocks_list[i:i + batch_size]
        progress.progress(i / max(total, 1), text=f"掃描中 {i}/{total}，已發現 {found_count} 筆")

        try:
            download_period = "10y" if selected_base_date is not None else "90d"
            data = yf.download(batch, period=download_period, progress=False, group_by="ticker", auto_adjust=False)
        except Exception:
            continue

        for ticker in batch:
            try:
                if isinstance(data.columns, pd.MultiIndex):
                    if ticker not in data.columns.levels[0]:
                        continue
                    stock_df = data[ticker].dropna()
                else:
                    stock_df = data.dropna()

                if not quick_prefilter(stock_df, selected_strategies, vol_threshold, fresh_days, selected_base_date, atr_period):
                    continue

                stock_results = backtest_stock(
                    ticker,
                    selected_strategies,
                    holding_days,
                    vol_threshold,
                    fresh_days,
                    selected_base_date,
                    atr_period,
                    atr_stop_mult,
                    atr_take_mult,
                    hh_hl_period,
                )
                results.extend(stock_results)
                found_count += len(stock_results)

                if results:
                    temp_df = pd.DataFrame(results).sort_values("_score", ascending=False).reset_index(drop=True)
                    temp_df.insert(0, "推薦排名", range(1, len(temp_df) + 1))
                    placeholder.dataframe(temp_df.drop(columns=["_score"], errors="ignore"), use_container_width=True, hide_index=True)
            except Exception:
                continue

        time.sleep(0.2)

    progress.progress(1.0, text="掃描完成")
    return pd.DataFrame(results)

# =========================
# 手機卡片顯示
# =========================
def show_mobile_cards(df, title, max_cards=10):
    if df is None or df.empty:
        st.info(f"目前沒有{title}。")
        return

    show_df = df.head(int(max_cards)).copy()
    for _, row in show_df.iterrows():
        rank = row.get("觀察排名", row.get("排名", ""))
        code = row.get("股票代碼", "")
        action = row.get("操作建議", "")
        price = row.get("現價", "")
        score = row.get("最高推薦分數", "")
        ret = row.get("平均報酬%", "")
        win = row.get("平均歷史勝率%", "")
        vol = row.get("量比", "")
        structure = row.get("日線結構", "")
        recent = row.get("近期訊號", "")
        strategy = row.get("最佳策略", "")
        status = row.get("狀態", "")
        stop_price = row.get("ATR停損價", "")
        take_price = row.get("ATR停利價", "")

        action_class = "mobile-good" if "優先" in str(action) or "最優先" in str(action) else "mobile-warn"
        card_html = f"""
        <div class="mobile-card">
          <div class="mobile-title">#{rank}　{code}　{price}</div>
          <div class="mobile-sub"><span class="{action_class}">{action}</span>｜{strategy}</div>
          <div class="mobile-tags">
            分數：{score}｜勝率：{win}%｜均報酬：{ret}%｜量比：{vol}<br>
            結構：{structure}｜訊號：{recent}<br>
            ATR停損：{stop_price}｜ATR停利：{take_price}<br>
            狀態：{status}
          </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)


def compact_table(df):
    if df is None or df.empty:
        return df
    keep_cols = [
        "觀察排名", "排名", "股票代碼", "操作建議", "現價", "最佳策略",
        "最高推薦分數", "平均歷史勝率%", "平均報酬%", "量比", "日線結構", "近期訊號",
        "ATR停損價", "ATR停利價", "狀態"
    ]
    return df[[c for c in keep_cols if c in df.columns]]


def show_responsive_section(title, caption, df, empty_name, rank_col_hint="排名"):
    """同一份結果，同時支援手機與電腦。"""
    st.markdown(f"## {title}")
    st.caption(caption)

    if df is None or df.empty:
        st.info(f"目前沒有{empty_name}。")
        return

    mode = str(view_mode)

    if mode == "電腦模式":
        st.dataframe(df, use_container_width=True, hide_index=True, height=520)
        with st.expander("展開：手機重點卡片預覽"):
            show_mobile_cards(df, empty_name, max_cards=10)
    elif mode == "手機模式":
        show_mobile_cards(df, empty_name, max_cards=10)
        with st.expander("展開：手機短表格"):
            st.dataframe(compact_table(df), use_container_width=True, hide_index=True)
        with st.expander("展開：完整欄位表格"):
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        # 自動模式：手機先看卡片；電腦可直接展開完整表格。
        show_mobile_cards(df, empty_name, max_cards=8)
        tab1, tab2 = st.tabs(["重點短表", "完整電腦表"])
        with tab1:
            st.dataframe(compact_table(df), use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(df, use_container_width=True, hide_index=True, height=520)

# =========================
# 執行與輸出
# =========================
if analyze_btn:
    if not selected_strategies:
        st.error("請至少勾選一個策略。")
        st.stop()

    if scan_mode == "全市場掃描":
        stocks = get_tw_stock_list(market_type)
        st.info(f"開始掃描 {len(stocks)} 檔 {market_type} 股票。")
    else:
        stocks = [s.strip().upper().replace(" ", "") for s in stock_input.replace("\n", ",").split(",") if s.strip()]
        if market_type == "上市":
            stocks = [s for s in stocks if s.endswith(".TW")]
        elif market_type == "上櫃":
            stocks = [s for s in stocks if s.endswith(".TWO")]
        st.info(f"開始分析 {len(stocks)} 檔自訂股票。")

    report_df = run_scan(stocks)

    if report_df.empty:
        st.warning("沒有找到符合條件的股票。可以放寬近期窗口、降低放量倍數、降低最低成交張數。")
    else:
        report_df = report_df.sort_values("_score", ascending=False).reset_index(drop=True)
        report_df.insert(0, "推薦排名", range(1, len(report_df) + 1))
        summary_df = build_strategy_summary_table(report_df)
        best_df, buy_df, watch_df = build_three_tables(summary_df, min_daily_volume_lots, vol_threshold, use_hh_hl_bonus, filter_mode)

        st.success(f"掃描完成，共找到 {len(summary_df)} 檔股票有訊號。")

        show_responsive_section(
            "1. 優先觀察名單",
            "最先研究的名單，不是直接買進訊號。手機看卡片，電腦看完整表格。",
            best_df,
            "優先觀察名單",
        )

        show_responsive_section(
            "2. 轉強候選",
            "有底部訊號，再加上放量、ATR轉強、日線結構、分數或多策略其中之一。",
            buy_df,
            "轉強候選",
        )

        show_responsive_section(
            "3. 底部雷達觀察",
            "只有底部味道，還沒轉強。手機先看前幾檔，電腦可看完整欄位。",
            watch_df,
            "底部雷達觀察",
        )

        st.download_button(
            "下載完整明細 CSV",
            report_df.drop(columns=["_score"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
            file_name="responsive_atr_scan_detail.csv",
            mime="text/csv",
            use_container_width=True,
        )
