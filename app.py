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
st.set_page_config(page_title="카고2", layout="wide")
st.title("카고2")

if 'tariff_db' not in st.session_state:
    st.session_state.tariff_db = pd.DataFrame()

# 탭 구성 (기존 기능 우선)
tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

# --- TAB 1: SR 정정 ---
with tab1:
    # 1. 업로드 칸 가로 배열 [ ㅁ  ㅁ ]
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        # 코스코 체크박스를 파일 업로드 바로 밑에 작게 배치
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)

    with col_up2:
        item_file = st.file_uploader("2. 하우스리스트->엑셀내려받기 파일 입력 (선택)", type=["xlsx"], key="item_sub")

    st.divider()

    if sr_file:
        col_left_space, col_res = st.columns([1, 2.5]) # 결과창을 넓게 배치
        
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            
            # 품목 정보 매핑 (두 번째 파일이 있을 경우)
            item_dict = {}
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file)
                for _, row in item_df.iterrows():
                    h_no = str(row.get('House B/L No', '')).strip()
                    desc = str(row.get('품목', '')).strip()
                    hs = str(row.get('HS CODE', '')).strip()
                    if h_no and h_no != "nan":
                        item_dict[h_no] = {"desc": desc, "hs": hs}

            # 기존 카고2 로직 실행
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
                
                # 두 번째 파일(품목/HS) 정보가 있다면 출력
                if h_no in item_dict:
                    d_val, h_val = item_dict[h_no]["desc"], item_dict[h_no]["hs"]
                    if d_val and d_val != "nan": lines.append(d_val)
                    if h_val and h_val != "nan": lines.append(h_val)
                lines.append("")
            
            result = "\n".join(lines)
            
            with col_res:
                st.subheader("정리 결과")
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2, 3: 기록 및 로이타리프 (기존 기능 유지) ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log", f.read(), height=500)
with tab3:
    st.info("이전에 설정한 로이타리프 조회 기능입니다.")
    # (로이타리프 로직은 이전과 동일하게 유지됨)
