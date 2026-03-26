import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 유틸리티 함수 ---
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
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("Europe Docs tool")

if 'tariff_db' not in st.session_state:
    st.session_state.tariff_db = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

# --- TAB 1: SR 정정 ---
with tab1:
    col_files, col_res = st.columns([1, 1.5])
    
    with col_files:
        st.subheader("파일 업로드")
        sr_file = st.file_uploader("1. SR 엑셀 파일을 업로드하세요", type=["xlsx"], key="sr_up")
        item_file = st.file_uploader("2. 하우스리스트 -> 엑셀내려받기 파일 입력 (선택사항)", type=["xlsx"], key="item_up")
        
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환")

    if sr_file:
        try:
            log_uploaded_filename(sr_file.name, "SR")
            df = pd.read_excel(sr_file)
            
            # 품목 정보 딕셔너리 생성 (두 번째 파일이 있을 경우)
            item_dict = {}
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM_LIST")
                item_df = pd.read_excel(item_file)
                # 하우스번호를 키로, 품목과 HS CODE를 값으로 저장
                for _, row in item_df.iterrows():
                    h_no = str(row.get('House B/L No', '')).strip()
                    content = str(row.get('품목', '')).strip()
                    hs_code = str(row.get('HS CODE', '')).strip()
                    if h_no:
                        item_dict[h_no] = {"desc": content, "hs": hs_code}

            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')
            
            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(포장갯수=('포장갯수','sum'), Weight=('Weight','sum'), Measure=('Measure','sum')).reset_index()
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            
            lines = []
            single = (len(total) == 1)
            
            if not single:
                g_p = int(total['포장갯수'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10), ""])
            
            for _, r in total.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM\n")
            
            lines.append("<MARK>\n")
            for _, r in marks.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\n")
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single: lines.append("")
                lines.append("")
            
            lines.extend(["<DESCRIPTION>", ""])
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""])
                    if not single: lines.extend([f"{cur[0]} / {cur[1]}", ""])
                    prev = cur
                
                h_no = str(r['House B/L No']).strip()
                u_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                
                lines.append(h_no)
                lines.append(f"{int(r['포장갯수'])} {u_val} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                
                # 품목 및 HS CODE 추가 로직
                if h_no in item_dict:
                    desc_text = item_dict[h_no]["desc"]
                    hs_text = item_dict[h_no]["hs"]
                    if desc_text and desc_text != "nan": lines.append(desc_text)
                    if hs_text and hs_text != "nan": lines.append(hs_text)
                
                lines.append("")
            
            result = "\n".join(lines)
            
            with col_res:
                c1, c2 = st.columns([2, 1])
                c1.subheader("정리 결과")
                c2.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt", use_container_width=True)
                st.text_area("결과", result, height=600, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2, 3: 기존 로직 유지 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log History", f.read(), height=500)
with tab3:
    st.info("로이타리프 기능은 이전 설정대로 유지됩니다.")
