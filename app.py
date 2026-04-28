import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, timedelta, timezone

# --- 1. 유틸리티 함수 ---
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
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# [CEVA 전용] 단위 포맷 함수
def format_unit_ceva(unit, count):
    if not unit: return ""
    u = str(unit).upper().strip()
    mapping = {'PLT': 'PLT', 'PALLET': 'PLT', 'PLTS': 'PLT', 'PKG': 'PKG', 'PKGS': 'PKG', 'CTN': 'CTN', 'CTNS': 'CTN'}
    base = mapping.get(u, u)
    if count > 1:
        return base + "S"
    return base

# [CEVA 전용] 중량 포맷 함수
def format_wgt_ceva(v):
    try:
        val = float(v)
        if val == int(val):
            return str(int(val))
        return str(val)
    except:
        return str(v)

# --- 2. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool (Cargo Tool 4)", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab_ceva, tab2 = st.tabs(["SR 정정", "CEVA(LEH)", "업로드 기록"])

# ==========================================
# TAB 1: SR 정정 (Cargo Tool 4 - 대원칙 보존)
# ==========================================
with tab1:
    # 레이아웃 최적화: 2번 업로드 칸 비중을 늘려 가로 길이 확보
    col_up1, col_up2, col_opt = st.columns([1.0, 1.5, 0.8])
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
    with col_up2:
        # [수정] 요청하신 정확한 문구로 복구
        item_file = st.file_uploader("2. 하우스리스트 → S/R NO 검색 → 엑셀내려받기 파일 입력(품목, HS CODE 추가 가능)", type=["xlsx"], key="item_sub")
    with col_opt:
        st.write("") 
        st.write("") 
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
        mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)

    st.divider()

    if sr_file:
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            item_dict = {}; empty_line_bls = [] 
            warning_messages = []

            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                if "House B/L No" in item_df.columns and "품목" in item_df.columns:
                    for _, row in item_df.iterrows():
                        h_no = str(row["House B/L No"]).strip()
                        raw_desc = str(row["품목"]).strip() if pd.notna(row["품목"]) else ""
                        
                        if h_no and h_no != "nan":
                            found_hs_list = re.findall(r'[0-9]{4,10}|[0-9]{4,6}\.[0-9]{2,4}', raw_desc)
                            detected_hs = found_hs_list[-1] if found_hs_list else ""
                            
                            detected_desc_pure = raw_desc
                            if detected_hs:
                                detected_desc_pure = raw_desc.replace(detected_hs, "").strip()
                            
                            item_dict[h_no] = {"desc": raw_desc, "hs": detected_hs}
                            if "\n\n" in raw_desc: empty_line_bls.append(h_no)

                            # 검증 로직
                            is_desc_empty = not detected_desc_pure or detected_desc_pure.lower() == "nan" or detected_desc_pure.strip() == ""
                            is_hs_empty = not detected_hs or detected_hs.strip() == ""

                            if is_desc_empty and is_hs_empty:
                                warning_messages.append(f"⚠️ {h_no}: 품목, HS CODE 가 공란입니다!")
                            elif is_desc_empty:
                                warning_messages.append(f"⚠️ {h_no}: 품목이 공란입니다!")
                            elif is_hs_empty:
                                warning_messages.append(f"⚠️ {h_no}: HS CODE 가 공란입니다!")
                            
                            if "MAGNET" in raw_desc.upper():
                                warning_messages.append(f"⚠️ {h_no}: 자성물질 MSDS 필요!")
                            
                            if detected_hs:
                                clean_hs = str(detected_hs).replace(".", "").replace(" ", "")
                                if clean_hs == "242400":
                                    warning_messages.append(f"⚠️ {h_no}: 유효하지 않은 HS CODE / HOUSEHOLD GOODS 는 9905.00 을 써주세요.")

            # --- [연산 및 출력 로직 보존 - 수정 0%] ---
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy().dropna(subset=['House B/L No'])
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
                if num_containers > 1:
                    lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                    lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if num_containers <= 4 and mark_spacing:
                        lines.append("") 
                if not (num_containers <= 4 and mark_spacing):
                    lines.append("") 
            
            lines.extend(["", "<DESCRIPTION>", ""]) 
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""]) 
                    if num_containers > 1:
                        lines.extend([f"{cur[0]} / {cur[1]}", ""])
                    prev = cur
                h_no_raw = str(r['House B/L No']).strip()
                lines.append(h_no_raw)
                lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                if h_no_raw in item_dict:
                    info = item_dict[h_no_raw]
                    if info["desc"] and info["desc"].lower() != "nan": lines.append(info["desc"])
                lines.append("")
            
            result = "\n".join(lines)
            res_head, res_down = st.columns([3, 1])
            with res_head: st.subheader("정리 결과")
            with res_down: st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt", use_container_width=True)
            
            # 경고창 디자인: 첫 줄 공백 제거 및 박스 크기 최소화
            if empty_line_bls or (item_file and warning_messages):
                if empty_line_bls:
                    st.warning(f"📢 **다중 품목 의심 B/L:** {', '.join(list(set(empty_line_bls)))} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
                
                if warning_messages:
                    combined_warning = "\n".join(warning_messages)
                    st.markdown(f'<div style="display:inline-block;padding:5px 15px;border-radius:5px;background-color:rgba(255, 75, 75, 0.1);border:1px solid rgb(255, 75, 75);color:rgb(255, 75, 75);font-family:sans-serif;font-size:14px;line-height:1.5;white-space:pre-wrap;margin-bottom:5px;">{combined_warning}</div><br>', unsafe_allow_html=True)
            
            st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# ==========================================
# TAB 2: CEVA(LEH)
# ==========================================
with tab_ceva:
    col_ceva_left, col_ceva_right = st.columns([1, 1.5])
    with col_ceva_left:
        ceva_file = st.file_uploader("CEVA 엑셀 파일을 업로드하세요", type=["xlsx"], key="ceva_up")
    if ceva_file:
        try:
            c_df = pd.read_excel(ceva_file, header=None)
            def get_val(r, c):
                try: 
                    v = c_df.iloc[r, c]
                    return str(v).strip() if pd.notna(v) else ""
                except: return ""
            sets = [
                {"qty": (35,8), "unit": (35,14), "wgt": (36,8), "cbm": (37,8), "hc": (38,4), "mark": (36,16), "desc": (36,34)},
                {"qty": (44,8), "unit": (44,14), "wgt": (45,8), "cbm": (46,8), "hc": (47,4), "mark": (45,16), "desc": (45,34)},
                {"qty": (58,8), "unit": (58,14), "wgt": (59,8), "cbm": (60,8), "hc": (61,4), "mark": (59,16), "desc": (59,34)},
                {"qty": (67,8), "unit": (67,14), "wgt": (68,8), "cbm": (69,8), "hc": (70,4), "mark": (68,16), "desc": (68,34)},
                {"qty": (76,8), "unit": (77,8), "wgt": (77,8), "cbm": (78,8), "hc": (79,4), "mark": (77,16), "desc": (77,34)},
                {"qty": (85,8), "unit": (85,14), "wgt": (86,8), "cbm": (87,8), "hc": (88,4), "mark": (86,16), "desc": (86,34)},
                {"qty": (94,8), "unit": (94,14), "wgt": (95,8), "cbm": (96,8), "hc": (97,4), "mark": (95,16), "desc": (95,34)}
            ]
            mark_lines = []
            desc_lines = []
            for s in sets:
                qty_val = get_val(*s["qty"])
                if not qty_val: continue
                qty_int = int(float(qty_val)) if qty_val.replace('.','').isdigit() else 0
                unit_str = format_unit_ceva(get_val(*s["unit"]), qty_int)
                wgt_str = format_wgt_ceva(get_val(*s["wgt"]))
                hc_val_raw = get_val(*s["hc"])
                mark_str = get_val(*s["mark"])
                desc_str = get_val(*s["desc"])
                mark_lines.append(mark_str); mark_lines.append(""); mark_lines.append("") 
                desc_lines.append(desc_str); desc_lines.append(f"{qty_int} {unit_str} / {wgt_str} KGS / CBM")
                if hc_val_raw:
                    clean_hc = hc_val_raw.replace("HC:", "").strip()
                    desc_lines.append(f"HC: {clean_hc}")
                desc_lines.append(""); desc_lines.append("") 
            ceva_result = "<MARK>\n\n" + "\n".join(mark_lines) + "\n\n<DESCRIPTION>\n\n" + "\n".join(desc_lines)
            with col_ceva_right:
                st.subheader("📋 MARK & DESC 정리")
                st.text_area("CEVA 결과", ceva_result, height=750, label_visibility="collapsed")
        except Exception as e:
            st.error(f"CEVA 처리 중 오류 발생: {e}")

# ==========================================
# TAB 3: 업로드 기록
# ==========================================
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: 
            st.text_area("Log", f.read(), height=800)
