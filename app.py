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

# --- 1. 유틸리티 함수 (카고3/4 순정 디자인 및 폰트 유지) ---
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

# --- 2. 메모장 데이터 분석 ---
def parse_sr_txt(txt_content):
    data = {"total_pkg": 0, "total_wgt": "0", "total_msr": "0", "containers": [], "seals": [], "hbl_list": []}
    pkg_match = re.search(r"TOTAL:\s*(\d+)\s*PKGS", txt_content)
    wgt_match = re.search(r"/\s*([\d.]+)\s*KGS", txt_content)
    msr_match = re.search(r"/\s*([\d.]+)\s*CBM", txt_content)
    if pkg_match: data["total_pkg"] = int(pkg_match.group(1))
    if wgt_match: data["total_wgt"] = wgt_match.group(1)
    if msr_match: data["total_msr"] = msr_match.group(1)
    
    cntr_matches = re.findall(r"([A-Z]{4}\d{7})\s*/\s*([A-Z0-9]+)", txt_content)
    for c, s in cntr_matches:
        data["containers"].append(c); data["seals"].append(s)
        
    if "<DESCRIPTION>" in txt_content:
        desc_part = txt_content.split("<DESCRIPTION>")[-1]
        blocks = re.findall(r"([A-Z0-9]{8,16})\n(\d+)\s*\w+\s*/\s*([\d.]+)\s*KGS\s*/\s*([\d.]+)\s*CBM", desc_part)
        for hbl, pkg, wgt, msr in blocks:
            data["hbl_list"].append({"hbl": hbl, "wgt": format_number(wgt), "msr": format_number(msr)})
    return data

# --- 3. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정리", "MBL 검수", "업로드 기록"])

# --- TAB 1: SR 정리 (사용자님이 선호하는 오리지널 레이아웃) ---
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

# --- TAB 2: MBL 검수 (HBL 텍스트 위치 기반 정밀 검수) ---
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1. 메모장 정보 입력**")
        input_mode = st.radio("방식 선택", ["복사 붙여넣기", "파일 업로드"], horizontal=True, label_visibility="collapsed")
        memo_content = ""
        if input_mode == "복사 붙여넣기":
            memo_content = st.text_area("메모장 내용을 여기에 붙여넣으세요.", height=250)
        else:
            m_file = st.file_uploader("메모장 파일 업로드 (.txt)", type=["txt"], key="m_up")
            if m_file: memo_content = m_file.read().decode("utf-8")
            
    with col2:
        st.markdown("**2. 선사 DRAFT BL 업로드**")
        draft_pdf = st.file_uploader("PDF 파일 업로드 (.pdf)", type=["pdf"], key="d_up", label_visibility="collapsed")
        
        if memo_content and draft_pdf:
            try:
                sr = parse_sr_txt(memo_content)
                errors = []
                with pdfplumber.open(draft_pdf) as pdf:
                    for page in pdf.pages:
                        p_text = page.extract_text()
                        if not p_text: continue
                        p_text_upper = p_text.upper()
                        
                        for item in sr["hbl_list"]:
                            hbl = item["hbl"]
                            if hbl in p_text_upper:
                                # HBL 번호가 발견된 위치 근처 600자(MSC Rider 표 한 칸 분량)를 긁어옴
                                start = p_text_upper.find(hbl)
                                context = p_text_upper[start : start + 600]
                                
                                # 해당 HBL 영역 내에서 우리가 기대하는 수치(CBM, KGS)가 있는지 확인
                                if item["msr"] not in context:
                                    # 잘못된 수치가 적혀있을 가능성이 높으므로 에러 메시지 구성
                                    # 해당 영역에서 숫자 + CU. M 패턴을 찾아 실제 적힌 수치 추출 시도
                                    found_val = re.search(r"([\d,]+\.\d{3})\s*(?:CU\.\s*M|CBM)", context)
                                    wrong_val = found_val.group(1) if found_val else "확인불가"
                                    errors.append(f"❌ 부피 불일치: {item['msr']} CBM (HBL: {hbl}) → PDF상 {wrong_val} 기재됨")
                                
                                if item["wgt"] not in context:
                                    found_wgt = re.search(r"([\d,]+\.\d{3})\s*KGS", context)
                                    wrong_wgt = found_wgt.group(1) if found_wgt else "확인불가"
                                    errors.append(f"❌ 중량 불일치: {item['wgt']} KGS (HBL: {hbl}) → PDF상 {wrong_wgt} 기재됨")

                st.divider()
                if not errors:
                    st.success("✅ 모든 항목이 정확히 일치합니다.")
                else:
                    # 사용자님이 원하셨던 '촘촘한' 스타일 유지
                    for err in errors:
                        st.error(err)
            except Exception as e:
                st.error(f"오류 발생: {e}")

with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
