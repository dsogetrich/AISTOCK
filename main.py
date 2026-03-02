import streamlit as st

# --- [新增] 密碼保護功能 ---
def check_password():
    """如果密碼正確，返回 True"""
    def password_entered():
        # 這裡設定你的專屬密碼
        if st.session_state["password"] == "79979":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 驗證後刪除暫存密碼更安全
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 第一次進入，顯示輸入框
        st.markdown("### 🔐 台股AI戰情室 - 身份驗證")
        st.text_input("請輸入訪問密碼以開啟分析系統", type="password", on_change=password_entered, key="password")
        st.info("提示：密碼為 5 位數字")
        return False
    elif not st.session_state["password_correct"]:
        # 密碼錯誤，顯示錯誤並重新輸入
        st.markdown("### 🔐 台股AI戰情室 - 身份驗證")
        st.text_input("密碼不正確，請重新輸入", type="password", on_change=password_entered, key="password")
        st.error("😕 密碼錯誤，存取被拒絕。")
        return False
    else:
        # 密碼正確
        return True

# 執行密碼檢查，若不通過則停止執行後續程式碼
if not check_password():
    st.stop()

# --- 原本的程式碼開始 ---
print('[INFO] main.py patched v9 loaded with Password Protection')
from data_loader import StockDataLoader
from chart_plotter import plot_combined_chart, plot_revenue_chart, plot_quarterly_chart
from ai_engine import analyze_stock_trend, generate_quick_summary
import base64
from pathlib import Path
import pandas as pd
import re

def _quick_summary_line(df: pd.DataFrame, full_name: str) -> str:
    """K線上方摘要：收盤固定 2 位小數"""
    if df is None or df.empty or 'close' not in df.columns:
        return full_name
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    try:
        close = float(latest['close'])
    except Exception:
        close = float(pd.to_numeric(latest.get('close', 0), errors='coerce') or 0)
    try:
        prev_close = float(prev['close'])
    except Exception:
        prev_close = float(pd.to_numeric(prev.get('close', close), errors='coerce') or close)

    chg = close - prev_close
    chg_pct = (chg / prev_close * 100.0) if prev_close else 0.0

    vol = 0
    if 'volume' in df.columns:
        try:
            vol = int(round(float(latest.get('volume', 0))))
        except Exception:
            vol = int(pd.to_numeric(latest.get('volume', 0), errors='coerce') or 0)

    return f"{full_name} 收盤：{close:.2f} ({chg:+.2f} / {chg_pct:+.2f}%) | 量 {vol:,d} 張"


def _highlight_ai_report(md: str) -> str:
    """AI 報告美化"""
    if not isinstance(md, str):
        return md
    md = md.replace('\r\n', '\n').replace('\r', '\n')
    out_lines = []
    for raw in md.split('\n'):
        line = raw.strip()
        if line == "":
            out_lines.append("")
            continue
        _chapter_m = re.match(r'^#{0,6}\s*\**\s*(第[一二三四五]章[^*\n]*)\**\s*$', line)
        if _chapter_m:
            title = _chapter_m.group(1).strip().replace('**', '')
            out_lines.append(f"<div style='font-size:36px;font-weight:900;line-height:1.6;margin:28px 0 16px;color:#FFD700;border-bottom:2px solid #FFD700;padding-bottom:8px'>{title}</div>")
            continue
        m1 = re.match(r'^(#{1,6})\s*(.+)$', line)
        if m1:
            level = len(m1.group(1))
            title = m1.group(2).strip().replace('**', '')
            size = {1:32, 2:28, 3:26, 4:24, 5:22, 6:20}.get(level, 18)
            out_lines.append(f"<div style='font-size:{size}px;font-weight:800;line-height:1.25;margin:14px 0 8px;color:#ffffff'>{title}</div>")
            continue
        m2 = re.match(r'^\*\*(.+?)\*\*\s*[:：]*\s*$', line)
        if m2:
            title = m2.group(1).strip().replace('**', '')
            out_lines.append(f"<div style='font-size:26px;font-weight:800;margin:16px 0 10px;color:#4EC9B0;'>{title}</div>")
            continue
        
        line2 = raw
        # 關鍵詞分色
        line2 = re.sub(r'大紅K|中紅K|小紅K', r"<span style='color:#FF4444;font-weight:800'>\1</span>", line2)
        line2 = re.sub(r'大黑K|中黑K|小黑K', r"<span style='color:#00DD00;font-weight:800'>\1</span>", line2)
        line2 = re.sub(r'多頭|上漲|突破|支撐|買超', r"<span style='color:#FF4444;font-weight:800'>\1</span>", line2)
        line2 = re.sub(r'空頭|下跌|跌破|壓力|賣超', r"<span style='color:#00DD00;font-weight:800'>\1</span>", line2)
        
        out_lines.append(line2)
    return '\n'.join(out_lines)

st.set_page_config(page_title="台股AI戰情室", layout="wide", page_icon="📈", initial_sidebar_state="expanded")

# 自定義CSS
st.markdown("""
<style>
.ai-report{font-size:26px;line-height:2.0;}
.sidebar-logo { text-align: center; padding: 15px 0; border-bottom: 2px solid #444; }
.sidebar-logo img { width: 150px; border-radius: 10px