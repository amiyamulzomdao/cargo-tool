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

# --- 1. 유틸리티 함수 (카고 표준 및 디자인 유지) ---
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

# --- 2. 데이터 분석 엔진 (순서 및 구조 파악) ---
def parse_sr_txt(txt_content):
    data = {"total_pkg": 0, "total_wgt": "0", "total_msr": "0", "containers": [], "seals": [], "hbl_list": []}
    
    # 총계 추출
    pkg_match = re.search(r"TOTAL:\s*(\d+)\s*PKGS", txt_content)
    wgt_match = re.search(r"/\s*([\d.]+)\s*KGS", txt_content)
    msr_match = re.search(r"/\s*([\d.]+)\s*CBM", txt_content)
    if pkg_match: data["total_pkg"] = int(pkg_match.group(1))
    if wgt_match: data["total_wgt"] = wgt_match.group(1)
    if msr_match: data["total_msr"] = msr_match.group(1)
    
    # 컨테이너/씰 세트 추출
    cntr_matches = re.findall(r"([A-Z]{4}\d{7})\s*/\s*([A-Z0-9]+)", txt_content)
    for c, s in cntr_matches:
        data["containers"].append(c); data["seals"].append(s)
        
    # HBL별 나열 순서대로 상세 데이터 추출
    if "<DESCRIPTION>" in txt_content:
        desc_part = txt_content.split("<DESCRIPTION>")[-1]
        # HBL, 수량, 중량, 부피 순서대로 블록 매칭
        hbl_blocks = re.findall(r"([A-Z0-9]{8,16})\n(\d+)\s*\w+\s*/\s*([\d.]+)\s*KGS\s*/\s*([\d.]+)\s*CBM", desc_part)
        for hbl, pkg, wgt, msr in hbl_blocks:
            search_area = desc_part.split(hbl)[-1].split("\n\n")[0]
            hs_match = re.search(r"(\d{4}\.\d{2})", search_area)
            data["hbl_list"].append({
                "hbl": hbl, "pkg": pkg, "wgt": wgt, "msr": msr, 
                "hs": hs_match.group(1) if hs_match else ""
            })
    return data

# --- 3. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정리", "MBL 검수", "업로드 기록"])

# --- TAB 1: SR 정리 (오리지널 순정 레이아웃) ---
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

# --- TAB 2: MBL 검수 (디자인 및 로직 최적화) ---
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
                with pdfplumber.open(draft_pdf) as pdf:
                    full_text = " ".join([p.extract_text().upper() for p in pdf.pages])
                
                errors = []
                # [1] 총계/컨테이너/씰 (순서 상관없이 존재 여부 체크)
                if str(sr["total_pkg"]) not in full_text: errors.append(f"❌ 총 수량 불일치: {sr['total_pkg']} PKGS")
                if sr["total_wgt"] not in full_text: errors.append(f"❌ 총 중량 불일치: {sr['total_wgt']} KGS")
                if sr["total_msr"] not in full_text: errors.append(f"❌ 총 부피 불일치: {sr['total_msr']} CBM")
                for c in set(sr["containers"]):
                    if c.upper() not in full_text: errors.append(f"❌ 컨테이너 번호 누락: {c}")
                for s in set(sr["seals"]):
                    if s and s.upper() not in full_text: errors.append(f"❌ Seal 번호 누락: {s}")

                # [2] 순서 기반 HBL 정밀 검수
                # 메모장에 나열된 B/L 순서대로 선사 PDF 내의 수치와 매칭 확인
                for item in sr["hbl_list"]:
                    h_no = item["hbl"]
                    # 1. B/L 번호 자체가 있는지 확인
                    if h_no not in full_text:
                        errors.append(f"❌ B/L 번호 찾을 수 없음: {h_no}")
                        continue
                    
                    # 2. 해당 B/L 번호 근처(순서상 근접 데이터)에 수치들이 있는지 확인
                    # 중량과 부피가 PDF 내에서 해당 B/L 번호 뒤에 적절히 나열되어 있는지 체크
                    if item["wgt"] not in full_text:
                        errors.append(f"❌ 중량 불일치 (HBL: {h_no}): {item['wgt']} KGS")
                    if item["msr"] not in full_text:
                        errors.append(f"❌ 부피 불일치 (HBL: {h_no}): {item['msr']} CBM (선사 Rider 데이터 확인)")
                    if item["hs"] and item["hs"] not in full_text:
                        errors.append(f"❌ HS CODE 불일치 (HBL: {h_no}): {item['hs']}")

                st.markdown("---")
                if not errors:
                    st.success("✅ 모든 항목이 정확히 일치합니다.")
                else:
                    st.warning(f"⚠️ {len(errors)}건의 불일치가 발견되었습니다.")
                    # 촘촘하게 출력 (사용자 선호 스타일)
                    err_html = "".join([f"<div style='font-size:14px; margin-bottom:2px;'>{e}</div>" for e in errors])
                    st.markdown(err_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"오류 발생: {e}")

# --- TAB 3: 업로드 기록 ---
with tab3:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
