import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 1. 숫자 및 단위 정리 함수 ---
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

# --- 3. 페이지 기본 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

# 탭 구성 (CBM & 서차지 계산 탭 추가)
tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "CBM & 서차지 계산"])

# --- TAB 1: SR 정정 (카고3 기능 유지) ---
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
        col_space, col_res = st.columns([1, 2.5])
        
        try:
            log_uploaded_filename(sr_file.name, "SR")
            sr_df = pd.read_excel(sr_file)
            
            item_dict = {}
            empty_line_bls = [] 
            
            if item_file:
                log_uploaded_filename(item_file.name, "ITEM")
                item_df = pd.read_excel(item_file, header=1)
                item_df.columns = [str(c).strip() for c in item_df.columns]
                
                if "House B/L No" in item_df.columns and "품목" in item_df.columns:
                    for _, row in item_df.iterrows():
                        h_no = str(row["House B/L No"]).strip()
                        desc_full = str(row["품목"]) if pd.notna(row["품목"]) else ""
                        desc_stripped = desc_full.strip() 
                        hs_raw = str(row.get("HS CODE", "")).strip()
                        
                        if h_no and h_no != "nan":
                            item_dict[h_no] = {"desc": desc_full.strip(), "hs": hs_raw}
                            
                            has_inner_empty = False
                            if "\n\n" in desc_stripped:
                                has_inner_empty = True
                            else:
                                lines = desc_stripped.split('\n')
                                for i in range(1, len(lines) - 1):
                                    if lines[i].strip() == "":
                                        has_inner_empty = True
                                        break
                            if has_inner_empty:
                                empty_line_bls.append(h_no)

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
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10)]) 
            
            for _, r in total.iterrows():
                lines.append("") 
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
            
            lines.extend(["", "", "<MARK>", ""]) 
            for _, r in marks.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single and mark_spacing:
                        lines.append("")
                if not (single and mark_spacing):
                    lines.append("") 
            
            lines.extend(["", "<DESCRIPTION>", ""]) 
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""]) 
                    lines.extend([f"{cur[0]} / {cur[1]}", ""])
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
                    bl_list_str = ', '.join(list(set(empty_line_bls)))
                    st.warning(f"📢 **다중 품목 의심 B/L:** {bl_list_str} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
                
                st.download_button("💾 메모장 다운로드", result, f"SR_{sr_file.name.split('.')[0]}.txt")
                st.text_area("결과창", result, height=800, label_visibility="collapsed")
                
        except Exception as e:
            st.error(f"오류 발생: {e}")

# --- TAB 2: 업로드 기록 ---
with tab2:
    st.subheader("파일 업로드 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("Log", f.read(), height=500)

# --- TAB 3: CBM & 서차지 계산 (카고4 실험 탭) ---
with tab3:
    st.subheader("📏 수기 CBM 계산기")
    # 수식 설명 (연하게)
    st.caption("$CBM = \\text{가로(m)} \\times \\text{세로(m)} \\times \\text{높이(m)}$")
    
    calc_col1, calc_col2 = st.columns([2, 1])
    
    with calc_col1:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: h_cm = st.number_input("높이(H) cm", min_value=0.0, step=1.0, key="calc_h")
        with c2: w_cm = st.number_input("가로(W) cm", min_value=0.0, step=1.0, key="calc_w")
        with c3: l_cm = st.number_input("세로(L) cm", min_value=0.0, step=1.0, key="calc_l")
        with c4: qty = st.number_input("수량(Qty)", min_value=1, step=1, key="calc_q")
        with c5: weight_kg = st.number_input("총 중량(kg)", min_value=0.0, step=1.0, key="calc_weight")

        # 미터 변환
        h_m, w_m, l_m = h_cm/100, w_cm/100, l_cm/100
        single_cbm = h_m * w_m * l_m
        total_cbm = single_cbm * qty
        r_ton = max(total_cbm, weight_kg / 1000)

    with calc_col2:
        st.info(f"**결과**\n\n총 CBM: `{format_number(total_cbm)}`  \n적용 R/TON: `{format_number(r_ton)}`")

    st.divider()
    
    st.subheader("💰 서차지(Surcharge) 가계산")
    sc_col1, sc_col2 = st.columns([2, 1])
    
    with sc_col1:
        s1, s2, s3 = st.columns(3)
        with s1: ocean_rate = st.number_input("기본 운임 단가($)", min_value=0.0, step=1.0, value=0.0)
        with s2: other_sc = st.number_input("기타 서차지 합계($)", min_value=0.0, step=1.0, value=0.0)
        with s3: exchange_rate = st.number_input("적용 환율(₩)", min_value=0.0, step=1.0, value=1350.0)
        
        # 2단적재 금지 서차지 계산 (2.5 - 높이) * 가로 * 세로 * 운임
        # 높이가 0이면 계산 제외
        stack_sc_vol = (2.5 - h_m) * w_m * l_m * qty if h_m > 0 else 0
        stack_sc_usd = stack_sc_vol * ocean_rate
        
        total_usd = (r_ton * ocean_rate) + (r_ton * other_sc) + stack_sc_usd
        total_krw = total_usd * exchange_rate
        
        st.write("---")
        st.markdown(f"**[상세 내역]**")
        st.write(f"- 기본 물류비: `${(r_ton * ocean_rate):,.2f}`")
        st.write(f"- 기타 서차지: `${(r_ton * other_sc):,.2f}`")
        # 서차지 공식 설명 (연하게)
        st.write(f"- **2단적재 금지 서차지**: `${stack_sc_usd:,.2f}`")
        st.caption(f"公式: $(2.5 - {h_m:,.2f}m) \\times {w_m:,.2f}m \\times {l_m:,.2f}m \\times \\text{{운임}} \\times {qty}\\text{{개}}$")

    with sc_col2:
        st.metric("최종 예상 비용 (USD)", f"$ {total_usd:,.2f}")
        st.metric("최종 예상 비용 (KRW)", f"₩ {int(total_krw):,}")
        
    st.warning("""
    **💡 업무 참고 메모**
    * 서차지가 너무 높은 것 같으면 적당히 깎아줘도 됨. (너무 마이너스만 아니면 됨)
    * 높이 1.8m부터는 상단에 가벼운 박스류만 적재가 가능해서 웨이브(Wave) 해주는 편.
    """)
