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

def clean_date_final(val):
    if pd.isna(val) or val == "": return ""
    try:
        dt = pd.to_datetime(val)
        return dt.strftime("%d-%b-%Y")
    except: return str(val)

# --- 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("Europe Docs tool")

if 'tariff_db' not in st.session_state:
    st.session_state.tariff_db = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

# --- TAB 1: SR 정정 (가로 배치 레이아웃) ---
with tab1:
    # 화면을 좌(1):우(1.5)로 분할
    col_left, col_right = st.columns([1, 1.5])
    
    with col_left:
        st.write("### 1. 파일 업로드")
        sr_file = st.file_uploader("SR 엑셀 파일을 업로드하세요", type=["xlsx"], key="sr_up_new")
        item_file = st.file_uploader("하우스리스트->엑셀내려받기 파일 입력 (선택)", type=["xlsx"], key="item_up_new")
        
        # 코스코 체크박스를 업로드 칸 밑에 조그맣게 배치
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", help="체크 시 코스코 화물의 PLT 단위를 PKGS로 자동 변경합니다.")
        st.divider()

    if sr_file:
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            
            # 품목 정보 매핑 (두 번째 파일이 있을 경우)
            item_dict = {}
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM_LIST")
                item_df = pd.read_excel(item_file)
                for _, row in item_df.iterrows():
                    h_no = str(row.get('House B/L No', '')).strip()
                    desc = str(row.get('품목', '')).strip()
                    hs = str(row.get('HS CODE', '')).strip()
                    if h_no and h_no != "nan":
                        item_dict[h_no] = {"desc": desc, "hs": hs}

            # 데이터 가공 및 그룹화
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy()
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
                
                # 품목/HS CODE 매칭 출력
                if h_no in item_dict:
                    d_val, h_val = item_dict[h_no]["desc"], item_dict[h_no]["hs"]
                    if d_val and d_val != "nan": lines.append(d_val)
                    if h_val and h_val != "nan": lines.append(h_val)
                lines.append("")
            
            result = "\n".join(lines)
            
            # 오른쪽 컬럼에 결과 출력
            with col_right:
                st.write("### 2. 정리 결과")
                btn_col, _ = st.columns([1, 1.5])
                btn_col.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt", use_container_width=True)
                st.text_area("Result Area", result, height=700, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2: 업로드 기록 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log History", f.read(), height=500)

# --- TAB 3: 로이타리프 ---
with tab3:
    st.subheader("로이타리프 조회")
    # ... (기존 로이타리프 로직 동일 유지) ...
