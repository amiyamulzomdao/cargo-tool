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

# --- 표 색상 강조 함수 ---
def highlight_tariff(s):
    # 강조할 열 리스트 (헤더 이름 기준)
    yellow_cols = ['S/DATE', 'VALIDITY', '20GP', '40GP', '40HC']
    return ['background-color: #FFF9C4' if s.name in yellow_cols else '' for _ in s]

# --- 페이지 설정 ---
st.set_page_config(page_title="Cargo Master v3", layout="wide")
st.title("Cargo Master v3")

# 세션 상태 초기화 (누적 데이터 보관용)
if 'tariff_history' not in st.session_state:
    st.session_state.tariff_history = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

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
            log_uploaded_filename(main_file.name, "SR")
            df = pd.read_excel(main_file)
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
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
                st.text_area("결과", result, height=600, label_visibility="collapsed")
        except Exception as e: st.error(f"오류 발생: {e}")

# --- TAB 2: 업로드 기록 ---
with tab2:
    st.subheader("📁 통합 업로드 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("로그 데이터", f.read(), height=500)
        if st.button("로그 비우기"):
            os.remove("upload_log.txt")
            st.rerun()
    else: st.info("기록이 없습니다.")

# --- TAB 3: 로이타리프 ---
with tab3:
    st.subheader("📊 Loy Tariff - 운임 추적기")
    
    # 설정 레이아웃
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1: st.text_input("POL 고정", value="BUSAN", disabled=True)
    with col_t2:
        pods = sorted(["Hamburg", "Rotterdam", "Antwerp", "Le Havre", "Barcelona", "Valencia", "FOS", "Genoa", "Koper", "Istanbul", "Izmit", "Southampton", "Aarhus", "Constanta", "Gdansk", "Budapest"])
        sel_pod = st.selectbox("POD 선택", ["전체"] + pods)
    
    t_file = st.file_uploader("타리프 엑셀 업로드 (자동 누적)", type=["xlsx"], key="tariff_upload")
    
    if t_file:
        try:
            log_uploaded_filename(t_file.name, "Tariff")
            # ECU FAK 시트 기준, 5번 행(index 4)이 헤더
            raw_data = pd.read_excel(t_file, sheet_name='FAK', header=4)
            
            # 정확한 열 인덱스 추출: B(1), C(2), F(5), H(7)~U(20)
            target_idx = [1, 2, 5] + list(range(7, 21))
            extracted = raw_data.iloc[:, target_idx].copy()
            
            # 헤더 명칭 정리
            new_headers = ['POL', 'POD', 'CARRIER', 'CONTRACT', 'S/DATE', 'VALIDITY', 'DEPARTURE', '20GP', '40GP', '40HC', '45HC', '40NOR', 'ETS/EFS', 'PAYMENT', 'FREE TIME', 'REMARK', 'OWS']
            extracted.columns = new_headers
            
            # 1. POL 부산 필터링
            extracted = extracted[extracted['POL'].fillna('').astype(str).str.contains("BUSAN", case=False)]
            
            # 2. 운임 숫자 뒤에 USD 추가
            fare_cols = ['20GP', '40GP', '40HC', '45HC', '40NOR']
            for col in fare_cols:
                extracted[col] = extracted[col].apply(lambda x: f"{x} USD" if pd.notna(x) and str(x).replace('.','').replace(',','').isdigit() else x)

            # 파일명 및 시간 추가
            extracted['파일명'] = t_file.name
            extracted['확인일시'] = datetime.now().strftime("%m-%d %H:%M")

            # 자동 누적 (최신 데이터를 위로)
            st.session_state.tariff_history = pd.concat([extracted, st.session_state.tariff_history]).drop_duplicates(subset=['POD','CARRIER','S/DATE','파일명'], keep='first')

        except Exception as e:
            st.error(f"파일 처리 오류: {e}. 'FAK' 시트가 있는지 확인해 주세요.")

    # 결과 출력
    if not st.session_state.tariff_history.empty:
        all_carriers = sorted(st.session_state.tariff_history['CARRIER'].dropna().unique().astype(str))
        with col_t3:
            sel_carrier = st.selectbox("CARRIER 선택", ["전체"] + all_carriers)

        display_df = st.session_state.tariff_history.copy()
        if sel_pod != "전체":
            display_df = display_df[display_df['POD'].astype(str).str.contains(sel_pod, case=False, na=False)]
        if sel_carrier != "전체":
            display_df = display_df[display_df['CARRIER'] == sel_carrier]

        st.write("---")
        st.write(f"### 📋 운임 비교 리스트 (노란색: 주요 운임 정보)")
        
        # 스타일 적용 (노란색 하이라이트)
        st.dataframe(display_df.style.apply(highlight_tariff, axis=0), use_container_width=True)
        
        if st.button("전체 누적 기록 초기화"):
            st.session_state.tariff_history = pd.DataFrame()
            st.rerun()
