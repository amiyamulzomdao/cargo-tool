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
st.set_page_config(page_title="카고2", layout="wide")
st.title("카고2")

tab1, tab2 = st.tabs(["SR 정정", "업로드 기록"])

# --- TAB 1: SR 정정 ---
with tab1:
    col_up1, col_up2 = st.columns(2)
    
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)

    with col_up2:
        item_file = st.file_uploader("2. 하우스리스트->엑셀내려받기 파일 입력 (선택)", type=["xlsx"], key="item_sub")

    st.divider()

    if sr_file:
        col_left_space, col_res = st.columns([1, 2.5])
        
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            
            # --- 품목 정보 매핑 로직 강화 ---
            item_dict = {}
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                # 엑셀을 읽을 때 두 번째 행부터 제목인 경우를 대비해 시도
                item_df = pd.read_excel(item_file)
                
                # 컬럼명에서 'House', '품목', 'HS' 단어가 들어간 열을 자동으로 찾기
                h_col = next((c for c in item_df.columns if 'House' in str(c)), None)
                d_col = next((c for c in item_df.columns if '품목' in str(c)), None)
                s_col = next((c for c in item_df.columns if 'HS CODE' in str(c).upper()), None)

                if h_col and d_col:
                    for _, row in item_df.iterrows():
                        # 하우스 번호에서 공백 제거
                        h_no = str(row[h_col]).strip()
                        desc = str(row[d_col]).strip() if pd.notna(row[d_col]) else ""
                        hs = str(row[s_col]).strip() if s_col and pd.notna(row[s_col]) else ""
                        
                        if h_no and h_no != "nan":
                            item_dict[h_no] = {"desc": desc, "hs": hs}

            # 기본 카고2 로직
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
                
                h_no_raw = str(r['House B/L No']).strip()
                u_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                
                lines.append(h_no_raw)
                lines.append(f"{int(r['포장갯수'])} {u_val} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                
                # 품목 매칭 출력 (딕셔너리에서 검색)
                if h_no_raw in item_dict:
                    info = item_dict[h_no_raw]
                    if info["desc"] and info["desc"].lower() != "nan":
                        lines.append(info["desc"])
                    if info["hs"] and info["hs"].lower() != "nan":
                        lines.append(info["hs"])
                
                lines.append("")
            
            result = "\n".join(lines)
            
            with col_res:
                st.subheader("정리 결과")
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2: 업로드 기록 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log", f.read(), height=500)
