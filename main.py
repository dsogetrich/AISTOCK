import streamlit as st

# --- [新增] 密碼保護功能 ---
def check_password():
    """如果密碼正確，返回 True"""
    def password_entered():
        if st.session_state["password"] == "79979":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔐 台股AI戰情室 - 身份驗證")
        st.text_input("請輸入訪問密碼以開啟分析系統", type="password", on_change=password_entered, key="password")
        st.info("提示：密碼為 5 位數字")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔐 台股AI戰情室 - 身份驗證")
        st.text_input("密碼不正確，請重新輸入", type="password", on_change=password_entered, key="password")
        st.error("😕 密碼錯誤，存取被拒絕。")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- 核心功能開始 ---
from data_loader import StockDataLoader
from chart_plotter import plot_combined_chart, plot_revenue_chart, plot_quarterly_chart
from ai_engine import analyze_stock_trend, generate_quick_summary
import base64
from pathlib import Path
import pandas as pd
import re

def _quick_summary_line(df: pd.DataFrame, full_name: str) -> str:
    if df is None or df.empty or 'close' not in df.columns: return full_name
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    close = float(pd.to_numeric(latest.get('close', 0), errors='coerce') or 0)
    prev_close = float(pd.to_numeric(prev.get('close', close), errors='coerce') or close)
    chg = close - prev_close
    chg_pct = (chg / prev_close * 100.0) if prev_close else 0.0
    vol = int(pd.to_numeric(latest.get('volume', 0), errors='coerce') or 0)
    return f"{full_name} 收盤：{close:.2f} ({chg:+.2f} / {chg_pct:+.2f}%) | 量 {vol:,d} 張"

def _highlight_ai_report(md: str) -> str:
    if not isinstance(md, str): return md
    out_lines = []
    for line in md.split('\n'):
        if "第" in line and "章" in line:
            out_lines.append(f"<div style='font-size:30px;font-weight:900;color:#FFD700;border-bottom:2px solid #FFD700;'>{line}</div>")
        else:
            out_lines.append(line)
    return '\n'.join(out_lines)

st.set_page_config(page_title="台股AI戰情室", layout="wide", page_icon="📈")

# 自定義 CSS
st.markdown("""
<style>
.sidebar-footer { position: fixed; bottom: 0; width: 250px; background: #0e1117; padding: 10px; border-top: 1px solid #444; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🚀 控制中心")
api_key = st.sidebar.text_input("Gemini API Key", type="password")
stock_id = st.sidebar.text_input("股票代碼", value="2330")
run_analysis = st.sidebar.button("🔍 開始分析", type="primary")

if run_analysis and stock_id:
    loader = StockDataLoader()
    df, error, stock_name = loader.get_combined_data(stock_id, 250, True)
    if error:
        st.error(error)
    else:
        st.title(f"📊 {stock_id} {stock_name}")
        st.info(_quick_summary_line(df, stock_name))
        fig = plot_combined_chart(df, stock_id, stock_name, {'MA20':True, 'MA100':True})
        st.plotly_chart(fig, use_container_width=True)
        if api_key:
            with st.spinner("AI 分析中..."):
                report = analyze_stock_trend(api_key, stock_id, stock_name, df)
                st.markdown(_highlight_ai_report(report), unsafe_allow_html=True)

st.sidebar.markdown('<div class="sidebar-footer">⚠️ 僅供研究使用，投資有風險</div>', unsafe_allow_html=True)
