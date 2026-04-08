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
        if pd.isna(v): return "0"
        val = float(str(v).replace(',', ''))
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

def log_uploaded_filename(fn, category="SR"):
    p = "upload_log.txt"
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 2. 페이지 설정 및 디자인 (연한 남색 & 회색) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    .test-box {
        padding: 20px;
        background-color: #ebedef;
        border-left: 5px solid #2c3e50;
        border-radius: 5px;
        margin-bottom: 20px;
        color: #2c3e50;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab_ceva, tab2, tab3 = st.tabs(["SR 정리", "CEVA(LEH)", "TEST중", "업로드 기록"])

# --- TAB 1: SR 정리 (생략) ---
with tab1:
    st.info("기존 SR 정리 기능을 사용하세요.")

# --- TAB 2: CEVA(LEH) (데이터 구조 전면 수정) ---
with tab_ceva:
    st.markdown('<div class="test-box">🛠️ (CEVA 전용) 엑셀의 Goods details를 기반으로 양식을 생성합니다.</div>', unsafe_allow_html=True)
    
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False

    if not st.session_state.ceva_authenticated:
        col_pw1, _ = st.columns([1, 2.5])
        with col_pw1:
            pw = st.text_input("CEVA Passcode", type="password", key="ceva_pw")
            if st.button("인증하기", key="ceva_btn"):
                if pw == "1234":
                    st.session_state.ceva_authenticated = True
                    st.rerun()
                else: st.error("Access Denied")
    else:
        col_cv1, col_cv2 = st.columns(2)
        with col_cv1:
            st.markdown("**1. CEVA SR 엑셀 입력**")
            ceva_file = st.file_uploader("SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        
        if ceva_file:
            try:
                log_uploaded_filename(ceva_file.name, "CEVA")
                # 엑셀 시트 전체를 읽어 데이터 시작점(Goods details 아래) 찾기
                df_raw = pd.read_excel(ceva_file, header=None)
                
                # 'Shipping Instruction'이나 데이터가 시작되는 핵심 키워드 위치 추적
                # 제공된 엑셀 구조상 17행(인덱스 16)부터 실제 데이터가 시작됨
                data_start_idx = 16 
                df_data = pd.read_excel(ceva_file, skiprows=data_start_idx)
                
                # 컬럼 인덱스로 접근 (이름이 없어도 순서대로 긁음)
                # B열: 품목/디스크립션, F열: 포장갯수, G열: 단위, H열: 중량, I열: CBM
                mark_list = []
                desc_list = []

                for _, row in df_data.iterrows():
                    # 빈 행 건너뛰기
                    if pd.isna(row.iloc[1]): continue 
                    
                    description = str(row.iloc[1]).strip() # B열
                    pkg = str(int(row.iloc[5])) if pd.notna(row.iloc[5]) else "0" # F열
                    unit = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else "PKG" # G열
                    wgt = format_number(row.iloc[7]) # H열
                    cbm = format_number(row.iloc[8]) # I열
                    
                    # 마크 생성 (디스크립션 첫 줄 활용)
                    mark_list.extend([description, ""])
                    
                    # 디스크립션 생성 (사용자 요청 양식)
                    desc_list.extend([
                        description,
                        "",
                        "BK#", # 수동 입력용 빈 칸 유지
                        f"{pkg} {unit} / {wgt} KGS / {cbm} CBM",
                        "HC:",
                        "--------------------------",
                        ""
                    ])

                with col_cv2:
                    st.markdown("**2. 시스템 입력용 데이터 (복사하세요)**")
                    st.text_area("MARK 란", "\n".join(mark_list), height=200)
                    st.text_area("DESCRIPTION 란", "\n".join(desc_list), height=400)
                    
            except Exception as e:
                st.error(f"CEVA 데이터 추출 중 오류: {e}")

# --- TAB 3: TEST중 & TAB 4: 업로드 기록 (기존 유지) ---
with tab2:
    st.info("기존 MBL 검수 테스트 영역입니다.")
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
