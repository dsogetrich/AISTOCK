import streamlit as st
print('[INFO] main.py patched v9 loaded')
from data_loader import StockDataLoader
from chart_plotter import plot_combined_chart, plot_revenue_chart, plot_quarterly_chart
from ai_engine import analyze_stock_trend, generate_quick_summary
import base64
from pathlib import Path
import pandas as pd
import re

def _quick_summary_line(df: pd.DataFrame, full_name: str) -> str:
    """K線上方摘要：收盤固定 2 位小數（避免 23.35000038 這種浮點顯示）"""
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
    """把 AI 報告做『結構化』美化：不靠寫死關鍵字，改抓標題/章節/欄位格式"""
    if not isinstance(md, str):
        return md

    md = md.replace('\r\n', '\n').replace('\r', '\n')

    out_lines = []
    for raw in md.split('\n'):
        line = raw.strip()

        if line == "":
            out_lines.append("")
            continue

        # 1) 優先偵測「第X章」，無論有無 # 或 **，AI輸出格式不穩定故語意優先
        _chapter_m = re.match(r'^#{0,6}\s*\**\s*(第[一二三四五]章[^*\n]*)\**\s*$', line)
        if _chapter_m:
            title = _chapter_m.group(1).strip().replace('**', '')
            out_lines.append(
                f"<div style='font-size:36px;font-weight:900;line-height:1.6;margin:28px 0 16px;color:#FFD700;border-bottom:2px solid #FFD700;padding-bottom:8px'>{title}</div>"
            )
            continue

        # 1b) 其他 Markdown 標題：# / ## / ### ...
        m1 = re.match(r'^(#{1,6})\s*(.+)$', line)
        if m1:
            level = len(m1.group(1))
            title = m1.group(2).strip().replace('**', '')
            size = {1:32, 2:28, 3:26, 4:24, 5:22, 6:20}.get(level, 18)
            out_lines.append(
                f"<div style='font-size:{size}px;font-weight:800;line-height:1.25;margin:14px 0 8px;color:#ffffff'>{title}</div>"
            )
            continue

        # 2) ✅ 副標題處理（移除所有星號，統一變色）
        # 匹配副標題：**xxx** 或 **xxx：** 或 **xxx::** 
        m2 = re.match(r'^\*\*(.+?)\*\*\s*[:：]*\s*$', line)
        if m2:
            title = m2.group(1).strip()
            # 移除標題內的星號
            title = title.replace('**', '')
            out_lines.append(
                f"<div style='font-size:26px;font-weight:800;margin:16px 0 10px;color:#4EC9B0;'>{title}</div>"
            )
            continue
        
        # ✅ 處理第五章特定副標題（即使沒有**包圍）
        chapter5_subtitles = ['多空方向', '綜合評分依據', '關鍵價位', '積極型操作思路', '保守型操作思路', '風險提示']
        if any(line.strip() == subtitle for subtitle in chapter5_subtitles):
            out_lines.append(
                f"<div style='font-size:26px;font-weight:800;margin:16px 0 10px;color:#4EC9B0;'>{line.strip()}</div>"
            )
            continue
        
        # ✅ 處理小副標題（如「營收趨勢」、「年增率變化」、「技術面」等）+ 條列式
        # 這些通常是單獨一行，且沒有**包圍
        small_subtitle_patterns = [
            '營收趨勢', '年增率變化', '營收高峰', '營收低谷', '動能評估',
            '季營收變化', '季毛利率趨勢', '成本控制能力', '關聯性分析',
            '技術面', '籌碼面', '基本面',
            '第一支撐位', '第二支撐位', '第一壓力位', '第二壓力位', '止損價位',
            '技術性修正風險', '籌碼面不穩定', '基本面壓力', '產業競爭'
        ]
        
        # 如果這行只包含小副標題文字（可能有冒號）
        line_clean = line.strip().rstrip('：:')
        if line_clean in small_subtitle_patterns:
            # 使用條列式呈現，加上圓點
            out_lines.append(
                f"<div style='margin:14px 0 8px 0;'><span style='color:#FF8C42;font-weight:800;font-size:22px'>• {line_clean}</span></div>"
            )
            continue
        
        # ✅ 特殊處理：「趨勢定義為『xxx』」中的『』內容變色
        if '趨勢定義為' in line and '「' in line and '」' in line:
            line = re.sub(r'趨勢定義為\s*「([^」]+)」', r'趨勢定義為「<span style="color:#FFD700;font-weight:900">\1</span>」', line)
            out_lines.append(line)
            continue

        # 3) ✅ 處理項目符號列表（* 開頭的內容）轉換為條列式
        # 匹配「* **xxx** 內容」或「* xxx」
        m_bullet = re.match(r'^\*\s+\*\*([^*]+)\*\*\s*[:：]?\s*(.*)$', line)
        if m_bullet:
            # 項目標題（如「* **支撐位** 內容」）
            label = m_bullet.group(1).strip()
            content = m_bullet.group(2).strip()
            
            if content:  # 如果有內容，顯示在同一行
                out_lines.append(
                    f"<div style='margin:12px 0 6px 20px;line-height:1.8;'><span style='color:#4EC9B0;font-weight:800;font-size:22px'>{label}</span>：{content}</div>"
                )
            else:  # 如果沒內容，只顯示標題
                out_lines.append(
                    f"<div style='margin:12px 0 6px 20px;line-height:1.8;'><span style='color:#4EC9B0;font-weight:800;font-size:22px'>{label}</span></div>"
                )
            continue
        
        # 處理嵌套項目（如「  * 第一短期支撐...」或「- xxx」）
        m_nested = re.match(r'^\s*[-*]\s+(.+)$', line)
        if m_nested:
            content = m_nested.group(1).strip()
            out_lines.append(
                f"<div style='margin:6px 0 6px 40px;line-height:1.8;'>• {content}</div>"
            )
            continue

        # 4) 欄位名：內容（只上色『欄位名』，移除冒號重複）
        m3 = re.match(r'^(•\s*)?([^：]{2,18})(：)(.*)$', line)
        if m3:
            bullet = m3.group(1) or ""
            k = m3.group(2).strip()
            rest = m3.group(4).strip()
            out_lines.append(
                f"{bullet}<span style='color:#FF8C42;font-weight:800'>{k}</span>：{rest}"
            )
            continue

        # 5) ✅ 處理數字格式化與關鍵詞變色
        line2 = raw
        
        # ✅ K線型態分色處理
        # 紅K系列 → 紅色
        for pattern in ['大紅K', '中紅K', '小紅K', '紡錘紅K', '倒鎚紅K', '紅K鎚子']:
            line2 = re.sub(f'({pattern})', r"<span style='color:#FF4444;font-weight:800;background:rgba(255,68,68,0.15);padding:2px 6px;border-radius:3px'>\1</span>", line2)
        # 黑K系列 → 綠色
        for pattern in ['大黑K', '中黑K', '小黑K', '紡錘黑K', '倒鎚黑K', '黑K鎚子']:
            line2 = re.sub(f'({pattern})', r"<span style='color:#00DD00;font-weight:800;background:rgba(0,221,0,0.12);padding:2px 6px;border-radius:3px'>\1</span>", line2)
        # 其他K線型態 → 粉紅色
        for pattern in ['墓碑線', '吊人線', '十字線', 'T字線', '倒T線', '一字線']:
            line2 = re.sub(f'({pattern})', r"<span style='color:#FF69B4;font-weight:800;background:rgba(255,105,180,0.15);padding:2px 6px;border-radius:3px'>\1</span>", line2)
        
        # ✅ 新增：關鍵詞變色（須在處理數字之前，避免干擾）
        # 技術面/籌碼面/基本面 → 水藍色（但排除已經是大標題的情況）
        if not re.search(r'第[一二三四五]章', line2) and '五大維度' not in line2:  # 排除大標題與序言
            line2 = re.sub(r'技術面', r"<span style='color:#5DADE2;font-weight:800'>技術面</span>", line2)
            line2 = re.sub(r'籌碼面', r"<span style='color:#5DADE2;font-weight:800'>籌碼面</span>", line2)
            line2 = re.sub(r'基本面', r"<span style='color:#5DADE2;font-weight:800'>基本面</span>", line2)
        
        # 短期/中期/長期 → 不同顏色
        # 空箱→綠、多箱→紅
        line2 = re.sub(r'空箱', r"<span style='color:#00DD00;font-weight:800'>空箱</span>", line2)
        line2 = re.sub(r'多箱', r"<span style='color:#FF4444;font-weight:800'>多箱</span>", line2)
        # 外資/投信→亮紫
        line2 = re.sub(r'外資', r"<span style='color:#DA70D6;font-weight:800'>外資</span>", line2)
        line2 = re.sub(r'投信', r"<span style='color:#DA70D6;font-weight:800'>投信</span>", line2)
        # MA100→紅底白字；MA20→綠底白字（MA100先處理避免被MA20吃掉）
        line2 = re.sub(r'MA100', r"<span style='background:#CC2200;color:#ffffff;font-weight:900;padding:1px 6px;border-radius:3px'>MA100</span>", line2)
        line2 = re.sub(r'MA20', r"<span style='background:#007700;color:#ffffff;font-weight:900;padding:1px 6px;border-radius:3px'>MA20</span>", line2)
        line2 = re.sub(r'短期(?![趨勢線])', r"<span style='color:#ADFF2F;font-weight:800'>短期</span>", line2)
        line2 = re.sub(r'中期(?![趨勢線])', r"<span style='color:#FF4444;font-weight:800'>中期</span>", line2)
        line2 = re.sub(r'長期(?![趨勢線])', r"<span style='color:#DDA0DD;font-weight:800'>長期</span>", line2)
        
        # 多方相關 → 紅色
        line2 = re.sub(r'多方', r"<span style='color:#FF4444;font-weight:800'>多方</span>", line2)
        line2 = re.sub(r'多頭', r"<span style='color:#FF4444;font-weight:800'>多頭</span>", line2)
        line2 = re.sub(r'上漲', r"<span style='color:#FF4444;font-weight:800'>上漲</span>", line2)
        line2 = re.sub(r'突破', r"<span style='color:#FF4444;font-weight:800'>突破</span>", line2)
        line2 = re.sub(r'支撐', r"<span style='color:#FF4444;font-weight:800'>支撐</span>", line2)
        
        # 空方相關 → 綠色
        line2 = re.sub(r'(?<!多)空方', r"<span style='color:#00DD00;font-weight:800'>空方</span>", line2)
        line2 = re.sub(r'空頭', r"<span style='color:#00DD00;font-weight:800'>空頭</span>", line2)
        line2 = re.sub(r'下跌', r"<span style='color:#00DD00;font-weight:800'>下跌</span>", line2)
        line2 = re.sub(r'跌破', r"<span style='color:#00DD00;font-weight:800'>跌破</span>", line2)
        line2 = re.sub(r'壓力', r"<span style='color:#00DD00;font-weight:800'>壓力</span>", line2)
        
        # 「負值」這2個字（文字）→ 綠色
        line2 = re.sub(r'負值', r"<span style='color:#00DD00;font-weight:800'>負值</span>", line2)
        
        # ✅ 買超/賣超的詞本身變色
        # 買超 → 紅色字體
        line2 = re.sub(r'買超', r"<span style='color:#FF4444;font-weight:800'>買超</span>", line2)
        # 賣超 → 較暗的綠色字體
        line2 = re.sub(r'賣超', r"<span style='color:#00CC00;font-weight:800'>賣超</span>", line2)
        
        # ✅ 處理「張」的數字（包含千位數以上）- 使用橙色
        # 匹配：數字(可能有逗號) + 張
        line2 = re.sub(r'(\d{1,3}(?:,\d{3})+|\d+)\s*張', r"<span style='color:#FFA500;font-weight:800'>\1</span> 張", line2)
        
        # ✅ 處理負數：整個負數（符號+數字+單位）都變紅色
        # 重要策略：先處理負數（紅色），再處理正數（藍色），避免被覆蓋
        
        # 1. 處理負數百分比：-XX.XX% 或 -XX%（包含毛利率、年增率等）
        # 1a. 有前綴詞的負數百分比
        line2 = re.sub(r'([為率至到])\s*(-\d+(?:\.\d+)?%)', r'\1 <span style="color:#FF4444;font-weight:800">\2</span>', line2)
        # 1b. 括號內的負數百分比（如「年增率-41.70%」）
        line2 = re.sub(r'(年增率|月增率|成長率)\s*(-\d+(?:\.\d+)?%)', r'\1<span style="color:#FF4444;font-weight:800">\2</span>', line2)
        # 1c. 其他位置的負數百分比
        line2 = re.sub(r'([\s(=]|^)(-\d+(?:\.\d+)?%)', r'\1<span style="color:#FF4444;font-weight:800">\2</span>', line2)
        
        # 2. 處理負數營收：-XX,XXX,XXX千元（完整格式，包含符號）
        # 2a. 「營收為-XXX千元」格式
        line2 = re.sub(r'(營收[為達])\s*(-\d{1,3}(?:,\d{3})*)\s*千元', r'\1<span style="color:#FF4444;font-weight:800">\2千元</span>', line2)
        # 2b. 其他「為/至/降到-XXX千元」格式
        line2 = re.sub(r'([為至降到])\s*(-\d{1,3}(?:,\d{3})*)\s*千元', r'\1 <span style="color:#FF4444;font-weight:800">\2 千元</span>', line2)
        # 2c. 「為-XXX元」格式
        line2 = re.sub(r'([為至降到])\s*(-\d{1,3}(?:,\d{3})*)\s*元', r'\1 <span style="color:#FF4444;font-weight:800">\2 元</span>', line2)
        
        # 3. 處理負數 + 億
        line2 = re.sub(r'([為至降到])\s*(-\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*億', r'\1 <span style="color:#FF4444;font-weight:800">\2 億</span>', line2)
        
        # 4. 處理負數 + 張（但要避免已經被處理過的）
        line2 = re.sub(r'([為至到])\s*(-\d{1,3}(?:,\d{3})*)\s*張(?!</span>)', r'\1 <span style="color:#FF4444;font-weight:800">\2 張</span>', line2)
        
        # 5. 處理帶逗號的負數（如「約-1,750」）
        line2 = re.sub(r'約\s*(-\d{1,3}(?:,\d{3})+)', r'約 <span style="color:#FF4444;font-weight:800">\1</span>', line2)
        
        # 6) ✅ 關鍵數字（% / 元 / 億 / 千元）- 正數用藍色
        # 重要：必須在負數處理之後，避免覆蓋負數的紅色
        
        # 6a. 正數營收：「營收為XXX千元」或「營收達XXX千元」
        line2 = re.sub(r'(營收[為達])\s*(\d{1,3}(?:,\d{3})+)\s*千元(?!</span>)', r'\1<span style="color:#9CDCFE;font-weight:800">\2千元</span>', line2)
        
        # 6b. 正數年增率/月增率：「年增率XX.XX%」
        line2 = re.sub(r'(年增率|月增率|成長率)\s*(\d+(?:\.\d+)?)%(?!</span>)', r'\1<span style="color:#9CDCFE;font-weight:800">\2%</span>', line2)
        
        # 6c. 正數百分比（完整數字）- 避免重複處理
        line2 = re.sub(r'([為率])\s*(\d+(?:\.\d+)?)%(?!</span>)', r'\1 <span style="color:#9CDCFE;font-weight:800">\2%</span>', line2)
        line2 = re.sub(r'(?<![-\d>為率])(\d+(?:\.\d+)?)%(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1%</span>", line2)
        
        # 6d. 正數千元（完整數字，包含逗號）
        line2 = re.sub(r'([為至降到])\s*(\d{1,3}(?:,\d{3})+)\s*千元(?!</span>)', r'\1 <span style="color:#9CDCFE;font-weight:800">\2 千元</span>', line2)
        line2 = re.sub(r'(?<![-\d>為至降到])(\d{1,3}(?:,\d{3})+)\s*千元(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1 千元</span>", line2)
        
        # 6e. 正數元（完整數字，包含逗號）
        line2 = re.sub(r'([為至降到])\s*(\d{1,3}(?:,\d{3})+)\s*元(?!</span>)', r'\1 <span style="color:#9CDCFE;font-weight:800">\2 元</span>', line2)
        line2 = re.sub(r'([為至降到])\s*(\d+(?:\.\d+)?)\s*元(?!</span>)', r'\1 <span style="color:#9CDCFE;font-weight:800">\2 元</span>', line2)
        line2 = re.sub(r'(?<![-\d>為至降到])(\d{1,3}(?:,\d{3})+)\s*元(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1 元</span>", line2)
        line2 = re.sub(r'(?<![-\d>為至降到])(\d+(?:\.\d+)?)\s*元(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1 元</span>", line2)
        
        # 正數億（完整數字，包含逗號）
        line2 = re.sub(r'([為至降到])\s*(\d{1,3}(?:,\d{3})+)\s*億(?!</span>)', r'\1 <span style="color:#9CDCFE;font-weight:800">\2 億</span>', line2)
        line2 = re.sub(r'(?<![-\d>為至降到])(\d{1,3}(?:,\d{3})+)\s*億(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1 億</span>", line2)
        line2 = re.sub(r'(?<![-\d>為至降到])(\d+(?:\.\d+)?)\s*億(?!</span>)', r"<span style='color:#9CDCFE;font-weight:800'>\1 億</span>", line2)


        out_lines.append(line2)

    return '\n'.join(out_lines)

st.set_page_config(
    page_title="台股AI戰情室", 
    layout="wide", 
    page_icon="📈",
    initial_sidebar_state="expanded" 
)

# 自定義CSS
st.markdown("""
<style>
.ai-report{font-size:26px;line-height:2.0;}
.ai-report code{font-size:0.95em;}

    /* 側邊欄Logo樣式 */
    .sidebar-logo {
        text-align: center;
        padding: 15px 0;
        margin-bottom: 15px;
        border-bottom: 2px solid #444;
    }
    .sidebar-logo img {
        width: 150px;
        height: auto;
        border-radius: 10px;
    }
    
    /* 側邊欄底部警語容器 */
    [data-testid="stSidebar"] > div:first-child {
        padding-bottom: 100px;
    }
    
    .sidebar-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 270px;  /* 縮小到270px，確保不超出側邊欄 */
        background: linear-gradient(to top, rgba(14, 17, 23, 1) 80%, rgba(14, 17, 23, 0));
        padding: 12px 10px;  /* 進一步縮小padding */
        border-top: 2px solid #ff4444;
        z-index: 999;
    }
    
    .sidebar-footer a {
        color: #ff6b6b;
        text-decoration: none;
        font-weight: bold;
        font-size: 11px;  /* 縮小到11px */
        display: block;
        margin-bottom: 6px;  /* 縮小間距 */
        transition: color 0.2s;
    }
    
    .sidebar-footer a:hover {
        color: #ff9999;
        text-decoration: underline;
    }
    
    .sidebar-warning {
        color: #ffd700;
        font-size: 8.5px;  /* 縮小到8.5px */
        line-height: 1.3;  /* 縮小行高 */
        margin: 0;
        padding: 10px 12px;  /* 縮小padding */
        background: rgba(255, 215, 0, 0.15);
        border-radius: 6px;
        border-left: 4px solid #ff4444;
    }
    
    /* AI警語樣式 */
    .ai-disclaimer {
        color: #ffd700;
        font-size: 12px;
        margin-left: 10px;
        font-weight: normal;
    }
</style>
""", unsafe_allow_html=True)

# ========== Logo 放在最上方（sidebar 開始之前）==========
logo_path = Path(__file__).parent / "YT.png"
if logo_path.exists():
    with open(logo_path, "rb") as f:
        logo_base64 = base64.b64encode(f.read()).decode()
    st.sidebar.markdown(f"""
    <div class="sidebar-logo">
        <img src="data:image/png;base64,{logo_base64}" alt="宏爺講股">
    </div>
    """, unsafe_allow_html=True)

st.sidebar.title("🚀 控制中心")

with st.sidebar.expander("🔑 AI 設定", expanded=True):
    api_key = st.text_input("Gemini API Key", type="password")

with st.sidebar.expander("📊 查詢參數", expanded=True):
    stock_id = st.text_input("股票代碼", value="2330", help="例如：2330, 2317")
    days = st.slider("分析天數", min_value=60, max_value=400, value=250, step=10)
    
    # K線類型（預設還原K線）
    st.markdown("**K線類型(預設還原)**")
    use_normal = st.checkbox("使用一般K線（未還原）", value=False, 
                             help="勾選此項將顯示實際交易價格（有除權息跳空）\n不勾選則使用還原K線（消除除權息影響）")
    use_adjusted = not use_normal  # 反轉邏輯
    
    st.markdown("**均線顯示**")
    show_ma_dict = {
        'MA5': st.checkbox("5日線", value=False),
        'MA20': st.checkbox("20日線 (月線)", value=True),
        'MA60': st.checkbox("60日線 (季線)", value=False),
        'MA100': st.checkbox("100日線", value=True),
        'MA120': st.checkbox("120日線 (半年線)", value=False),
        'MA240': st.checkbox("240日線 (年線)", value=False),
    }

run_analysis = st.sidebar.button("🔍 開始分析", type="primary", use_container_width=True)

if run_analysis and stock_id:
    loader = StockDataLoader()
    
    k_type = "一般K線(未還原)" if use_normal else "還原K線"
    with st.spinner(f"🔄 正在載入 {stock_id} 數據 ({k_type})..."):
        df, error, stock_name = loader.get_combined_data(stock_id, days, use_adjusted)
    
    if error:
        st.error(error)
        st.stop()
    
    # 趨勢判斷
    latest = df.iloc[-1]
    trend_status = "盤整/不明"
    if 'MA20' in df.columns and 'MA100' in df.columns:
        price = latest['close']
        ma20 = latest['MA20']
        ma100 = latest['MA100']
        if price > ma20 and price > ma100: trend_status = "📈 多頭格局"
        elif price < ma20 and price < ma100: trend_status = "📉 空頭格局"
        elif price > ma100 and price < ma20: trend_status = "📊 多箱整理"
        elif price < ma100 and price > ma20: trend_status = "📊 空箱整理"

    st.title(f"📊 {stock_id} {stock_name} 趨勢戰情室 | {trend_status}")
    
    # 顯示 K 線類型
    k_type_display = "一般K線(未還原)" if use_normal else "還原K線"
    k_type_color = "#FFA500" if use_normal else "#00DD00"
    st.markdown(
        f"<div style='background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px; "
        f"border-left: 4px solid {k_type_color}; margin-bottom: 20px;'>"
        f"<b style='color: {k_type_color};'>📈 {k_type_display}</b></div>",
        unsafe_allow_html=True
    )
    
    st.info(_quick_summary_line(df, f"{stock_id} {stock_name}"))
    
    # 圖表
    with st.spinner("繪製圖表中..."):
        fig = plot_combined_chart(df, stock_id, stock_name, show_ma_dict)
        st.plotly_chart(
            fig, 
            use_container_width=True, 
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'{stock_id}_{stock_name}_chart',
                    'height': 1300,
                    'width': 1800,
                    'scale': 2
                }
            },
            key=f'chart_{stock_id}'  # keep chart component stable so zoom won't reset
        )
    
    # ========== 月營收與年增率圖表 ==========
    st.markdown("---")
    st.subheader("📊 月營收與年增率分析")
    
    with st.spinner("載入月營收數據..."):
        df_revenue, rev_error = loader.get_monthly_revenue(stock_id)
    
    if rev_error:
        st.warning(f"⚠️ {rev_error}")
    elif df_revenue is not None and not df_revenue.empty:
        # 顯示最新月營收摘要
        latest_rev = df_revenue.iloc[-1]
        if pd.notna(latest_rev['營收']) and pd.notna(latest_rev['年增率']):
            yoy_icon = "📈" if latest_rev['年增率'] >= 0 else "📉"
            yoy_color = "red" if latest_rev['年增率'] >= 0 else "green"
            st.markdown(
                f"{yoy_icon} 最新月營收：**{int(latest_rev['年'])}年{int(latest_rev['月'])}月** | "
                f"營收 **{latest_rev['營收']/100000000:.2f}** 億元 | "
                f"年增率 <span style='color:{yoy_color}'>**{latest_rev['年增率']:+.2f}%**</span>",
                unsafe_allow_html=True
            )
        
        # 繪製月營收圖表
        fig_revenue = plot_revenue_chart(df_revenue, stock_id, stock_name)
        st.plotly_chart(
            fig_revenue,
            use_container_width=True,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'{stock_id}_{stock_name}_revenue',
                    'height': 700,
                    'width': 1400,
                    'scale': 2
                }
            },
            key=f'revenue_{stock_id}'
        )
    
    # ========== 季營收與季毛利率圖表 ==========
    st.markdown("---")
    
    with st.spinner("載入季度財務數據..."):
        df_quarterly, qtr_error = loader.get_quarterly_data(stock_id)
    
    if qtr_error:
        st.warning(f"⚠️ {qtr_error}")
    elif df_quarterly is not None and not df_quarterly.empty:
        # 金融股：不顯示毛利率（改由提示文字說明可能有小誤差）
        is_finance = bool(df_quarterly.get('是否金融股', False).iloc[-1]) if '是否金融股' in df_quarterly.columns else False
        gp_available = ('毛利率' in df_quarterly.columns) and df_quarterly['毛利率'].notna().any()
        if is_finance and (not gp_available):
            st.subheader("📊 季營收分析")
            st.caption("＊金融股：季營收由月營收加總，數據可能小誤差值")
        else:
            st.subheader("📊 季營收與季毛利率分析")

        # 顯示最新季度摘要
        latest_qtr = df_quarterly.iloc[-1]
        # 顯示最新季度摘要：一般公司顯示毛利率；金融股只顯示營收
        if pd.notna(latest_qtr['營收']):
            if ('毛利率' in df_quarterly.columns) and pd.notna(latest_qtr.get('毛利率')):
                st.markdown(
                    f"💼 最新季度：**{latest_qtr['年度']}Q{latest_qtr['季度']}** | "
                    f"營收 **{latest_qtr['營收']/100000000:.2f}** 億元 | "
                    f"{latest_qtr.get('毛利率名稱','毛利率')} **{latest_qtr['毛利率']:.2f}%**",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"💼 最新季度：**{latest_qtr['年度']}Q{latest_qtr['季度']}** | "
                    f"營收 **{latest_qtr['營收']/100000000:.2f}** 億元",
                    unsafe_allow_html=True
                )
        
        # 繪製季度圖表
        fig_quarterly = plot_quarterly_chart(df_quarterly, stock_id, stock_name)
        st.plotly_chart(
            fig_quarterly,
            use_container_width=True,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'{stock_id}_{stock_name}_quarterly',
                    'height': 600,
                    'width': 1400,
                    'scale': 2
                }
            },
            key=f'quarterly_{stock_id}'
        )
    
    # AI 分析
    st.markdown("---")
    st.markdown("""
    <h2 style='display: inline-block;'>🤖 AI 戰情官・深度解盤</h2>
    <span class='ai-disclaimer'>僅供學術研究使用，非投資建議，AI可能出錯，投資有風險，盈虧自負</span>
    """, unsafe_allow_html=True)
    
    if api_key:
        with st.spinner("🧠 AI 深度分析中（運籌帷幄 約 3~4 分鐘）..."):
            # 把月營收/季營收與毛利率摘要塞給AI，讓第四章「財務體質」一定能引用數字
            fundamental_summary = ""
            
            # === 月營收數據 ===
            try:
                df_rev, rev_error = loader.get_monthly_revenue(stock_id)
                if df_rev is not None and not df_rev.empty:
                    rev_tail = df_rev.tail(12).copy()  # 取最近12個月
                    
                    # 處理欄位名稱
                    col_date = '日期' if '日期' in rev_tail.columns else ('date' if 'date' in rev_tail.columns else None)
                    col_rev  = '營收' if '營收' in rev_tail.columns else ('revenue' if 'revenue' in rev_tail.columns else None)
                    col_yoy  = '年增率' if '年增率' in rev_tail.columns else ('yoy' if 'yoy' in rev_tail.columns else None)
                    
                    if col_date and col_rev:
                        # 轉換營收為千元單位
                        rev_tail[col_rev] = (rev_tail[col_rev] / 1000).round(0).astype(int)
                        
                        # 格式化年增率為2位小數
                        if col_yoy:
                            rev_tail[col_yoy] = rev_tail[col_yoy].round(2)
                        
                        # 準備顯示欄位
                        display_cols = [col_date, col_rev]
                        if col_yoy:
                            display_cols.append(col_yoy)
                        
                        fundamental_summary += "【月營收數據（近12個月）】\n"
                        fundamental_summary += "註：營收單位為千元，年增率單位為%\n"
                        fundamental_summary += rev_tail[display_cols].to_string(index=False)
                        fundamental_summary += "\n\n"
            except Exception as e:
                print(f"[WARNING] 月營收數據獲取失敗: {e}")
            
            # === 季營收與毛利率數據 ===
            try:
                df_q, qtr_error = loader.get_quarterly_data(stock_id)
                if df_q is not None and not df_q.empty:
                    q_tail = df_q.tail(8).copy()  # 取最近8季
                    
                    # 轉換營收為千元單位
                    if '營收' in q_tail.columns:
                        q_tail['營收'] = (q_tail['營收'] / 1000).round(0).astype(int)
                    
                    # 格式化毛利率為2位小數
                    if '毛利率' in q_tail.columns:
                        q_tail['毛利率'] = q_tail['毛利率'].round(2)
                    
                    # 準備顯示欄位
                    cols = [c for c in ['季度標籤', '營收', '毛利率'] if c in q_tail.columns]
                    
                    if cols and len(cols) >= 2:  # 至少要有季度標籤和營收
                        fundamental_summary += "【季營收與毛利率數據（近8季）】\n"
                        fundamental_summary += "註：營收單位為千元，毛利率單位為%\n"
                        fundamental_summary += q_tail[cols].to_string(index=False)
                        fundamental_summary += "\n"
            except Exception as e:
                print(f"[WARNING] 季營收數據獲取失敗: {e}")
            
            # 檢查是否有數據
            if not fundamental_summary.strip():
                fundamental_summary = "（暫無月營收/季營收數據可供分析）"
            else:
                print(f"[INFO] 成功準備財務數據，長度: {len(fundamental_summary)} 字元")

            ai_report = analyze_stock_trend(api_key, stock_id, stock_name, df, fundamental_summary=fundamental_summary)
            ai_report = _highlight_ai_report(ai_report)
            st.markdown(f"<div class='ai-report'>{ai_report}</div>", unsafe_allow_html=True)
    else:
        st.warning("請輸入 API Key 以啟用 AI 分析")

