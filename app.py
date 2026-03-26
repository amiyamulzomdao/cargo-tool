import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 유틸리티 함수 ---
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

# --- 페이지 설정 ---
st.set_page_config(page_title="Cargo Master v3", layout="wide")
st.title("Cargo Master v3")

# 세션 상태 초기화
if 'tariff_history' not in st.session_state:
    st.session_state.tariff_history = pd.DataFrame()

# 탭 순서 변경: SR 정정 -> 업로드 기록 -> 로이타리프
tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프 (실험중)"])

# --- TAB 1: SR 정정 ---
with tab1:
    main_file = st.file_uploader("SR 엑셀 파일을 업로드하세요", type=["xlsx"], key="sr_upload")
    if main_file:
        col_in, col_res = st.columns([1, 1.5])
        with col_in:
            st.subheader("설정 및 정보")
            force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환")
            st.info(f"파일: {main_file.name}")
        try:
            log_uploaded_filename(main_file.name, "SR") # SR 기록
            df = pd.read_excel(main_file)
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            has_gt = df['단위'].fillna('').astype(str).str.upper().str.contains('GT').any()
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
                lines.extend(["[GRAND TOTAL]", total_line, "-" * (len(total_line) + 10), ""])
            
            for _, r in total.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {int(r['포장갯수'])} PKGS / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM\n")
            
            lines.append("<MARK>\n")
            for _, r in marks.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\n")
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single: lines.append("")
                lines.append("")
            
            lines.extend(["<DESCRIPTION>", ""])
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines.extend(["", ""])
                    if not single: lines.extend([f"{cur[0]} / {cur[1]}", ""])
                    prev = cur
                u_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                lines.extend([f"{r['House B/L No']}", f"{int(r['포장갯수'])} {u_val} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM", ""])
            
            result = "\n".join(lines)
            with col_res:
                c1, c2 = st.columns([2, 1])
                c1.subheader("정리 결과")
                c2.download_button("💾 메모장 다운로드", result, f"SR_{main_file.name.split('.')[0]}.txt", use_container_width=True)
                if has_gt: st.error("⚠️ *GT 단위가 있습니다. 데이터 확인이 필요합니다.*")
                st.text_area("결과", result, height=600, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")
    else: st.write("")

# --- TAB 2: 업로드 기록 ---
with tab2:
    st.subheader("📁 통합 업로드 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            log_data = f.read()
        st.text_area("로그 데이터 (SR 및 타리프)", log_data, height=500)
        if st.button("로그 기록 비우기"):
            os.remove("upload_log.txt")
            st.rerun()
    else:
        st.info("아직 기록된 업로드 이력이 없습니다.")

# --- TAB 3: 로이타리프 (실험중) ---
with tab3:
    st.subheader("📊 Loy Tariff - 운임 추적기 (실험중)")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1: st.text_input("POL (B5)", value="BUSAN", disabled=True)
    with col_t2:
        pods = ["Hamburg", "Rotterdam", "Antwerp", "Le Havre", "Barcelona", "Valencia", "FOS", "Genoa", "Koper", "Istanbul", "Izmit", "Southampton", "Aarhus", "Constanta", "Gdansk", "Budapest"]
        sel_pod = st.selectbox("POD 선택 (C5)", ["전체"] + pods)
    with col_t3:
        sel_carrier = st.text_input("CARRIER 검색 (F5)", placeholder="선사명 입력")

    t_file = st.file_uploader("타리프 엑셀 파일을 업로드하세요", type=["xlsx"], key="tariff_upload")
    
    if t_file:
        try:
            log_uploaded_filename(t_file.name, "Tariff") # 타리프 기록 추가
            df_t = pd.read_excel(t_file, header=4)
            # 데이터 추출 (B, C, F 열 및 H~U 열)
            selected_cols = df_t.iloc[:, [1, 2, 5] + list(range(7, 21))] 
            selected_cols.columns = ['POL', 'POD', 'CARRIER'] + list(df_t.columns[7:21])
            
            filtered_df = selected_cols.copy()
            if sel_pod != "전체":
                filtered_df = filtered_df[filtered_df['POD'].astype(str).str.contains(sel_pod, case=False, na=False)]
            if sel_carrier:
                filtered_df = filtered_df[filtered_df['CARRIER'].astype(str).str.contains(sel_carrier, case=False, na=False)]
            
            filtered_df['업로드일시'] = datetime.now().strftime("%m-%d %H:%M")
            filtered_df['파일명'] = t_file.name

            if st.button("현재 데이터 누적하기"):
                st.session_state.tariff_history = pd.concat([filtered_df, st.session_state.tariff_history]).drop_duplicates()
                st.success("운임 데이터가 누적되었습니다!")

            st.write("### 🔍 필터링 결과")
            st.dataframe(filtered_df, use_container_width=True)

        except Exception as e:
            st.error(f"타리프 처리 중 오류 발생: {e}")

    if not st.session_state.tariff_history.empty:
        st.write("---")
        st.write("### 📜 누적 데이터 (비교용)")
        st.dataframe(st.session_state.tariff_history, use_container_width=True)
        if st.button("누적 기록 초기화"):
            st.session_state.tariff_history = pd.DataFrame()
            st.rerun()
