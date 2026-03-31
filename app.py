import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 1. 숫자 및 단위 정리 함수 (카고3 동일) ---
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

# --- 2. 업로드 기록 저장 함수 ---
def log_uploaded_filename(fn, category="SR"):
    p = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] ({category}) {fn}\n"
    with open(p, "a", encoding='utf-8') as f: f.write(entry)

# --- 3. 안전한 숫자 변환 함수 (text_input 대응) ---
def safe_float(val):
    try:
        return float(val.replace(',', ''))
    except:
        return 0.0

# --- 4. 페이지 설정 및 디자인(CSS) ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")

st.markdown("""
    <style>
    /* 결과 박스 스타일 (세로형 강조) */
    .result-box-v {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        border: 2px solid #e9ecef;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .result-title-v {
        font-size: 15px;
        color: #6c757d;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .result-value-v {
        font-size: 40px;
        font-weight: 800;
        color: #007bff;
    }
    .surcharge-box {
        background-color: #fff4f4;
        border-color: #ffcccc;
    }
    .surcharge-value {
        color: #d9534f;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🚢 Europe Docs tool")

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "CBM & 서차지 계산"])

# --- TAB 1 & 2: 기존 기능 유지 ---
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

# --- TAB 3: CBM & 서차지 계산 (카고4 세로형 최종 보정) ---
with tab3:
    # 1. CBM 계산 섹션
    st.subheader("📏 CBM 계산기")
    st.caption("$CBM = \\text{가로(m)} \\times \\text{세로(m)} \\times \\text{높이(m)}$")
    
    # 세로형 입력을 위해 2줄로 배치
    c_row1_1, c_row1_2, c_row1_3 = st.columns(3)
    with c_row1_1: h_raw = st.text_input("높이(H) cm", value="0", key="v_h")
    with c_row1_2: w_raw = st.text_input("가로(W) cm", value="0", key="v_w")
    with c_row1_3: l_raw = st.text_input("세로(L) cm", value="0", key="v_l")
    
    c_row2_1, c_row2_2 = st.columns(2)
    with c_row2_1: q_raw = st.text_input("수량(Qty)", value="1", key="v_q")
    with c_row2_2: w_kg_raw = st.text_input("총 중량(kg)", value="0", key="v_weight")

    # 수치 계산
    h_m, w_m, l_m = safe_float(h_raw)/100, safe_float(w_raw)/100, safe_float(l_raw)/100
    qty_val = safe_float(q_raw)
    total_cbm = h_m * w_m * l_m * qty_val

    # CBM 결과 (큼직하게 단독 배치)
    st.markdown(f'''
        <div class="result-box-v">
            <div class="result-title-v">총 CBM</div>
            <div class="result-value-v">{format_number(total_cbm)}</div>
        </div>
    ''', unsafe_allow_html=True)

    st.divider()
    
    # 2. 2단금지 서차지 섹션 (체크박스 제어)
    st.subheader("💰 서차지 계산")
    is_stack_forbidden = st.checkbox("2단적재 금지(Non-Stackable) 서차지 계산하기")
    
    if is_stack_forbidden:
        st.caption("$\\# \\text{계산식: } (2.5 - \\text{높이}) \\times \\text{가로} \\times \\text{세로} \\times \\text{운임} \\times \\text{수량}$")
        
        # 운임 입력
        ocean_rate_raw = st.text_input("운임($)", value="0", key="v_rate")
        
        # 계산 로직
        stack_sc_usd = (2.5 - h_m) * w_m * l_m * qty_val * safe_float(ocean_rate_raw) if h_m > 0 else 0

        # 서차지 결과 (붉은 계열로 강조)
        st.markdown(f'''
            <div class="result-box-v surcharge-box">
                <div class="result-title-v">2단금지 서차지 금액 (USD)</div>
                <div class="result-value-v surcharge-value">$ {stack_sc_usd:,.2f}</div>
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.info("2단금지 서차지 계산이 필요하면 위 체크박스를 선택해주세요.")

    st.divider()
    
    # 3. 업무 참고 메모 (기존 스타일 유지)
    st.warning("""
    **💡 업무 참고 메모**
    * 서차지 높은 거 같으면 깎아줘도 됨. 높이 1.8m 부턴 상단에 박스만 적재 가능해서 웨이브 해주는 편. (너무 마이너스만 아니면 됨)
    """)
