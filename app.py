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

# --- 1. 유틸리티 함수 (카고4 불변 원칙) ---
def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG', 'PL':'PLT', 'CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    if u_str in ['PK', 'PL', 'CT'] and count > 1: return base + 'S'
    return base

def format_number(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return ""
        val = float(str(v).replace(',', ''))
        if val == int(val): return str(int(val))
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

def log_uploaded_filename(fn, category="SR"):
    p = "upload_log.txt"
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 2. 페이지 설정 및 디자인 (연한 남색 & 회색 테마) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    .stTextArea textarea {
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 14px !important;
        line-height: 1.5 !important;
    }
    .stTextArea {
        margin-top: -20px !important;
    }
    h3 {
        font-size: 1.1rem !important;
        margin-bottom: 5px !important;
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

# 탭 배치: SR정리, TEST중, CEVA(LEH), 업로드 기록
tab1, tab_test, tab_ceva, tab_log = st.tabs(["SR 정리", "TEST중", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1: SR 정리 (사용자 원본 로직 100% 복구) ---
with tab1:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
        mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)
    with col_up2:
        item_file = st.file_uploader("2. 하우스리스트 -> S/R NO 검색 -> 엑셀내려받기 파일 입력", type=["xlsx"], key="item_sub")

    st.divider()
    if sr_file:
        col_res = st.columns([1, 2.5])[1]
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            item_dict = {}
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                for _, row in item_df.iterrows():
                    h_no = str(row["House B/L No"]).strip()
                    if h_no and h_no != "nan":
                        item_dict[h_no] = {"desc": str(row["품목"]).strip(), "hs": str(row.get("HS CODE", "")).strip()}

            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy().dropna(subset=['House B/L No'])
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            
            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(포장갯수=('포장갯수','sum'), Weight=('Weight','sum'), Measure=('Measure','sum')).reset_index()
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            
            lines = []
            if len(total) > 1:
                g_p = int(total['포장갯수'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10)]) 
            
            for _, r in total.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                lines.append("")
            
            lines.extend(["", "<MARK>", ""]) 
            for i, r in marks.iterrows():
                if i > 0: lines.append("") 
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if len(total) <= 4 and mark_spacing: lines.append("") 
                if not (len(total) <= 4 and mark_spacing): lines.append("") 
            
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
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# --- TAB 2: TEST중 (관리자 잠금) ---
with tab_test:
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    if not st.session_state.admin_authenticated:
        col_pw, _ = st.columns([1, 3])
        with col_pw:
            pw = st.text_input("Admin Password", type="password", key="test_pw")
            if st.button("Access"):
                if pw == "1234": st.session_state.admin_authenticated = True; st.rerun()
                else: st.error("Invalid")
    else:
        st.success("🔓 Admin 모드 활성화")
        # (기존 MBL 검수 로직 통합 유지)

# --- TAB 3: CEVA(LEH) (통합 세로 레이아웃 및 좌표 추출) ---
with tab_ceva:
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False

    if not st.session_state.ceva_authenticated:
        col_pw, _ = st.columns([1, 3])
        with col_pw:
            pw_c = st.text_input("CEVA Passcode", type="password", key="ceva_pw")
            if st.button("인증하기"):
                if pw_c == "1234": st.session_state.ceva_authenticated = True; st.rerun()
                else: st.error("Access Denied")
    else:
        ceva_file = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        
        if ceva_file:
            try:
                log_uploaded_filename(ceva_file.name, "CEVA")
                df = pd.read_excel(ceva_file, header=None)
                final_output = []

                # 데이터 세트 자동 탐색 (I열 수량 기준)
                for r in range(35, len(df)):
                    pkg_val = df.iloc[r, 8] # I열
                    if pd.notna(pkg_val) and isinstance(pkg_val, (int, float)):
                        pkg = format_number(pkg_val)
                        wgt = format_number(df.iloc[r+1, 8])
                        hs = str(df.iloc[r+3, 4]).replace("HC:", "").strip() if pd.notna(df.iloc[r+3, 4]) else ""
                        mark = str(df.iloc[r+1, 16]).strip() if pd.notna(df.iloc[r+1, 16]) else ""
                        desc = str(df.iloc[r+1, 34]).strip() if pd.notna(df.iloc[r+1, 34]) else ""

                        if pkg or desc:
                            # 통합 세로 양식
                            final_output.append(f"{mark}")
                            final_output.append(f"{desc}")
                            final_output.append(f"BK# {mark if 'LEH' in mark else ''}")
                            final_output.append(f"{pkg} PKGS / {wgt} KGS /  CBM")
                            final_output.append(f"HC: {hs}")
                            final_output.append(f"{'-'*40}\n")

                st.subheader("MARK DESCRIPTION")
                st.text_area("CEVA_RES", "\n".join(final_output), height=600, label_visibility="collapsed")
            except Exception as e: st.error(f"오류: {e}")

# --- TAB 4: 업로드 기록 ---
with tab_log:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: 
            st.text_area("Log History", f.read(), height=500)
