import streamlit as st
import pandas as pd
import os
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

# --- 2. 페이지 설정 및 세련된 커스텀 디자인 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    /* 전체 폰트 통일 */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    /* 파일 업로드 박스 디자인 (연한 남색/회색 커스텀) */
    [data-testid="stFileUploadDropzone"] {
        background-color: #f1f4f9 !important; /* 연한 회색 */
        border: 2px dashed #5c7c9c !important; /* 세련된 연한 남색 */
        border-radius: 12px !important;
    }
    /* 결과창 디자인 및 간격 */
    .stTextArea textarea {
        font-family: monospace !important;
        font-size: 14px !important;
        background-color: #fafafa !important;
    }
    .stTextArea {
        margin-top: -25px !important;
    }
    /* 헤더 스타일링 */
    h3 {
        font-size: 1rem !important;
        margin-bottom: 5px !important;
        color: #34495e;
    }
    /* TEST중 안내 박스 */
    .test-box {
        padding: 15px;
        background-color: #f8f9fa;
        border-left: 5px solid #5c7c9c;
        border-radius: 4px;
        margin-bottom: 20px;
        color: #2c3e50;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab2, tab_ceva, tab3 = st.tabs(["SR 정리", "TEST중", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1 & 2 (기존 로직 유지) ---
with tab1: st.write("SR 정리 영역")
with tab2: st.write("MBL 검수 영역")

# --- TAB 3: CEVA(LEH) (다중 세트 추출 및 세로 배치) ---
with tab_ceva:
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False

    if not st.session_state.ceva_authenticated:
        col_pw, _ = st.columns([1, 3])
        with col_pw:
            pw = st.text_input("CEVA Passcode", type="password", key="ceva_pw")
            if st.button("인증"):
                if pw == "1234":
                    st.session_state.ceva_authenticated = True
                    st.rerun()
                else: st.error("Access Denied")
    else:
        ceva_file = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        
        if ceva_file:
            try:
                log_uploaded_filename(ceva_file.name, "CEVA")
                df = pd.read_excel(ceva_file, header=None)
                
                # 추출할 데이터 세트 좌표 정의 (사용자 제공 패턴 기반)
                # 세트 구성: (PKG_row, WGT_row, CBM_row, HS_row, MARK_row, DESC_row)
                data_sets = [
                    (35, 36, 37, 38, 45, 45), # Set 1: I45, I46, I47 / E39 / Q46 / AI46
                    (58, 59, 60, 61, 59, 59), # Set 2: I59, I60, I61 / E62 / Q60 / AI60
                    (67, 68, 69, 70, 77, 77)  # Set 3: I68, I69, I70 / E71 / Q78 / AI78
                ]
                # 컬럼 인덱스: E=4, I=8, Q=16, AI=34
                
                all_marks = []
                all_descs = []

                for pkg_r, wgt_r, cbm_r, hs_r, mark_r, desc_r in data_sets:
                    if df.shape[0] <= max(pkg_r, wgt_r, cbm_r, hs_r, mark_r, desc_r):
                        continue
                        
                    pkg = format_number(df.iloc[pkg_r, 8])
                    wgt = format_number(df.iloc[wgt_r, 8])
                    hs = str(df.iloc[hs_r, 4]).strip() if pd.notna(df.iloc[hs_r, 4]) else ""
                    mark = str(df.iloc[mark_r, 16]).strip() if pd.notna(df.iloc[mark_r, 16]) else ""
                    desc_name = str(df.iloc[desc_r, 34]).strip() if pd.notna(df.iloc[desc_r, 34]) else ""

                    if not pkg and not desc_name: continue # 데이터 없으면 스킵

                    all_marks.append(f"{mark}\n")
                    all_descs.append(
                        f"{desc_name}\n\n"
                        f"BK# \n"
                        f"{pkg} PKGS / {wgt} KGS /  CBM\n"
                        f"HC: {hs}\n"
                        f"--------------------------\n"
                    )

                # 결과 출력
                st.subheader("MARK")
                st.text_area("MARK_AREA", "\n".join(all_marks), height=150, label_visibility="collapsed")
                
                st.subheader("DESCRIPTION")
                st.text_area("DESC_AREA", "\n".join(all_descs), height=400, label_visibility="collapsed")
                
            except Exception as e:
                st.error(f"오류: {e}")

# --- TAB 4: 업로드 기록 ---
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
