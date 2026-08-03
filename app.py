import streamlit as st
import pandas as pd
import os
import re
import io
from datetime import datetime, timedelta, timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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

# [IST CONSOL 전용] 날짜 포맷 함수 (예: 9-Sep)
def format_date_ist(v):
    if pd.isna(v) or not v:
        return ""
    try:
        if isinstance(v, (datetime, pd.Timestamp)):
            dt = v
        else:
            v_str = str(v).strip().split(' ')[0]
            dt = pd.to_datetime(v_str)
        return f"{dt.day}-{dt.strftime('%b')}"
    except:
        return str(v).split(' ')[0]

# [IST CONSOL 전용] 회사명 정제 파서
def clean_company_name(text, is_pus=False, is_shipper=True):
    if pd.isna(text) or not str(text).strip():
        return ""
    
    raw = str(text).strip()
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    if not lines:
        return ""
    
    # PUS 시작 여부에 따른 줄 선택
    if is_pus:
        target_lines = lines[:1]
    else:
        if is_shipper:
            if lines[0].upper().startswith("NIPPON"):
                target_lines = lines
            else:

                target_lines = lines[1:] if len(lines) > 1 else lines
        else:
            target_lines = lines
            
    if not target_lines:
        return ""
        
    full_text = " ".join(target_lines)
    
    # 불필요 서두 문구 제거
    prefixes = [
        r"^O/B\s*", r"^O/B:\s*", r"^AS\s+AGENT\s+OF\s*", r"^ON\s+BEHALF\s+OF\s*",
        r"^OB\s*", r"^OB:\s*", r"^AS\s+AGENTS\s+FOR\s*", r"^AS\s+AGENT\s+FOR\s*"
    ]
    for ptn in prefixes:
        full_text = re.sub(ptn, "", full_text, flags=re.IGNORECASE).strip()
        
    # 법인 확장 키워드 패턴
    suffixes = [
        r"LTD\.", r"LIMITED", r"A\.S", r"A\.S\.", r"\bAS\b", r"INC\.",
        r"STI\.", r"STI", r"CO\.,\s*LTD\.", r"CORP\.", r"CORPORATION"
    ]
    
    words = full_text.split()
    matched_idx = -1
    for i, w in enumerate(words):
        w_clean = re.sub(r'[^A-Za-z\.]', '', w).upper()
        for sfx in suffixes:
            s_clean = re.sub(r'[^A-Za-z\.]', '', sfx).upper()
            if w_clean == s_clean or w_clean.endswith(s_clean):
                matched_idx = i
                break
        if matched_idx != -1:
            break
            
    if matched_idx != -1:
        comp_name = " ".join(words[:matched_idx+1])
    else:
        comp_name = target_lines[0]
        
    for ptn in prefixes:
        comp_name = re.sub(ptn, "", comp_name, flags=re.IGNORECASE).strip()
        
    return comp_name

# --- POD 정의 ---
POD_LIST = [
    ("전체", "ALL"),
    ("벨기에", "BEANR"), ("독일", "DEHAM"), ("덴마크", "DKAAR"), ("스페인", "ESBCN"),
    ("프랑스", "FRFOS"), ("프랑스", "FRLEH"), ("영국", "GBSOU"), ("이탈리아", "ITGOA"),
    ("네덜란드", "NLRTM"), ("노르웨이", "NOOSL"), ("폴란드", "PLGDN"), ("루마니아", "ROCND"),
    ("스웨덴", "SEGOT"), ("슬로베니아", "SIKOP"), ("터키", "TRIST")
]
POD_OPTIONS = [f"{country} ({code})" if code != "ALL" else "전체 (ALL)" for country, code in POD_LIST]

# --- 2. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool (Cargo Tool 6)", layout="wide")
st.title("🚢 Europe Docs tool")

# 탭 생성 (IST CONSOL 신규 탭 추가)
tab1, tab_ceva, tab_ist, tab_history, tab2 = st.tabs(["SR 정정", "CEVA(LEH)", "IST CONSOL", "선적이력", "업로드 기록"])

