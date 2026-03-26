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
            
            item_dict = {}
            empty_line_bls = [] # 빈 줄이 포함된 B/L 리스트
            
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                target_h = "House B/L No"
                target_d = "품목"
                target_s = "HS CODE"

                if target_h in item_df.columns and target_d in item_df.columns:
                    for _, row in item_df.iterrows():
                        h_no = str(row[target_h]).strip()
                        desc_raw = str(row[target_d]) if pd.notna(row[target_d]) else ""
                        hs_raw = str(row[target_s]).strip() if target_s in item_df.columns and pd.notna(row[target_s]) else ""
                        
                        if h_no and h_no != "nan":
                            item_dict[h_no] = {"desc": desc_raw, "hs": hs_raw}
                            
                            # [수정된 로직] 단순히 줄바꿈이 아니라, "빈 줄"이 있는지 체크
                            # \n\n 이 있거나, 줄 사이에 공백만 있는 줄이 있는지 확인
                            lines = desc_raw.split('\n')
                            has_empty_line = False
                            if len(lines) > 1:
                                for i in range(len(lines) - 1):
                                    # 현재 줄과 다음 줄 사이에 아무 내용도 없는 줄이 끼어 있는지 확인
                                    if lines[i].strip() == "" and i != 0 and i != len(lines)-1:
                                        has_empty_line = True
                                    # 연속된 줄바꿈(\n\n) 체크
                                    if "\n\n" in desc_raw:
                                        has_empty_line = True
                            
                            if has_empty_line:
                                empty_line_bls.append(h_no)

            # 데이터 가공 로직
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            
            gt_bls = df[df['단위'].fillna('').astype(str).str.upper().str.contains('GT')]['House B/L No'].unique().tolist()
            
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
                
                if h_no_raw in item_dict:
                    info = item_dict[h_no_raw]
                    if info["desc"] and info["desc"].lower() != "nan": lines.append(info["desc"])
                    if info["hs"] and info["hs"].lower() != "nan": lines.append(info["hs"])
                lines.append("")
            
            result = "\n".join(lines)
            
            with col_res:
                st.subheader("정리 결과")
                
                if gt_bls:
                    st.error(f"⚠️ **GT 단위 확인 필요 B/L:** {', '.join(gt_bls)}")
                
                if empty_line_bls:
                    st.warning(f"📢 **품목 내 빈 줄(다중 품목) 의심 B/L:** {', '.join(empty_line_bls)}")
                
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2: 업로드 기록 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log", f.read(), height=500)
