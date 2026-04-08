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
        if pd.isna(v): return ""
        val = float(str(v).replace(',', ''))
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

# --- 2. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    /* 결과 텍스트 영역 폰트 조정 */
    textarea {
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

# 탭 배치 (1: SR 정리, 2: TEST중, 3: CEVA(LEH), 4: 업로드 기록)
tab1, tab2, tab_ceva, tab3 = st.tabs(["SR 정리", "TEST중", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1 & 2 (기존 로직 유지) ---
with tab1: st.write("SR 정리 영역입니다.")
with tab2: st.write("MBL 검수 영역입니다.")

# --- TAB 3: CEVA(LEH) (세로 배치 및 셀 지정 추출) ---
with tab_ceva:
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False

    if not st.session_state.ceva_authenticated:
        col_pw, _ = st.columns([1, 3])
        with col_pw:
            pw = st.text_input("CEVA Passcode", type="password", key="ceva_pw")
            if st.button("인증하기"):
                if pw == "1234":
                    st.session_state.ceva_authenticated = True
                    st.rerun()
                else: st.error("Access Denied")
    else:
        # 파일 업로드 (가로 전체 사용)
        ceva_file = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        
        if ceva_file:
            try:
                # 엑셀을 Header 없이 읽어와서 좌표로 접근 (0부터 시작하므로 행-1, 열은 알파벳 순서)
                # A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8 ... Q=16 ... AI=34
                df = pd.read_excel(ceva_file, header=None)
                
                # 데이터 추출 (지정된 셀 위치)
                # 수량: I36 (Row 35, Col 8)
                pkg_val = df.iloc[35, 8] if df.shape[0] > 35 else ""
                # 중량: I37 (Row 36, Col 8)
                wgt_val = format_number(df.iloc[36, 8]) if df.shape[0] > 36 else ""
                # CBM: I38 (사용자 요청에 따라 항상 비움)
                cbm_val = "" 
                # HS CODE: E39 (Row 38, Col 4)
                hs_val = str(df.iloc[38, 4]).strip() if df.shape[0] > 38 else ""
                # MARK: Q37 (Row 36, Col 16)
                mark_val = str(df.iloc[36, 16]).strip() if df.shape[0] > 36 else ""
                # DESC: AI37 (Row 36, Col 34)
                desc_name = str(df.iloc[36, 34]).strip() if df.shape[0] > 36 else ""

                # 결과 텍스트 생성
                res_mark = f"{mark_val}\n"
                
                res_desc = (
                    f"{pkg_val} PKGS OF {desc_name}\n\n"
                    f"BK# \n"
                    f"{pkg_val} PKGS / {wgt_val} KGS / {cbm_val} CBM\n"
                    f"HC: {hs_val}\n"
                    f"--------------------------"
                )

                # 세로 형식 배치
                st.divider()
                st.subheader("MARK")
                st.text_area("MARK", res_mark, height=150, label_visibility="collapsed")
                
                st.subheader("DESCRIPTION")
                st.text_area("DESCRIPTION", res_desc, height=300, label_visibility="collapsed")
                
            except Exception as e:
                st.error(f"데이터 추출 오류: {e}. 엑셀 시트 구성이나 셀 위치를 확인해주세요.")

# --- TAB 4: 업로드 기록 ---
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