# ==========================================
# TAB 1: SR 정정 (Cargo Tool 6 - 대원칙 보존)
# ==========================================
with tab1:
    col_up1, col_up2, col_opt = st.columns([1.0, 1.5, 0.8])
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
    with col_up2:
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
            item_dict = {}; warning_messages = []

            if "House B/L No" in sr_df.columns and "단위" in sr_df.columns:
                for _, row in sr_df.iterrows():
                    h_no_sr = str(row["House B/L No"]).strip()
                    unit_sr = str(row["단위"]).strip().upper() if pd.notna(row["단위"]) else ""
                    if h_no_sr and h_no_sr != "nan":
                        if unit_sr == "GT":
                            warning_messages.append(f"⚠️ {h_no_sr}: 단위가 GT 입니다.")

            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                if "House B/L No" in item_df.columns and "품목" in item_df.columns:
                    for _, row in item_df.iterrows():
                        h_no = str(row["House B/L No"]).strip()
                        raw_desc = str(row["품목"]).strip() if pd.notna(row["품목"]) else ""
                        
                        if h_no and h_no != "nan":
                            all_lines = [l.strip() for l in raw_desc.split('\n') if l.strip()]
                            found_hs_list = []
                            for line in all_lines:
                                if re.match(r'^[0-9.]{4,11}$', line):
                                    found_hs_list.append(line)
                            
                            detected_hs = found_hs_list[-1] if found_hs_list else ""
                            detected_desc_pure = raw_desc
                            if detected_hs:
                                detected_desc_pure = raw_desc.replace(detected_hs, "").strip()
                            
                            item_dict[h_no] = {"desc": raw_desc, "hs": detected_hs}
                            
                            has_multiple = False
                            if len(all_lines) >= 3:
                                for i in range(len(all_lines) - 2):
                                    if re.match(r'^[0-9.]{4,10}$', all_lines[i]) and not re.match(r'^[0-9.]{4,10}$', all_lines[i+1]):
                                        has_multiple = True
                                        break
                            if has_multiple:
                                warning_messages.append(f"📢 {h_no}: 다중 품목 -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")

                            is_desc_empty = not detected_desc_pure or detected_desc_pure.lower() == "nan" or detected_desc_pure.strip() == ""
                            is_hs_empty = not detected_hs or detected_hs.strip() == ""

                            if is_desc_empty and is_hs_empty:
                                warning_messages.append(f"⚠️ {h_no}: 품목, HS CODE 가 공란입니다!")
                            elif is_desc_empty:
                                warning_messages.append(f"⚠️ {h_no}: 품목이 공란입니다!")
                            elif is_hs_empty:
                                warning_messages.append(f"⚠️ {h_no}: HS CODE 가 공란입니다!")
                            else:
                                clean_hs_digits = re.sub(r'[^0-9]', '', detected_hs)
                                if "." in detected_hs:
                                    if not re.match(r'^\d{4}\.\d{2}$', detected_hs):
                                        warning_messages.append(f"⚠️ {h_no}: HS CODE 형식 오류")
                                elif len(clean_hs_digits) != 6:
                                    warning_messages.append(f"⚠️ {h_no}: HS CODE 형식 오류")
                            
                            if "MAGNET" in raw_desc.upper():
                                warning_messages.append(f"⚠️ {h_no}: 자성물질 MSDS 필요!")
                            
                            if detected_hs:
                                clean_hs = str(detected_hs).replace(".", "").replace(" ", "")
                                if clean_hs == "242400":
                                    warning_messages.append(f"⚠️ {h_no}: 유효하지 않은 HS CODE / HOUSEHOLD GOODS 는 9905.00 을 써주세요.")

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
                    if num_containers <= 4 and mark_spacing: lines.append("") 
                if not (num_containers <= 4 and mark_spacing): lines.append("") 
            
            lines.extend(["", "<DESCRIPTION>", ""]) 
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""]) 
                    if num_containers > 1: lines.extend([f"{cur[0]} / {cur[1]}", ""])
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
            
            if warning_messages:
                combined_warning = "\n".join(warning_messages)
                st.markdown(f'<div style="display:inline-block;padding:5px 15px;border-radius:5px;background-color:rgba(255, 75, 75, 0.1);border:1px solid rgb(255, 75, 75);color:rgb(255, 75, 75);font-family:sans-serif;font-size:14px;line-height:1.5;white-space:pre-wrap;margin-bottom:5px;">{combined_warning}</div><br>', unsafe_allow_html=True)
            
            st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# ==========================================
