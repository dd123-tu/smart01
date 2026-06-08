
import ssl, time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="台股雷達｜全市場快速版", page_icon="📱", layout="wide")
TWSE_SSL_CONTEXT = ssl._create_unverified_context()

st.title("台股優先觀察雷達｜全市場快速版")
st.caption("先全市場快速掃描，再只對候選股做歷史統計，避免手機與雲端一直轉圈。")
st.info("這版是給手機 / Streamlit Cloud 用的全市場快速版：先快速找候選，再只補前 30 名歷史統計。")

with st.sidebar:
    st.header("掃描設定")
    market_type = st.radio("市場類型", ["上市", "上櫃", "全部"], index=0)
    scan_mode = st.radio("掃描模式", ["全市場掃描", "自訂股票名單"], index=0)
    stock_input = ""
    if scan_mode == "自訂股票名單":
        stock_input = st.text_area("股票代碼，逗號分隔", value="2498.TW,2330.TW,2317.TW,2356.TW,2376.TW", height=80)
    max_scan_count = st.number_input("全市場最大掃描檔數", value=800, min_value=100, max_value=3000, step=100)
    quick_period = st.selectbox("快速掃描資料長度", ["6mo", "1y", "2y"], index=1)
    history_period = st.selectbox("候選股歷史統計長度", ["2y", "5y", "10y"], index=1)
    fresh_days = st.number_input("近期窗口天數", value=10, min_value=3, max_value=30)
    vol_threshold = st.number_input("放量倍數", value=1.1, min_value=0.8, max_value=3.0, step=0.1)
    min_daily_volume_lots = st.number_input("提醒用最低成交張數", value=300, min_value=0, max_value=200000, step=100)
    holding_days = st.number_input("歷史觀察天數", value=10, min_value=3, max_value=60)
    atr_period = st.number_input("ATR週期", value=14, min_value=5, max_value=60)
    atr_stop_mult = st.number_input("ATR停損倍數", value=1.5, min_value=0.5, max_value=5.0, step=0.1)
    atr_take_mult = st.number_input("ATR停利倍數", value=2.0, min_value=0.5, max_value=10.0, step=0.1)
    selected = st.multiselect("啟用策略", ["RSI低檔","季線負乖離","布林下軌","KD+RSI雙低檔","底部背離","ATR轉強","MACD翻紅低位"], default=["RSI低檔","季線負乖離","布林下軌","KD+RSI雙低檔","底部背離","ATR轉強"])
    start_btn = st.button("啟動全市場雷達", type="primary", use_container_width=True)

@st.cache_data(ttl=86400, show_spinner=False)
def get_tw_stock_list(market_type="上市"):
    stocks=[]; sources=[]
    if market_type in ("上市","全部"): sources.append(("https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", ".TW"))
    if market_type in ("上櫃","全部"): sources.append(("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4", ".TWO"))
    try:
        import urllib.request
        orig = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **kw: orig(*a, **{**kw, "context": TWSE_SSL_CONTEXT})
        try:
            for url,suffix in sources:
                table = pd.read_html(url)[0]
                table.columns = table.iloc[0]
                table = table.iloc[1:]
                for value in table["有價證券代號及名稱"].dropna():
                    code = str(value).split()[0]
                    if code.isdigit() and len(code)==4: stocks.append(f"{code}{suffix}")
        finally:
            urllib.request.urlopen = orig
        return sorted(set(stocks))
    except Exception:
        if market_type in ("上市","全部"):
            stocks += [f"{i:04d}.TW" for i in range(1101,2000)]
            stocks += [f"{i:04d}.TW" for i in range(2301,3700)]
            stocks += [f"{i:04d}.TW" for i in range(6001,6800)]
        if market_type in ("上櫃","全部"):
            stocks += [f"{i:04d}.TWO" for i in range(3001,8999,5)]
        return sorted(set(stocks))

def get_one_from_batch(data, ticker):
    if data is None or data.empty: return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0): sub=data[ticker].copy()
        else: return pd.DataFrame()
    else:
        sub=data.copy()
    return sub.dropna()

