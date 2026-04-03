import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, timezone

# --- 1. 유틸리티 함수 (카고3 불변 원칙) ---
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

# 한국 시간(KST) 고정 및 중복 로그 방지
def log_uploaded_filename(fn, category="SR"):
    log_key = f"logged_{fn}_{category}"
    if log_key not in st.session_state:
        p = "upload_log.txt"
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{now}] ({category}) {fn}\n"
        with open(p, "a", encoding='utf-8') as f:
            f.write(entry)
        st.session_state[log_key] = True

# --- 2. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab2 = st.tabs(["SR 정정", "업로드 기록"])

with tab1:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
        mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)
    with col_up2:
        item_file = st.file_uploader("2. 품목/HS CODE 정보 파일 입력", type=["xlsx"], key="item_sub")

    st.divider()

    if sr_file:
        col_res = st.columns([1, 2.5])[1]
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            
            item_dict = {}; empty_line_bls = [] 
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                # [복구] 모든 시트를 뒤져서 제목 열을 찾는 오리지널 로직 보강
                item_df_raw = pd.read_excel(item_file, header=None)
                
                bl_col_idx, desc_col_idx, hs_col_idx = None, None, None
                # 첫 10줄 내에서 제목 키워드 검색
                for i in range(min(10, len(item_df_raw))):
                    row = [str(x).upper().replace(" ", "") for x in item_df_raw.iloc[i]]
                    for idx, val in enumerate(row):
                        if "HOUSEB/L" in val or "HB/L" in val or "BLNO" in val: bl_col_idx = idx
                        if "품목" in val or "DESCRIPTION" in val or "DESC" in val: desc_col_idx = idx
                        if "HS" in val: hs_col_idx = idx
                    if bl_col_idx is not None and desc_col_idx is not None:
                        start_row = i + 1
                        break
                else: start_row = 0

                if bl_col_idx is not None and desc_col_idx is not None:
                    for r in range(start_row, len(item_df_raw)):
                        # 번호 매칭을 위해 .0 제거 및 공백 제거 처리
                        h_no = str(item_df_raw.iloc[r, bl_col_idx]).strip().replace(".0", "")
                        desc_v = str(item_df_raw.iloc[r, desc_col_idx]).strip()
                        hs_v = str(item_df_raw.iloc[r, hs_col_idx]).strip() if hs_col_idx is not None else ""
                        
                        if h_no and h_no.lower() not in ["nan", "none", ""]:
                            item_dict[h_no] = {
                                "desc": desc_v if desc_v.lower() != "nan" else "",
                                "hs": hs_v if hs_v.lower() != "nan" else ""
                            }
                            if "\n\n" in desc_v: empty_line_bls.append(h_no)

            # --- SR 데이터 처리 로직 (카고3 불변 규칙) ---
            target_cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[target_cols].copy().dropna(subset=['House B/L No'])
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')
            
            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(포장갯수=('포장갯수','sum'), Weight=('Weight','sum'), Measure=('Measure','sum')).reset_index()
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            
            lines = []
            num_containers = len(total)
            
            if num_containers > 1:
                g_p = int(total['포장갯수'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10)]) 
            
            for _, r in total.iterrows():
                lines.append(""); lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
            
            lines.extend(["", "", "<MARK>", ""]) 
            for i, r in marks.iterrows():
                if i > 0: lines.append("") 
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    # 번호 출력 시 .0 제거 처리
                    h_str = str(hbl).strip().replace(".0", "")
                    lines.append(h_str)
                    if num_containers <= 4 and mark_spacing: lines.append("")
                if not (num_containers <= 4 and mark_spacing): lines.append("") 
            
            lines.extend(["", "<DESCRIPTION>", ""]) 
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""]) 
                    lines.extend([f"{cur[0]} / {cur[1]}", ""])
                    prev = cur
                
                h_no_raw = str(r['House B/L No']).strip().replace(".0", "")
                lines.append(h_no_raw)
                lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                
                # 매칭 로직 (HBL 번호 정밀 대조)
                info = item_dict.get(h_no_raw)
                if info:
                    if info["desc"]: lines.append(info["desc"])
                    if info["hs"]: lines.append(info["hs"])
                lines.append("")
            
            result = "\n".join(lines)
            with col_res:
                st.subheader("정리 결과")
                if empty_line_bls: st.warning(f"📢 **다중 품목 의심 B/L:** {', '.join(list(set(empty_line_bls)))} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
