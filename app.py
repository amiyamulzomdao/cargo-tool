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

# --- 2. 페이지 설정 및 세련된 디자인 (연한 남색 & 회색) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")

st.markdown("""
    <style>
    /* 파일 업로드 박스 전체 디자인 */
    [data-testid="stFileUploadDropzone"] {
        background-color: #f1f4f9 !important; /* 아주 연한 회색/블루 */
        border: 2px dashed #5c7c9c !important; /* 세련된 연한 남색 점선 */
        border-radius: 12px !important;
        padding: 10px !important;
    }
    
    /* 업로드 박스 내부 텍스트 색상 조절 */
    [data-testid="stFileUploadDropzone"] div div span {
        color: #34495e !important;
        font-weight: 500;
    }

    /* TEST중 안내 박스 디자인 */
    .test-box {
        padding: 18px;
        background-color: #f8f9fa;
        border-left: 6px solid #5c7c9c; /* 연한 남색 포인트 */
        border-radius: 4px;
        margin-bottom: 20px;
        color: #2c3e50;
        font-weight: 600;
        font-size: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# 메인 타이틀
st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정리", "TEST중", "업로드 기록"])

# --- TAB 1: SR 정리 ---
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

# --- TAB 2: TEST중 ---
with tab2:
    st.markdown('<div class="test-box">🛠️ (TEST중) 본 기능은 내부 테스트 중입니다.</div>', unsafe_allow_html=True)
    
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        col_pw1, col_pw2 = st.columns([1, 2.5])
        with col_pw1:
            password = st.text_input("Admin Password", type="password", placeholder="비밀번호 입력")
            if st.button("Access"):
                if password == "1234":
                    st.session_state.admin_authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid Password")
    else:
        st.info("🔓 Admin 모드가 활성화되었습니다.")
        if st.button("잠금"):
            st.session_state.admin_authenticated = False
            st.rerun()
            
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**1. SR 엑셀 데이터 입력**")
            m_file = st.file_uploader("정리 전 SR 엑셀 업로드", type=["xlsx"], key="mbl_sr_up")
        with col2:
            st.markdown("**2. 선사 DRAFT BL 업로드**")
            draft_pdf = st.file_uploader("PDF 파일 업로드 (.pdf)", type=["pdf"], key="d_up", label_visibility="collapsed")
            
            if m_file and draft_pdf:
                try:
                    sr_df_check = pd.read_excel(m_file)
                    sr_df_check['Seal#1'] = sr_df_check['Seal#1'].fillna('').astype(str).str.split('.').str[0]
                    with pdfplumber.open(draft_pdf) as pdf:
                        full_text = " ".join([p.extract_text().upper() for p in pdf.pages])
                    
                    errors = []
                    t_pkg = int(sr_df_check['포장갯수'].sum())
                    t_wgt = format_number(sr_df_check['Weight'].sum())
                    t_msr = format_number(sr_df_check['Measure'].sum())
                    
                    if str(t_pkg) not in full_text: errors.append(f"❌ 전체 TOTAL 수량 불일치: {t_pkg} PKGS")
                    if t_wgt not in full_text: errors.append(f"❌ 전체 TOTAL 중량 불일치: {t_wgt} KGS")
                    if t_msr not in full_text: errors.append(f"❌ 전체 TOTAL CBM 불일치: {t_msr} CBM")
                    
                    total_cntr = sr_df_check.groupby(['컨테이너 번호', 'Seal#1']).agg({'포장갯수':'sum', 'Weight':'sum', 'Measure':'sum'}).reset_index()
                    for _, c_row in total_cntr.iterrows():
                        c_no = str(c_row['컨테이너 번호']).strip()
                        c_pkg, c_wgt, c_msr = int(c_row['포장갯수']), format_number(c_row['Weight']), format_number(c_row['Measure'])
                        if c_no not in full_text: errors.append(f"❌ 컨테이너 번호 누락/오류: {c_no}")
                        c_pos = full_text.find(c_no)
                        context = full_text[c_pos:c_pos+1200] if c_pos != -1 else full_text
                        if str(c_pkg) not in context: errors.append(f"❌ TOTAL CNTR 수량 불일치 (CNTR: {c_no}): {c_pkg} PKGS")
                        if c_wgt not in context: errors.append(f"❌ TOTAL CNTR 중량 불일치 (CNTR: {c_no}): {c_wgt} KGS")
                        if c_msr not in context: errors.append(f"❌ TOTAL CNTR CBM 불일치 (CNTR: {c_no}): {c_msr} CBM")

                    for _, h_row in sr_df_check.iterrows():
                        h_no = str(h_row['House B/L No']).strip()
                        h_wgt, h_msr = format_number(h_row['Weight']), format_number(h_row['Measure'])
                        if h_no not in full_text:
                            errors.append(f"❌ B/L 번호 찾을 수 없음: {h_no}")
                            continue
                        h_pos = full_text.find(h_no)
                        h_context = full_text[h_pos:h_pos+600]
                        if h_wgt not in h_context: errors.append(f"❌ 중량 불일치 (HBL: {h_no}): {h_wgt} KGS")
                        if h_msr not in h_context: errors.append(f"❌ CBM 불일치 (HBL: {h_no}): {h_msr} CBM (확인 요망)")

                    st.markdown("---")
                    if not errors: st.success("✅ 모든 데이터가 정확히 일치합니다.")
                    else:
                        st.warning(f"⚠️ 총 {len(errors)}건의 불일치 발견")
                        err_html = "".join([f"<li style='font-size:14px; margin-bottom:2px;'>{e}</li>" for e in errors])
                        st.markdown(f"<ul style='list-style-type:none; padding-left:0;'>{err_html}</ul>", unsafe_allow_html=True)
                except Exception as e: st.error(f"오류 발생: {e}")

# --- TAB 3: 업로드 기록 ---
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