def calc_basic(df, vol_mult=1.1, atr_period=14):
    close=df["Close"]; high=df["High"]; low=df["Low"]; volume=df["Volume"]
    delta=close.diff(); gain=delta.where(delta>0,0).rolling(14).mean(); loss=(-delta.where(delta<0,0)).rolling(14).mean()
    rsi=100-(100/(1+(gain/loss)))
    ma20=close.rolling(20).mean(); ma60=close.rolling(60).mean(); std20=close.rolling(20).std()
    lower_band=ma20-2*std20; bias60=(close-ma60)/ma60*100
    low9=low.rolling(9).min(); high9=high.rolling(9).max(); rsv=(close-low9)/(high9-low9)*100
    k=rsv.ewm(com=2,adjust=False).mean()
    ema12=close.ewm(span=12,adjust=False).mean(); ema26=close.ewm(span=26,adjust=False).mean()
    macd=ema12-ema26; macd_sig=macd.ewm(span=9,adjust=False).mean(); macd_hist=macd-macd_sig
    prev_close=close.shift(1); tr=pd.concat([(high-low),(high-prev_close).abs(),(low-prev_close).abs()],axis=1).max(axis=1)
    atr=tr.rolling(int(atr_period)).mean(); atr_ma20=atr.rolling(20).mean(); atr_pct=atr/close*100
    vol_ma5=volume.rolling(5).mean(); vol_ratio=volume/vol_ma5; vol_confirm=vol_ratio>=vol_mult
    kd_div=(k<30)&(k>k.shift(1))&(close<close.shift(1))
    macd_div=(close<close.rolling(20).min().shift(1))&(macd_hist>macd_hist.shift(1))
    signals={
        "RSI低檔": rsi<35,
        "季線負乖離": bias60<-10,
        "布林下軌": close<lower_band,
        "KD+RSI雙低檔": (k<25)&(rsi<40),
        "底部背離": kd_div|macd_div,
        "ATR轉強": (atr>atr_ma20)&(close>close.shift(1))&vol_confirm,
        "MACD翻紅低位": (macd_hist>0)&(macd_hist.shift(1)<=0)&(macd<0),
    }
    return signals,rsi,bias60,atr,atr_pct,vol_ratio

def hhhl(df, days=5):
    if len(df)<days*2+2: return False
    return bool(df["High"].tail(days).max()>df["High"].iloc[-days*2:-days].max() and df["Low"].tail(days).min()>df["Low"].iloc[-days*2:-days].min() and df["Close"].iloc[-1]>df["Close"].iloc[-days])

