import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 1. 유틸리티 함수 (카고3 동일) ---
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

def safe_float(val):
    try:
        return float(str(val).replace(',', ''))
    except:
        return 0.0

# --- 2. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")

st.markdown("""
    <style>
    .result-box-final {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        border: 2px solid #e9ecef;
        margin-top: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .result-title-final {
        font-size: 14px;
        color: #6c757d;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .result-value-final {
        font-size: 32px;
        font-weight: 800;
        color: #007bff;
    }
    .sc-value {
        color: #d9534f;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "CBM & 서차지 계산"])

# --- TAB 1 & 2: 카고3 로직 유지 ---
with tab1:
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"], key="sr_main")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
        mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)
    with col_up2:
        item_file = st.file_uploader("2. 하우스리스트 -> S/R NO 검색 -> 엑셀내려받기 파일 입력(품목명, HS CODE 입력 가능)_선택사항", type=["xlsx"], key="item_sub")
    st.divider()
    if sr_file:
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            item_dict = {}; empty_line_bls = [] 
            if item_file:
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                if "House B/L No" in item_df.columns and "품목" in item_df.columns:
                    for _, row in item_df.iterrows():
                        h_no = str(row["House B/L No"]).strip()
                        desc_full = str(row["품목"]) if pd.notna(row["품목"]) else ""
                        if h_no and h_no != "nan":
                            item_dict[h_no] = {"desc": desc_full.strip(), "hs": str(row.get("HS CODE", "")).strip()}
                            if "\n\n" in desc_full.strip(): empty_line_bls.append(h_no)
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = sr_df[cols].copy().dropna(subset=['House B/L No'])
            gt_bls = df[df['단위'].fillna('').astype(str).str.upper().str.contains('GT')]['House B/L No'].unique().tolist()
            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(포장갯수=('포장갯수','sum'), Weight=('Weight','sum'), Measure=('Measure','sum')).reset_index()
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            lines = []; single = (len(total) == 1)
            if not single:
                g_p = int(total['포장갯수'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {format_number(total['Weight'].sum())} KGS / {format_number(total['Measure'].sum())} CBM"
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10)]) 
            for _, r in total.iterrows():
                lines.append(""); lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
            lines.extend(["", "", "<MARK>", ""]) 
            for _, r in marks.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}"); lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single and mark_spacing: lines.append("")
                if not (single and mark_spacing): lines.append("") 
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
                    if info["desc"]: lines.append(info["desc"])
                    if info["hs"]: lines.append(info["hs"])
                lines.append("")
            result = "\n".join(lines)
            with st.columns([1, 2.5])[1]:
                st.subheader("정리 결과")
                if gt_bls: st.error(f"⚠️ **GT 단위 확인 필요 B/L:** {', '.join(gt_bls)}")
                if empty_line_bls: st.warning(f"📢 **다중 품목 의심 B/L:** {', '.join(list(set(empty_line_bls)))} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f: st.text_area("Log", f.read(), height=500)

# --- TAB 3: CBM & 서차지 계산 (카고4 실험 - 단가 안내 최적화) ---
with tab3:
    if 'boxes' not in st.session_state:
        st.session_state.boxes = [{'h': '0', 'w': '0', 'l': '0', 'q': '1'}]

    left_calc, right_calc = st.columns(2, gap="large")

    with left_calc:
        st.subheader("📏 CBM 계산기")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button("➕ 박스 규격 추가"):
                st.session_state.boxes.append({'h': '0', 'w': '0', 'l': '0', 'q': '1'})
        with b_col2:
            if st.button("➖ 마지막 박스 삭제") and len(st.session_state.boxes) > 1:
                st.session_state.boxes.pop()

        total_sum_cbm = 0.0
        for i, box in enumerate(st.session_state.boxes):
            st.markdown(f"**Box #{i+1}**")
            r1, r2, r3, r4 = st.columns(4)
            with r1: h = st.text_input(f"높이(cm)", value=box['h'], key=f"h_{i}")
            with r2: w = st.text_input(f"가로(cm)", value=box['w'], key=f"w_{i}")
            with r3: l = st.text_input(f"세로(cm)", value=box['l'], key=f"l_{i}")
            with r4: q = st.text_input(f"수량", value=box['q'], key=f"q_{i}")
            
            st.session_state.boxes[i] = {'h': h, 'w': w, 'l': l, 'q': q}
            row_cbm = (safe_float(h)/100) * (safe_float(w)/100) * (safe_float(l)/100) * safe_float(q)
            total_sum_cbm += row_cbm

        st.markdown(f'''
            <div class="result-box-final">
                <div class="result-title-final">전체 합계 부피 (Total CBM)</div>
                <div class="result-value-final">{format_number(total_sum_cbm)}</div>
            </div>
        ''', unsafe_allow_html=True)

    with right_calc:
        st.subheader("💰 서차지 계산")
        # 요청하신 문구로 수정 완료
        is_active = st.checkbox("서차지 계산 활성화 (1PLT 기준)", key="f_active_v4_plt")
        
        if is_active:
            st.caption("$(2.5 - \\text{높이}) \\times \\text{가로} \\times \\text{세로} \\times \\text{운임}$ (1개당 단가)")
            # 첫 번째 박스 규격 기준
            ref_box = st.session_state.boxes[0]
            ref_h = safe_float(ref_box['h']) / 100
            ref_w = safe_float(ref_box['w']) / 100
            ref_l = safe_float(ref_box['l']) / 100
            
            ocean_rate_raw = st.text_input("운임($)", value="0", key="f_rate_v4_plt")
            
            # 1개당 단가 계산 (수량 제외)
            stack_sc_usd = (2.5 - ref_h) * ref_w * ref_l * safe_float(ocean_rate_raw) if ref_h > 0 else 0

            st.markdown(f'''
                <div class="result-box-final">
                    <div class="result-title-final">2단적재 금지 서차지 (USD / 1PLT 단가)</div>
                    <div class="result-value-final sc-value">$ {stack_sc_usd:,.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
            st.info(f"💡 Box #1 규격(H:{ref_box['h']}cm)을 기준으로 산출된 개당 서차지입니다.")
        else:
            st.info("단가 안내가 필요하면 위 체크박스를 선택하세요.")

    st.divider()
    st.warning("""
    **💡 업무 참고 메모**
    * 서차지 높은 거 같으면 깎아줘도 됨. 높이 1.8m 부턴 상단에 박스만 적재 가능해서 웨이브 해주는 편. (너무 마이너스만 아니면 됨)
    """)
