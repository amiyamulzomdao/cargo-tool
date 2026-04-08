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

# --- 1. 유틸리티 함수 (카고4 불변 원칙) ---
def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG', 'PL':'PLT', 'CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    if u_str in ['PK', 'PL', 'CT'] and count > 1: return base + 'S'
    return base

def format_number(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return ""
        val = float(str(v).replace(',', ''))
        if val == int(val): return str(int(val))
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

def log_uploaded_filename(fn, category="SR"):
    p = "upload_log.txt"
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 2. 메모장 분석 엔진 (MBL 검수용) ---
def parse_sr_txt(txt_content):
    data = {"containers": [], "seals": [], "hbl_list": [], "total_pkg": 0, "total_wgt": "0", "total_msr": "0"}
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
        hbl_blocks = re.findall(r"([A-Z0-9]{8,16})\n(\d+)\s*\w+\s*/\s*([\d.]+)\s*KGS\s*/\s*([\d.]+)\s*CBM", desc_part)
        for hbl, pkg, wgt, msr in hbl_blocks:
            search_area = desc_part.split(hbl)[-1].split("\n\n")[0]
            hs_match = re.search(r"(\d{4}\.\d{2})", search_area)
            data["hbl_list"].append({"hbl": hbl, "pkg": pkg, "wgt": wgt, "msr": msr, "hs": hs_match.group(1) if hs_match else ""})
    return data

# --- 3. 페이지 설정 및 세련된 디자인 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif !important; }
    [data-testid="stFileUploadDropzone"] {
        background-color: #f0f2f6 !important;
        border: 2px dashed #34495e !important;
        border-radius: 10px !important;
    }
    .stTextArea textarea {
        font-family: monospace !important;
        font-size: 14px !important;
        line-height: 1.4 !important;
    }
    h3 { font-size: 1rem !important; color: #2c3e50; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab_mbl, tab_ceva, tab_log = st.tabs(["SR 정리", "MBL 검수", "CEVA(LEH)", "업로드 기록"])

# --- TAB 1: SR 정리 (원본 로직 완전 복구) ---
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
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                # 다중 품목 의심 경고
                multi_check = item_df.groupby('House B/L No')['품목'].nunique()
                multi_hbls = multi_check[multi_check > 1].index.tolist()
                if multi_hbls:
                    for hbl in multi_hbls:
                        items = item_df[item_df['House B/L No'] == hbl]['품목'].unique()
                        st.warning(f"⚠️ 다중 품목 의심 ({hbl}): {', '.join(map(str, items))}")

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
                gt_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", gt_line, "-" * (len(gt_line) + 5), ""])
            
            for _, r in total.iterrows():
                lines.extend([f"{r['컨테이너 번호']} / {r['Seal#1']}", f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM", ""])
            
            lines.extend(["", "<MARK>", ""])
            for i, r in marks.iterrows():
                if i > 0: lines.append("")
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\n")
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if len(total) <= 4 and mark_spacing: lines.append("")
                if not (len(total) <= 4 and mark_spacing): lines.append("")
            
            lines.extend(["", "<DESCRIPTION>", ""])
            p_c = (None, None)
            for _, r in desc_df.iterrows():
                c_c = (r['컨테이너 번호'], r['Seal#1'])
                if c_c != p_c:
                    if p_c[0] is not None: lines.extend(["", ""])
                    lines.extend([f"{c_c[0]} / {c_c[1]}", ""])
                    p_c = c_c
                h_no_val = str(r['House B/L No']).strip()
                lines.append(h_no_val)
                lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
                if h_no_val in item_dict:
                    info = item_dict[h_no_val]
                    if info["desc"] and info["desc"].lower() != "nan": lines.append(info["desc"])
                    if info["hs"] and info["hs"].lower() != "nan": lines.append(info["hs"])
                lines.append("")
            
            result_txt = "\n".join(lines)
            with col_res:
                st.subheader("정리 결과")
                st.download_button("💾 메모장 다운로드", result_txt, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result_txt, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"SR 로직 오류: {e}")

# --- TAB 2: MBL 검수 (원본 로직 복구) ---
with tab_mbl:
    col1, col2 = st.columns(2)
    with col1:
        input_mode = st.radio("1. 메모장 정보 입력 방식 선택", ["복사 붙여넣기", "파일 업로드"], horizontal=True)
        memo_content = ""
        if input_mode == "복사 붙여넣기":
            memo_content = st.text_area("메모장 내용을 붙여넣으세요.", height=250)
        else:
            m_file = st.file_uploader("메모장 파일 업로드 (.txt)", type=["txt"], key="m_up")
            if m_file: memo_content = m_file.read().decode("utf-8")
    with col2:
        draft_pdf = st.file_uploader("2. 선사 DRAFT BL 업로드 (.pdf)", type=["pdf"], key="d_up")
        if memo_content and draft_pdf:
            try:
                sr = parse_sr_txt(memo_content)
                with pdfplumber.open(draft_pdf) as pdf:
                    full_text = " ".join([p.extract_text().upper() for p in pdf.pages])
                errors = []
                if str(sr["total_pkg"]) not in full_text: errors.append(f"❌ 총 수량 불일치: {sr['total_pkg']} PKGS")
                if sr["total_wgt"] not in full_text: errors.append(f"❌ 총 중량 불일치: {sr['total_wgt']} KGS")
                if sr["total_msr"] not in full_text: errors.append(f"❌ 총 부피 불일치: {sr['total_msr']} CBM")
                for c in set(sr["containers"]):
                    if c.upper() not in full_text: errors.append(f"❌ 컨테이너 번호 누락/오류: {c}")
                for s in set(sr["seals"]):
                    if s and s.upper() not in full_text: errors.append(f"❌ Seal 번호 누락/오류: {s}")
                for item in sr["hbl_list"]:
                    h_no = item["hbl"]
                    if h_no not in full_text: errors.append(f"❌ B/L 번호 찾을 수 없음: {h_no}"); continue
                    if item["wgt"] not in full_text: errors.append(f"❌ 중량 불일치 (HBL: {h_no}): {item['wgt']} KGS")
                    if item["msr"] not in full_text: errors.append(f"❌ 부피 불일치 (HBL: {h_no}): {item['msr']} CBM (확인 요망)")
                    if item["hs"] and item["hs"] not in full_text: errors.append(f"❌ HS CODE 불일치 (HBL: {h_no}): {item['hs']}")
                st.markdown("---")
                if not errors: st.success("✅ 불일치 항목 없음 (데이터 일치)")
                else:
                    st.warning(f"⚠️ 총 {len(errors)}건의 불일치 발견")
                    err_html = "".join([f"<li style='font-size:14px; margin-bottom:2px;'>{e}</li>" for e in errors])
                    st.markdown(f"<ul style='list-style-type:none; padding-left:0;'>{err_html}</ul>", unsafe_allow_html=True)
            except Exception as e: st.error(f"검수 오류: {e}")

# --- TAB 3: CEVA(LEH) (열 2줄 좌우 배치 및 데이터 정밀 교정) ---
with tab_ceva:
    if "ceva_authenticated" not in st.session_state:
        st.session_state.ceva_authenticated = False
    if not st.session_state.ceva_authenticated:
        pw_c = st.text_input("CEVA Passcode", type="password", key="ceva_pw")
        if st.button("인증"):
            if pw_c == "1234": st.session_state.ceva_authenticated = True; st.rerun()
    else:
        cf = st.file_uploader("CEVA SR 엑셀 업로드", type=["xlsx"], key="cf")
        if cf:
            try:
                log_uploaded_filename(cf.name, "CEVA")
                cdf = pd.read_excel(cf, header=None)
                m_list, d_list = [], []
                # I열 기준 자동 확장 탐색
                for r in range(35, len(cdf)):
                    pkg_raw = cdf.iloc[r, 8] # I열
                    if pd.notna(pkg_raw) and isinstance(pkg_raw, (int, float)):
                        p, w = format_number(pkg_raw), format_number(cdf.iloc[r+1, 8])
                        h = str(cdf.iloc[r+3, 4]).replace("HC:", "").replace("HS:", "").strip() if pd.notna(cdf.iloc[r+3, 4]) else ""
                        m = str(cdf.iloc[r+1, 16]).strip() if pd.notna(cdf.iloc[r+1, 16]) else ""
                        d = str(cdf.iloc[r+1, 34]).strip() if pd.notna(cdf.iloc[r+1, 34]) else ""
                        if p != "0" and d != "nan":
                            m_list.append(f"{m}\n\n\n\n")
                            d_list.append(f"{d}\n\nBK# {m if 'LEH' in m else ''}\n{p} PKGS / {w} KGS /  CBM\nHC: {h}\n\n\n\n")
                cl, cr = st.columns(2)
                with cl:
                    st.subheader("MARK")
                    st.text_area("CEVA_M", "".join(m_list), height=650, label_visibility="collapsed")
                with cr:
                    st.subheader("DESCRIPTION")
                    st.text_area("CEVA_D", "".join(d_list), height=650, label_visibility="collapsed")
            except Exception as e: st.error(f"CEVA 오류: {e}")

# --- TAB 4: 업로드 기록 ---
with tab_log:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)
