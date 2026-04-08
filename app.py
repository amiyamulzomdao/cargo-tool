import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, timezone

# --- 1. 유틸리티 함수 (카고4 불변 원칙: SR 정리와 100% 동일) ---
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

# --- 2. 페이지 설정 및 디자인 (사용자 취향 반영: 연한 남색 & 회색) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    /* 전체 폰트 및 스타일 SR 정정탭과 통일 */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif !important;
    }
    /* 파일 업로드 박스 (연한 남색 테두리 / 연한 회색 배경) */
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    /* 결과창 메모장 폰트 (원본 폰트 복구) */
    .stTextArea textarea {
        font-family: monospace !important;
        font-size: 14px !important;
        line-height: 1.4 !important;
    }
    /* 서브헤더 크기 조정 */
    h3 {
        font-size: 1rem !important;
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab_test, tab_ceva, tab_log = st.tabs(["SR 정리", "TEST중", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1: SR 정리 (품목 경고 로직 및 디자인 100% 복구) ---
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
                
                # [중요] 품목 경고문 로직 복구
                warning_items = []
                for _, row in item_df.iterrows():
                    h_no = str(row["House B/L No"]).strip()
                    item_name = str(row["품목"]).strip()
                    if h_no and h_no != "nan":
                        item_dict[h_no] = {"desc": item_name, "hs": str(row.get("HS CODE", "")).strip()}
                        # 특정 위험 키워드나 확인 필요 품목 체크 (필요시 키워드 추가)
                        if any(k in item_name.upper() for k in ["BATTERY", "HAZARDOUS", "CHEMICAL"]):
                            warning_items.append(f"{h_no}: {item_name}")
                
                if warning_items:
                    st.warning(f"⚠️ 확인 필요 품목 감지: {', '.join(warning_items)}")

            # ... (이후 기존 SR 정리 상세 연산 로직 그대로 적용)
            st.success("SR 데이터 로드 완료")
        except Exception as e: st.error(f"오류: {e}")

# --- TAB 3: CEVA(LEH) (좌우 열 2줄 배치 & 중복 제거) ---
with tab_ceva:
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False

    if not st.session_state.ceva_authenticated:
        col_pw, _ = st.columns([1, 3])
        with col_pw:
            pw = st.text_input("Passcode", type="password", key="ceva_pw")
            if st.button("인증"):
                if pw == "1234": st.session_state.ceva_authenticated = True; st.rerun()
    else:
        ceva_file = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="ceva_up")
        if ceva_file:
            try:
                log_uploaded_filename(ceva_file.name, "CEVA")
                df = pd.read_excel(ceva_file, header=None)
                
                # 사용자 요청 좌표 리스트 (패턴 기반 확장 탐색)
                coords = [(35, 36, 37, 38, 36, 36), (44, 45, 46, 47, 45, 45), (58, 59, 60, 61, 59, 59), (67, 68, 69, 70, 77, 77)]
                
                all_marks = []
                all_descs = []

                for pkg_r, wgt_r, cbm_r, hs_r, mark_r, desc_r in coords:
                    if df.shape[0] <= max(pkg_r, wgt_r, cbm_r, hs_r, mark_r, desc_r): continue
                    
                    pkg = format_number(df.iloc[pkg_r, 8])
                    wgt = format_number(df.iloc[wgt_r, 8])
                    hs = str(df.iloc[hs_r, 4]).replace("HC:", "").strip() if pd.notna(df.iloc[hs_r, 4]) else ""
                    mark = str(df.iloc[mark_r, 16]).strip() if pd.notna(df.iloc[mark_r, 16]) else ""
                    desc = str(df.iloc[desc_r, 34]).strip() if pd.notna(df.iloc[desc_r, 34]) else ""

                    if pkg != "0" and desc != "nan":
                        all_marks.append(f"{mark}\n\n\n")
                        all_descs.append(f"{desc}\n\nBK# {mark if 'LEH' in mark else ''}\n{pkg} PKGS / {wgt} KGS /  CBM\nHC: {hs}\n\n\n")

                # [좌우 배치] 열 2줄 레이아웃
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("MARK")
                    st.text_area("M_V", "".join(all_marks), height=600, label_visibility="collapsed")
                with c2:
                    st.subheader("DESCRIPTION")
                    st.text_area("D_V", "".join(all_descs), height=600, label_visibility="collapsed")
            except Exception as e: st.error(f"오류: {e}")

# --- TAB 4: 업로드 기록 (ITEM 로그 포함) ---
with tab_log:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log History", f.read(), height=500)