else:
    # ========== 起始畫面：醒目免責聲明（不阻擋操作）==========
    st.markdown("""
    <div style='display: flex; justify-content: center; align-items: center; min-height: 60vh;'>
        <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                    padding: 40px 50px; border-radius: 15px; max-width: 700px; width: 90%;
                    border: 3px solid #ff4444; box-shadow: 0 0 30px rgba(255,68,68,0.4);'>
            <h1 style='color: #ff4444; text-align: center; font-size: 28px; 
                       margin-bottom: 25px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);'>
                ⚠️ 免責聲明 ⚠️
            </h1>
            <div style='color: #ffffff; font-size: 17px; line-height: 1.9; 
                        background: rgba(255,68,68,0.1); padding: 25px; 
                        border-radius: 10px; border-left: 5px solid #ff4444;'>
                <p style='margin: 0 0 15px 0;'>
                    📌 <strong>本報告所載之內容、數據、分析及意見，僅供教育及學術研究用途</strong>，不代表任何形式之投資建議、邀約或操作指引。
                </p>
                <p style='margin: 0 0 15px 0;'>
                    🤖 <strong>AI報告係依據歷史數據與技術指標進行解讀，AI內容可能出錯</strong>，使用者應自行判斷並查證。
                </p>
                <p style='margin: 0; color: #ffd700; font-size: 19px; font-weight: bold;'>
                    💰 <strong>投資有風險，請自行評估並自負盈虧</strong>
                </p>
            </div>
            <div style='text-align: center; margin-top: 25px; color: #9CDCFE; font-size: 16px;'>
                👈 請在左側輸入股票代碼與 API Key 後開始分析
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========== 側邊欄底部：YouTube連結和警語 ==========
st.sidebar.markdown("""
<div class="sidebar-footer">
    <a href="https://www.youtube.com/@宏爺講股" target="_blank">📺 宏爺講股 YouTube頻道</a>
    <p class="sidebar-warning">⚠️ 僅為教育學術研究使用<br>非投資與買賣建議<br>投資有風險，盈虧自負</p>
</div>
""", unsafe_allow_html=True)
