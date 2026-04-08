import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta, timezone

# PDF 라이브러리 체크
try:
    import pdfplumber
except ImportError:
    pass

# --- 1. 유틸리티 함수 (사용자 원본 유지) ---
def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG', 'PL':'PLT', 'CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    if u_str in ['PK', 'PL', 'CT'] and count > 1: return base + 'S'
    return base

def format_number(v):
    try:
        val = float(v)
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

def log_uploaded_filename(fn, category="SR"):
    p = "upload_log.txt"
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# --- 2. 페이지 설정 및 디자인 (사용자 지정 폰트 복구) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    /* 파일 업로드 박스 (연한 남색 테두리 / 연한 회색 배경) */
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    /* 결과창 메모장 폰트 (사용자 요청 스타일 복구) */
    .stTextArea textarea {
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        color: #2c3e50 !important;
    }
    h3 { font-size: 1.1rem !important; color: #2c3e50; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

# 탭 배치: 사용자 원본 탭들 사이에 CEVA 추가
tab1, tab_ceva, tab2 = st.tabs(["SR 정정", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1: SR 정정 (사용자 제공 코드 로직 100% 동일) ---
with tab1:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
        mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)
    with col_up2:
        item_file = st.file_uploader("2. 하우스리스트 -> S/R NO 검색 -> 엑셀내려받기 파일 입력(품목명, HS CODE 입력 가능)_선택사항", type=["xlsx"], key="item_sub")

    st.divider()

    if sr_file:
        col_res = st.columns([1, 2.5])[1]
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            item_dict = {}; empty_line_bls = [] 
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                # 다중 품목 의심 체크 로직
                if "House B/L No" in item_df.columns and "품목" in item_df.columns:
                    # 동일 HBL에 품목명이 여러 개인 경우 체크
                    hbl_counts = item_df.groupby('House B/L No')['품목'].nunique()
                    empty_line_bls = hbl_counts[hbl_counts > 1].index.tolist()

                    for _, row in item_df.iterrows():
                        h_no = str(row["House B/L No"]).strip()
                        desc_val = str(row["품목"]).strip() if pd.notna(row["품목"]) else ""
                        hs_val = str(row.get("HS CODE", "")).strip() if pd.notna(row.get("HS CODE", "")) else ""
                        if h_no and h_no != "nan":
                            item_dict[h_no] = {"desc": desc_val, "hs": hs_val}

            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy().dropna(subset=['House B/L No'])
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')
            
            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(포장갯수=('포장갯수','sum'), Weight=('Weight','sum'), Measure=('Measure','sum')).reset_index()
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            
            lines = []
            num_containers = len(total)
            
            if num_containers > 1:
                g_p = int(total['포장갯수'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10)]) 
            
            for _, r in total.iterrows():
                lines.append(""); lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
            
            lines.extend(["", "", "<MARK>", ""]) 
            for i, r in marks.iterrows():
                if i > 0: lines.append("") 
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if num_containers <= 4 and mark_spacing:
                        lines.append("") 
                if not (num_containers <= 4 and mark_spacing):
                    lines.append("") 
            
            lines.extend(["", "<DESCRIPTION>", ""]) 
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""]) 
                    lines.extend([f"{cur[0]} / {cur[1]}", ""])
                    prev = cur
                h_no_raw = str(r['House B/L No']).strip()
                lines.append(h_no_raw)
                lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                if h_no_raw in item_dict:
                    info = item_dict[h_no_raw]
                    if info["desc"] and info["desc"].lower() != "nan": lines.append(info["desc"])
                    if info["hs"] and info["hs"].lower() != "nan": lines.append(info["hs"])
                lines.append("")
            
            result = "\n".join(lines)
            with col_res:
                st.subheader("정리 결과")
                if empty_line_bls: 
                    st.warning(f"📢 **다중 품목 의심 B/L:** {', '.join(list(set(empty_line_bls)))} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# --- TAB 2: CEVA(LEH) (요청하신 좌우 2열 배치) ---
with tab_ceva:
    if "ceva_auth" not in st.session_state: st.session_state.ceva_auth = False
    if not st.session_state.ceva_auth:
        cpw = st.text_input("CEVA Passcode", type="password")
        if st.button("인증"):
            if cpw == "1234": st.session_state.ceva_auth = True; st.rerun()
            else: st.error("Access Denied")
    else:
        cf = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        if cf:
            try:
                log_uploaded_filename(cf.name, "CEVA")
                cdf = pd.read_excel(cf, header=None)
                m_list, d_list = [], []
                # I열 기준 자동 확장 탐색 (좌표 규칙 적용)
                for r in range(35, len(cdf)):
                    if pd.notna(cdf.iloc[r, 8]) and isinstance(cdf.iloc[r, 8], (int, float)):
                        p = format_number(cdf.iloc[r, 8]) # 수량(I)
                        w = format_number(cdf.iloc[r+1, 8]) # 중량(I+1)
                        h = str(cdf.iloc[r+3, 4]).replace("HC:", "").replace("HS:", "").strip() if pd.notna(cdf.iloc[r+3, 4]) else ""
                        m = str(cdf.iloc[r+1, 16]).strip() if pd.notna(cdf.iloc[r+1, 16]) else ""
                        d = str(cdf.iloc[r+1, 34]).strip() if pd.notna(cdf.iloc[r+1, 34]) else ""
                        
                        if p != "":
                            m_list.append(f"{m}\n\n\n\n")
                            # BK# 중복 제거 및 네 줄 띄우기 적용
                            d_list.append(f"{d}\n\nBK# {m if 'LEH' in m else ''}\n{p} PKGS / {w} KGS /  CBM\nHC: {h}\n\n\n\n")
                
                cl, cr = st.columns(2)
                with cl:
                    st.subheader("MARK")
                    st.text_area("CEVA_M", "".join(m_list), height=650, label_visibility="collapsed")
                with cr:
                    st.subheader("DESCRIPTION")
                    st.text_area("CEVA_D", "".join(d_list), height=650, label_visibility="collapsed")
            except Exception as e: st.error(f"CEVA 오류: {e}")

# --- TAB 3: 업로드 기록 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: 
            st.text_area("Log History", f.read(), height=500)
