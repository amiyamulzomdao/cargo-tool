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
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 2. 메모장 분석 엔진 (복붙/파일 공용) ---
def parse_sr_txt(txt_content):
    data = {"containers": [], "seals": [], "hbl_list": [], "total_pkg": 0, "total_wgt": "0"}
    pkg_match = re.search(r"TOTAL:\s*(\d+)\s*PKGS", txt_content)
    wgt_match = re.search(r"/\s*([\d.]+)\s*KGS", txt_content)
    if pkg_match: data["total_pkg"] = int(pkg_match.group(1))
    if wgt_match: data["total_wgt"] = wgt_match.group(1)
    
    cntr_matches = re.findall(r"([A-Z]{4}\d{7})\s*/\s*([A-Z0-9]+)", txt_content)
    for c, s in cntr_matches:
        data["containers"].append(c); data["seals"].append(s)
        
    if "<DESCRIPTION>" in txt_content:
        desc_part = txt_content.split("<DESCRIPTION>")[-1]
        hbl_blocks = re.findall(r"([A-Z0-9]{8,16})\n(\d+)\s*\w+\s*/\s*([\d.]+)\s*KGS", desc_part)
        for hbl, pkg, wgt in hbl_blocks:
            search_area = desc_part.split(hbl)[-1].split("\n\n")[0]
            hs_match = re.search(r"(\d{4}\.\d{2})", search_area)
            data["hbl_list"].append({"hbl": hbl, "hs": hs_match.group(1) if hs_match else "", "wgt": wgt})
    return data

# --- 3. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정리", "MBL 검수", "업로드 기록"])

# --- TAB 1: SR 정리 (기존 오리지널 레이아웃) ---
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
                lines.append(""); lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
            
            lines.extend(["", "", "<MARK>", ""]) 
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

# --- TAB 2: MBL 검수 (복붙 기능 추가) ---
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**메모장 정보 입력**")
        input_mode = st.radio("방식", ["복사 붙여넣기", "파일 업로드"], horizontal=True, label_visibility="collapsed")
        memo_content = ""
        if input_mode == "복사 붙여넣기":
            memo_content = st.text_area("메모장 내용을 여기에 붙여넣으세요.", height=200)
        else:
            m_file = st.file_uploader("메모장 업로드 (.txt)", type=["txt"])
            if m_file: memo_content = m_file.read().decode("utf-8")
            
    with col2:
        st.markdown("**선사 DRAFT BL 업로드**")
        draft_pdf = st.file_uploader("PDF 업로드", type=["pdf"], label_visibility="collapsed")
    
    if memo_content and draft_pdf:
        try:
            sr = parse_sr_txt(memo_content)
            with pdfplumber.open(draft_pdf) as pdf:
                pdf_text = "".join([p.extract_text() for p in pdf.pages]).upper()
            
            errors = []
            if str(sr["total_pkg"]) not in pdf_text: errors.append(f"❌ 총 수량 불일치: {sr['total_pkg']} PKGS")
            if sr["total_wgt"] not in pdf_text: errors.append(f"❌ 총 중량 불일치: {sr['total_wgt']} KGS")
            for c in set(sr["containers"]):
                if c.upper() not in pdf_text: errors.append(f"❌ 컨테이너 번호 누락: {c}")
            for s in set(sr["seals"]):
                if s and s.upper() not in pdf_text: errors.append(f"❌ Seal 번호 누락: {s}")
            for item in sr["hbl_list"]:
                if item["hs"] and item["hs"] not in pdf_text: errors.append(f"❌ HS CODE 불일치 ({item['hbl']}): {item['hs']}")
                if item["wgt"] not in pdf_text: errors.append(f"❌ 중량 불일치 ({item['hbl']}): {item['wgt']} KGS")
            
            st.divider()
            if not errors: st.success("✅ 불일치 항목 없음")
            else:
                for err in errors: st.error(err)
        except Exception as e: st.error(f"오류: {e}")

# --- TAB 3: 업로드 기록 ---
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