# TAB 2: CEVA(LEH)
# ==========================================
with tab_ceva:
    col_ceva_up = st.columns([1])[0]
    with col_ceva_up:
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
                {"qty": (76,8), "unit": (76,14), "wgt": (77,8), "cbm": (78,8), "hc": (79,4), "mark": (77,16), "desc": (77,34)},
                {"qty": (85,8), "unit": (85,14), "wgt": (86,8), "cbm": (87,8), "hc": (88,4), "mark": (86,16), "desc": (86,34)},
                {"qty": (94,8), "unit": (94,14), "wgt": (95,8), "cbm": (96,8), "hc": (97,4), "mark": (95,16), "desc": (95,34)}
            ]
            
            mark_lines, desc_lines = [], []
            for s in sets:
                qty_val = get_val(*s["qty"])
                if not qty_val: continue
                qty_int = int(float(qty_val)) if qty_val.replace('.','').isdigit() else 0
                unit_str = format_unit_ceva(get_val(*s["unit"]), qty_int)
                wgt_str = format_wgt_ceva(get_val(*s["wgt"]))
                hc_val_raw, mark_str, desc_str = get_val(*s["hc"]), get_val(*s["mark"]), get_val(*s["desc"])
                
                mark_lines.extend([mark_str, "", ""])
                desc_lines.append(desc_str)
                desc_lines.append(f"{qty_int} {unit_str} / {wgt_str} KGS / CBM")
                if hc_val_raw:
                    desc_lines.append(f"HC: {hc_val_raw.replace('HC:', '').strip()}")
                desc_lines.extend(["", ""]) 
            
            st.divider()
            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.subheader("<MARK>")
                st.text_area("MARK 결과", "\n".join(mark_lines), height=600, label_visibility="collapsed")
            with res_col2:
                st.subheader("<DESCRIPTION>")
                st.text_area("DESC 결과", "\n".join(desc_lines), height=600, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# ==========================================
# TAB 3: IST CONSOL (신규 추가 탭)
# ==========================================
with tab_ist:
    col_ist_up = st.columns([1.5, 1])[0]
    with col_ist_up:
        ist_file = st.file_uploader("IST 엑셀 파일(1파일)을 업로드하세요", type=["xlsx"], key="ist_up")
        
    st.divider()
    
    if ist_file:
        try:
            log_uploaded_filename(ist_file.name, "IST")
            raw_ist_df = pd.read_excel(ist_file)
            
            # 헤더 행 유연 감지
            header_idx = None
            if "House B/L No" in raw_ist_df.columns:
                df1 = raw_ist_df
            else:
                for idx in range(min(5, len(raw_ist_df))):
                    row_vals = [str(v).strip() for v in raw_ist_df.iloc[idx].values]
                    if any("House B/L" in v for v in row_vals):
                        header_idx = idx
                        break
                if header_idx is not None:
                    df1 = pd.read_excel(ist_file, header=header_idx + 1)
                else:
                    df1 = raw_ist_df

            df1.columns = [str(c).strip() for c in df1.columns]
            
            # 유연 열 매핑 추적
            hbl_col = next((c for c in df1.columns if "House B/L" in c), None)
            vessel_col = next((c for c in df1.columns if "Vessel" in c), None)
            voyage_col = next((c for c in df1.columns if "항차" in c), None)
            etd_col = next((c for c in df1.columns if "ETD" in c), None)
            eta_col = next((c for c in df1.columns if "ETA" in c), None)
            mbl_col = next((c for c in df1.columns if "Master B/L" in c), None)
            shipper_col = next((c for c in df1.columns if "Shipper" in c and "Real" not in c), None)
            consignee_col = next((c for c in df1.columns if "Consignee" in c), None)
            notify_col = next((c for c in df1.columns if "Notify" in c), None)
            weight_col = next((c for c in df1.columns if "Weight" in c), None)
            pkg_col = next((c for c in df1.columns if "포장갯수" in c), None)
            measure_col = next((c for c in df1.columns if "Measure" in c), None)
            cntr_col = next((c for c in df1.columns if "컨테이너" in c), None)
            seal_col = next((c for c in df1.columns if "Seal No" in c or "Seal#1" in c), None)

            if hbl_col:
                valid_df = df1.dropna(subset=[hbl_col]).copy()
                first_row = valid_df.iloc[0] if len(valid_df) > 0 else None
                
                vessel_val = str(first_row[vessel_col]).strip() if (first_row is not None and vessel_col and pd.notna(first_row[vessel_col])) else ""
                voyage_val = str(first_row[voyage_col]).strip() if (first_row is not None and voyage_col and pd.notna(first_row[voyage_col])) else ""
                etd_val = format_date_ist(first_row[etd_col]) if (first_row is not None and etd_col) else ""
                eta_val = format_date_ist(first_row[eta_col]) if (first_row is not None and eta_col) else ""
                mbl_val = str(first_row[mbl_col]).strip() if (first_row is not None and mbl_col and pd.notna(first_row[mbl_col])) else ""

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "IST FINAL"

                # 테두리 및 스타일 정의
                thin = Side(border_style="thin", color="000000")
                box_border = Border(left=thin, right=thin, top=thin, bottom=thin)
                align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
                align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
                fill_header = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
                font_title = Font(name="Calibri", size=14, bold=True)
                font_header = Font(name="Calibri", size=10, bold=True)
                font_data = Font(name="Calibri", size=10, bold=False)

                # 상단 헤더 텍스트 작성
                ws["B2"] = "IST FINAL CONSOL LIST"; ws["B2"].font = font_title
                
                headers_r1 = [
                    ("E2", "Vessel", vessel_val), ("F2", "Voyage", voyage_val), ("G2", "", ""),
                    ("H2", "ETD", etd_val), ("I2", "ETA", eta_val), ("J2", "Master B/L No.", mbl_val),
                    ("K2", "", ""), ("L2", "", ""), ("M2", "Carrier", "MSC")
                ]
                
                for cell_ref, title, val in headers_r1:
                    cell = ws[cell_ref]
                    cell.value = f"{title}\n{val}".strip() if title else val
                    cell.font = font_header; cell.alignment = align_center; cell.fill = fill_header; cell.border = box_border

                ws["B3"] = "BUSAN"; ws["B3"].font = font_header; ws["B3"].alignment = align_center; ws["B3"].fill = fill_header; ws["B3"].border = box_border
                ws["B4"] = "ISTANBUL"; ws["B4"].font = font_header; ws["B4"].alignment = align_center; ws["B4"].fill = fill_header; ws["B4"].border = box_border

                table_headers = [
                    ("B5", "HBL No."), ("C5", "CNTR SIZE"), ("D5", "Shipper"), ("E5", "Consignee"),
                    ("F5", "KGS"), ("G5", "PKG'S"), ("H5", ""), ("I5", "CBM"),
                    ("J5", "R/O"), ("K5", "Container No."), ("L5", "Seal No."), ("M5", "REMARKS")
                ]
                for cell_ref, h_text in table_headers:
                    cell = ws[cell_ref]
                    cell.value = h_text
                    cell.font = font_header; cell.alignment = align_center; cell.fill = fill_header; cell.border = box_border

                # 데이터 행 채우기
                start_row = 6
                preview_data = []

                for idx, r in valid_df.iterrows():
                    row_idx = start_row + len(preview_data)
                    hbl_val = str(r[hbl_col]).strip() if pd.notna(r[hbl_col]) else ""
                    is_pus = hbl_val.upper().startswith("PUS")

                    # Shipper 파싱
                    raw_shipper = r[shipper_col] if shipper_col else ""
                    shipper_clean = clean_company_name(raw_shipper, is_pus=is_pus, is_shipper=True)

                    # Consignee 파싱
                    if is_pus:
                        raw_consignee = r[consignee_col] if consignee_col else ""
                        consignee_clean = clean_company_name(raw_consignee, is_pus=True, is_shipper=False)
                    else:
                        raw_notify = r[notify_col] if notify_col else ""
                        consignee_clean = clean_company_name(raw_notify, is_pus=False, is_shipper=False)

                    wgt_v = r[weight_col] if weight_col else ""
                    pkg_v = r[pkg_col] if pkg_col else ""
                    cbm_v = r[measure_col] if measure_col else ""
                    cntr_v = r[cntr_col] if cntr_col else ""
                    seal_v = r[seal_col] if seal_col else ""

                    row_data = {
                        "B": hbl_val,
                        "C": "40'HC",
                        "D": shipper_clean,
                        "E": consignee_clean,
                        "F": format_number(wgt_v),
                        "G": int(float(pkg_v)) if (pd.notna(pkg_v) and str(pkg_v).replace('.','').isdigit()) else pkg_v,
                        "H": "PKG'S",
                        "I": format_number(cbm_v),
                        "J": "",
                        "K": str(cntr_v).strip() if pd.notna(cntr_v) else "",
                        "L": str(seal_v).strip().split('.')[0] if pd.notna(seal_v) else "",
                        "M": ""
                    }

                    for col_letter, val in row_data.items():
                        cell = ws[f"{col_letter}{row_idx}"]
                        cell.value = val
                        cell.font = font_data; cell.border = box_border
                        if col_letter in ["F", "G", "I"]:
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                        elif col_letter in ["D", "E"]:
                            cell.alignment = align_left
                        else:
                            cell.alignment = align_center

                    preview_data.append(row_data)

                # 열 너비 자동 설정
                for col in ws.columns:
                    col_letter = get_column_letter(col[0].column)
                    if col_letter in ["D", "E"]:
                        ws.column_dimensions[col_letter].width = 32
                    elif col_letter in ["B", "K", "L"]:
                        ws.column_dimensions[col_letter].width = 18
                    else:
                        ws.column_dimensions[col_letter].width = 12

                output_excel = io.BytesIO()
                wb.save(output_excel)
                output_excel.seek(0)

                st.subheader("정리 결과")
                st.download_button(
                    label="💾 IST FINAL CONSOL LIST 엑셀 다운로드",
                    data=output_excel,
                    file_name=f"IST_FINAL_CONSOL_LIST_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

                if preview_data:
                    out_p_df = pd.DataFrame(preview_data)
                    out_p_df.columns = ["HBL No.", "CNTR SIZE", "Shipper", "Consignee", "KGS", "PKG'S", "UNIT", "CBM", "R/O", "Container No.", "Seal No.", "REMARKS"]
                    st.dataframe(out_p_df, use_container_width=True, height=500)

            else:
                st.error("엑셀 파일 내 'House B/L No' 열을 찾을 수 없습니다.")

        except Exception as e:
            st.error(f"IST 데이터 처리 중 오류 발생: {e}")

# ==========================================
# TAB 4: 선적이력
# ==========================================
with tab_history:
    col_pod, col_query, col_btn = st.columns([1, 1.8, 0.5])
    with col_pod:
        selected_pod_opt = st.selectbox("POD 선택", POD_OPTIONS, index=0)
        
        if "ALL" in selected_pod_opt:
            pod_code = "ALL"
        else:
            pod_code = selected_pod_opt.split("(")[-1].replace(")", "").strip()
            
    with col_query:
        search_query = st.text_input("HS CODE 또는 품목명 검색", placeholder="예: AUTOMOTIVE, 844391, 2008.99, MAGNET 등")
    with col_btn:
        st.write("") 
        st.write("")
        search_btn = st.button("🔍 검색", use_container_width=True)
    
    st.divider()

    if search_query.strip():
        search_upper = search_query.strip().upper()
        search_digits = re.sub(r'[^0-9]', '', search_upper)
        history_warnings = []

        if "200899" in search_digits or "2008.99" in search_upper:
            history_warnings.append("⚠️ 2008.99-9000 EU 관세 품목 분류에 등록 되지 않은 코드")
        if "242400" in search_digits or "2424.00" in search_upper:
            history_warnings.append("⚠️ 유효하지 않은 HS CODE / HOUSEHOLD GOODS 는 9905.00 을 써주세요.")
        if "MAGNET" in search_upper or "자성" in search_upper:
            history_warnings.append("⚠️ 자성물질 MSDS 필요")
        if "CARBON" in search_upper or "카본" in search_upper:
            history_warnings.append("⚠️ carbon DG 로 간주되어 LCL 선적 불가")
        if "ALKALINE" in search_upper or "알카라인" in search_upper:
            history_warnings.append("ℹ️ Alkaline Battery 선적 가능")
        if "LITHIUM" in search_upper or "리튬" in search_upper:
            history_warnings.append("⚠️ lithium battery NON-DG 여도 LCL 선적 불가")
        if any(kw in search_upper for kw in ["FOOD", "식품", "음식"]):
            history_warnings.append("⚠️ FOOD STUFF 도착지 확인 필요")

        if history_warnings:
            combined_hist_warning = "\n".join(history_warnings)
            st.markdown(f'<div style="display:inline-block;padding:5px 15px;border-radius:5px;background-color:rgba(255, 75, 75, 0.1);border:1px solid rgb(255, 75, 75);color:rgb(255, 75, 75);font-family:sans-serif;font-size:14px;line-height:1.5;white-space:pre-wrap;margin-bottom:15px;">{combined_hist_warning}</div><br>', unsafe_allow_html=True)

    files_to_scan = []
    if pod_code == "ALL":
        for country, code in POD_LIST:
            if code == "ALL": continue
            pfile = f"{code}.xlsx"
            if os.path.exists(pfile):
                files_to_scan.append((code, pfile))
            elif code == "PLGDN" and os.path.exists("GDN.xlsx"):
                files_to_scan.append((code, "GDN.xlsx"))
    else:
        pfile = f"{pod_code}.xlsx"
        if os.path.exists(pfile):
            files_to_scan.append((pod_code, pfile))
        elif pod_code == "PLGDN" and os.path.exists("GDN.xlsx"):
            files_to_scan.append((pod_code, "GDN.xlsx"))
            
    if files_to_scan:
        all_matched_rows = []
        for cur_pod, target_file in files_to_scan:
            try:
                raw_df = pd.read_excel(target_file)
                
                header_row_idx = None
                if "House B/L No" in raw_df.columns:
                    hist_df = raw_df
                else:
                    for idx in range(min(5, len(raw_df))):
                        row_vals = [str(v).strip() for v in raw_df.iloc[idx].values]
                        if any("House B/L" in v for v in row_vals):
                            header_row_idx = idx
                            break
                    if header_row_idx is not None:
                        hist_df = pd.read_excel(target_file, header=header_row_idx + 1)
                    else:
                        hist_df = raw_df

                hist_df.columns = [str(c).strip() for c in hist_df.columns]
                
                hbl_col = next((c for c in hist_df.columns if "House B/L" in c), None)
                etd_col = next((c for c in hist_df.columns if "ETD" in c), None)
                item_col = next((c for c in hist_df.columns if "품목" in c), None)
                
                if hbl_col and etd_col and item_col:
                    res_df = hist_df[[hbl_col, etd_col, item_col]].copy()
                    res_df.columns = ['House B/L No', 'ETD', '품목']
                    res_df = res_df.dropna(subset=['House B/L No'])
                    
                    if search_query.strip():
                        q_raw = search_query.strip().upper()
                        q_digits = re.sub(r'[^0-9]', '', q_raw)
                        
                        for _, r in res_df.iterrows():
                            item_val = str(r['품목']) if pd.notna(r['품목']) else ""
                            item_upper = item_val.upper()
                            item_digits = re.sub(r'[^0-9]', '', item_val)
                            
                            is_match = False
                            if len(q_digits) >= 4 and q_digits in item_digits:
                                is_match = True
                            elif q_raw in item_upper:
                                is_match = True
                                
                            if is_match:
                                etd_str = str(r['ETD']).split(' ')[0] if pd.notna(r['ETD']) else ""
                                item_dict = {
                                    'House B/L No': str(r['House B/L No']).strip(),
                                    'ETD': etd_str,
                                    '품목': item_val.strip()
                                }
                                if pod_code == "ALL":
                                    item_dict = {'POD': cur_pod, **item_dict}
                                all_matched_rows.append(item_dict)
            except Exception as e:
                pass
                
        if search_query.strip():
            if all_matched_rows:
                out_df = pd.DataFrame(all_matched_rows)
                st.subheader(f"🔍 검색 결과 ({len(out_df)}건)")
                
                cfg = {
                    "House B/L No": st.column_config.TextColumn("House B/L No", width=160),
                    "ETD": st.column_config.TextColumn("ETD", width=110),
                    "품목": st.column_config.TextColumn("품목", width=400),
                }
                if pod_code == "ALL":
                    cfg = {"POD": st.column_config.TextColumn("POD", width=90), **cfg}
                    
                st.dataframe(
                    out_df,
                    column_config=cfg,
                    use_container_width=False,
                    height=500
                )
            else:
                st.info("검색 조건에 맞는 이력이 없습니다.")
        else:
            st.write("💡 HS CODE 또는 품목명을 입력 후 Enter를 누르거나 [🔍 검색] 버튼을 누르면 해당 POD의 진행 이력을 검색합니다.")
    else:
        st.warning("저장된 이력 엑셀 파일이 없습니다. (루트 폴더에 포트코드.xlsx 파일을 넣어주세요)")

# ==========================================
# TAB 5: 업로드 기록
# ==========================================
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: 
            st.text_area("Log", f.read(), height=800)