def quick_scan_stock(ticker, df):
    if df.empty or len(df)<80: return None
    if any(c not in df.columns for c in ["Open","High","Low","Close","Volume"]): return None
    signals,rsi,bias60,atr,atr_pct,vol_ratio = calc_basic(df, vol_threshold, atr_period)
    selected_signals=[]; latest_idx=None
    for name in selected:
        sig=signals.get(name)
        if sig is not None and sig.tail(int(fresh_days)).any():
            selected_signals.append(name)
            dt=sig.tail(int(fresh_days))[sig.tail(int(fresh_days))].index[-1]
            if latest_idx is None or dt>latest_idx: latest_idx=dt
    if not selected_signals: return None
    bottom_names=["RSI低檔","季線負乖離","布林下軌","KD+RSI雙低檔","底部背離"]
    has_bottom=any(x in selected_signals for x in bottom_names); has_atr="ATR轉強" in selected_signals
    close=df["Close"]; volume=df["Volume"]
    latest_vol_lots=float(volume.iloc[-1])/1000 if not pd.isna(volume.iloc[-1]) else 0
    vr=float(vol_ratio.iloc[-1]) if not pd.isna(vol_ratio.iloc[-1]) and np.isfinite(vol_ratio.iloc[-1]) else 0
    vol_ok=vr>=float(vol_threshold); vol_enough=latest_vol_lots>=float(min_daily_volume_lots); structure_ok=hhhl(df,5)
    score=0
    score += len(selected_signals)*12 + (18 if has_bottom else 0) + (18 if has_atr else 0) + (12 if vol_ok else 0) + (10 if vol_enough else 0) + (12 if structure_ok else 0)
    if not pd.isna(rsi.iloc[-1]): score += max(0,min(15,(40-float(rsi.iloc[-1]))/2))
    if not pd.isna(bias60.iloc[-1]) and bias60.iloc[-1]<0: score += max(0,min(10,abs(float(bias60.iloc[-1]))/2))
    if not has_bottom and score<35: return None
    level="轉強候選" if has_bottom and (has_atr or vol_ok or structure_ok or len(selected_signals)>=2) else "底部雷達觀察"
    action="優先觀察" if level=="轉強候選" and score>=55 else ("可觀察" if level=="轉強候選" else "只觀察")
    days_ago=len(df.loc[latest_idx:])-1 if latest_idx is not None else ""
    return {"股票代碼":ticker,"分層":level,"操作建議":action,"快速分數":round(score,1),"符合策略數":len(selected_signals),"符合策略列表":"、".join(selected_signals),"現價":round(float(close.iloc[-1]),2),"最新成交量張數":round(latest_vol_lots,0),"量比":round(vr,2),"量能狀態":"放量" if vol_ok else "量不足","日線結構":"頭頭高底底高" if structure_ok else "未形成","目前RSI":round(float(rsi.iloc[-1]),1) if not pd.isna(rsi.iloc[-1]) else np.nan,"目前季線乖離%":round(float(bias60.iloc[-1]),1) if not pd.isna(bias60.iloc[-1]) else np.nan,"目前ATR":round(float(atr.iloc[-1]),2) if not pd.isna(atr.iloc[-1]) else np.nan,"ATR波動%":round(float(atr_pct.iloc[-1]),2) if not pd.isna(atr_pct.iloc[-1]) else np.nan,"ATR停損價":round(float(close.iloc[-1]-atr.iloc[-1]*float(atr_stop_mult)),2) if not pd.isna(atr.iloc[-1]) else np.nan,"ATR停利價":round(float(close.iloc[-1]+atr.iloc[-1]*float(atr_take_mult)),2) if not pd.isna(atr.iloc[-1]) else np.nan,"近期訊號":pd.Timestamp(latest_idx).strftime("%Y-%m-%d")+f" ({days_ago}天前)" if latest_idx is not None else "","資料最新交易日":pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d"),"_score":float(score)}

@st.cache_data(ttl=1800, show_spinner=False)
def download_batch(tickers, period):
    return yf.download(list(tickers), period=period, progress=False, group_by="ticker", auto_adjust=False, threads=True)

def history_stats(ticker):
    try:
        df=yf.download(ticker,period=history_period,progress=False,auto_adjust=False,threads=False)
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.droplevel(1)
        df=df.dropna()
        if df.empty or len(df)<150: return {}
        signals,_,_,_,_,_=calc_basic(df,vol_threshold,atr_period); close=df["Close"]; rets=[]; occ=0
        for name in selected:
            sig=signals.get(name)
            if sig is None: continue
            for i in range(80,len(df)-int(holding_days)):
                if bool(sig.iloc[i]):
                    occ+=1; entry=close.iloc[i]; exit_p=close.iloc[i+int(holding_days)]
                    if entry>0: rets.append((exit_p-entry)/entry)
        if not rets: return {"發生次數":0,"歷史勝率%":0,"平均報酬%":0,"最大獲利%":0,"最大虧損%":0}
        arr=np.array(rets); valid=arr[np.abs(arr)>=0.03]
        if len(valid)==0: valid=arr
        return {"發生次數":int(occ),"有效次數(±3%)":int(len(valid)),"歷史勝率%":round(float((valid>0).sum()/len(valid)*100),1),"平均報酬%":round(float(valid.mean()*100),2),"最大獲利%":round(float(valid.max()*100),1),"最大虧損%":round(float(valid.min()*100),1)}
    except Exception:
        return {}

def run_scan(stocks):
    progress=st.progress(0,text="準備掃描..."); status=st.empty(); found=st.empty(); results=[]; batch_size=50; total=len(stocks)
    for start in range(0,total,batch_size):
        batch=stocks[start:start+batch_size]
        status.info(f"正在抓資料：{start+1} ~ {min(start+batch_size,total)} / {total}，目前找到 {len(results)} 筆")
        try: data=download_batch(tuple(batch),quick_period)
        except Exception: continue
        for ticker in batch:
            try:
                row=quick_scan_stock(ticker,get_one_from_batch(data,ticker))
                if row is not None: results.append(row)
            except Exception: pass
        if results:
            tmp=pd.DataFrame(results).sort_values("_score",ascending=False).head(50)
            found.dataframe(tmp.drop(columns=["_score"],errors="ignore"),use_container_width=True,hide_index=True)
        progress.progress(min((start+batch_size)/total,1.0),text=f"全市場快速掃描中... {min(start+batch_size,total)} / {total}")
        time.sleep(0.05)
    progress.progress(1.0,text="快速掃描完成")
    if not results: return pd.DataFrame()
    df=pd.DataFrame(results).sort_values("_score",ascending=False).reset_index(drop=True); df.insert(0,"排名",range(1,len(df)+1))
    hist=st.empty(); top_n=min(30,len(df))
    for i in range(top_n):
        ticker=df.loc[i,"股票代碼"]; hist.info(f"正在補前30名歷史統計：{i+1}/{top_n} {ticker}")
        for k,v in history_stats(ticker).items(): df.loc[i,k]=v
    hist.success("歷史統計完成")
    df["優先觀察"]=(df["分層"].eq("轉強候選") & (pd.to_numeric(df["快速分數"],errors="coerce").fillna(0)>=45))
    return df.sort_values(["優先觀察","快速分數"],ascending=[False,False]).reset_index(drop=True)

if start_btn:
    if scan_mode=="自訂股票名單": stocks=[s.strip().upper().replace(" ","") for s in stock_input.split(",") if s.strip()]
    else:
        with st.spinner("取得台股清單中..."): stocks=get_tw_stock_list(market_type)
        if len(stocks)>int(max_scan_count):
            st.warning(f"目前清單 {len(stocks)} 檔，這次先掃前 {int(max_scan_count)} 檔。要掃更多可調高最大掃描檔數。")
            stocks=stocks[:int(max_scan_count)]
    st.write(f"本次掃描檔數：**{len(stocks)}**")
    report=run_scan(stocks)
    if report.empty: st.warning("沒有找到符合條件的股票。可放寬近期窗口、降低放量倍數，或增加最大掃描檔數。")
    else:
        priority=report[report["優先觀察"]==True].copy(); turn=report[report["分層"]=="轉強候選"].copy(); watch=report[report["分層"]=="底部雷達觀察"].copy()
        def show_table(title,df):
            st.subheader(title)
            cols=["排名","股票代碼","操作建議","快速分數","符合策略數","符合策略列表","現價","最新成交量張數","量比","量能狀態","日線結構","目前RSI","目前季線乖離%","目前ATR","ATR停損價","ATR停利價","近期訊號","歷史勝率%","平均報酬%","最大虧損%"]
            cols=[c for c in cols if c in df.columns]
            st.dataframe(df[cols],use_container_width=True,hide_index=True)
        show_table("① 優先觀察名單",priority)
        show_table("② 轉強候選",turn)
        show_table("③ 底部雷達觀察",watch)
        with st.expander("完整資料 / 下載 CSV"):
            st.dataframe(report.drop(columns=["_score"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("下載 CSV",report.drop(columns=["_score"],errors="ignore").to_csv(index=False).encode("utf-8-sig"),"tw_stock_radar_result.csv","text/csv")
else:
    st.warning("建議先用：上市 + 最大掃描 800 檔。確認正常後，再慢慢調高。")
    st.markdown("""
### 這版為什麼比較不會卡？
- 舊版：全市場每檔都可能做完整多年回測，手機會一直轉圈。
- 新版：先用近期資料快速掃全市場。
- 只有前 30 名候選股才補歷史統計。
- 可設定最大掃描檔數，避免 Streamlit Cloud 免費雲端被壓死。
""")
