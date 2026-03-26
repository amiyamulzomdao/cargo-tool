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

# --- 날짜 및 문구 가공 함수 ---
def clean_date(val):
    if pd.isna(val) or val == "": return ""
    try:
        if isinstance(val, (datetime, pd.Timestamp)):
            return val.strftime("%d-%b-%Y")
        dt = pd.to_datetime(val)
        return dt.strftime("%d-%b-%Y")
    except:
        return str(val)

def clean_rating_date(val):
    if pd.isna(val): return ""
    v_str = str(val)
    if "outport shipment based on actual deoarture" in v_str.lower():
        return "ETD of proforma schedule"
    return v_str

# --- 표 스타일링 (안전한 인덱스 참조 방식) ---
def style_tariff(row):
    # 선사별 색상 매핑
    colors = {
        'CMA': 'background-color: #E3F2FD',
        'ONE': 'background-color: #FCE4EC',
        'HMM': 'background-color: #F3E5F5',
        'MSK': 'background-color: #E8F5E9',
        'MSC': 'background-color: #FFF3E0',
        'HPL': 'background-color: #F1F8E9'
    }
    # 강조할 열 리스트
    yellow_cols = ['START DATE', 'Validity', "20'gp", "40'gp", "40'HQ"]
    
    # 선사 색상 결정 (안전하게 get 사용)
    carrier_val = str(row.get('Carrier', '')).upper()[:3]
    base_style = colors.get(carrier_val, '')
    
    styles = []
    for col_name in row.index:
        if col_name in yellow_cols:
            styles.append('background-color: #FFF9C4') # 노란색 강조
        else:
            styles.append(base_style) # 선사별 배경색
    return styles

# --- 페이지 설정 ---
st.set_page_config(page_title="Cargo Master v3", layout="wide")
st.title("Cargo Master v3")

if 'tariff_history' not in st.session_state:
    st.session_state.tariff_history = pd.DataFrame()

# 탭 이름 정리
tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

# --- TAB 1: SR 정정 ---
with tab1:
    main_file = st.file_uploader("SR 엑셀 파일 업로드", type=["xlsx"], key="sr_upload")
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

# --- TAB 3: 로이타리프 ---
with tab3:
    st.subheader("📊 Loy Tariff - 운임 추적기")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1: st.text_input("POL 고정", value="BUSAN", disabled=True)
    with col_t2:
        pods = sorted(["Hamburg", "Rotterdam", "Antwerp", "Le Havre", "Barcelona", "Valencia", "FOS", "Genoa", "Koper", "Istanbul", "Izmit", "Southampton", "Aarhus", "Constanta", "Gdansk", "Budapest"])
        sel_pod = st.selectbox("POD 선택", ["전체"] + pods)
    
    t_file = st.file_uploader("타리프 엑셀 업로드", type=["xlsx"], key="tariff_upload")
    
    if t_file:
        try:
            log_uploaded_filename(t_file.name, "Tariff")
            # FAK 시트 고정 읽기
            df_t = pd.read_excel(t_file, sheet_name='FAK', header=4)
            
            # 정확한 열 추출 (인덱스: B=1, C=2, F=5, I=8, J=9, K=10, L=11, M=12, N=13, Q=16)
            target_idx = [1, 2, 5, 8, 9, 10, 11, 12, 13, 16] 
            extracted = df_t.iloc[:, target_idx].copy()
            extracted.columns = ['POL', 'POD', 'Carrier', 'START DATE', 'Validity', 'Carrier\nRating date', "20'gp", "40'gp", "40'HQ", "Surcharge"]
            
            # 부산 필터링
            extracted = extracted[extracted['POL'].fillna('').astype(str).str.contains("BUSAN", case=False)]
            
            # 데이터 가공
            extracted['START DATE'] = extracted['START DATE'].apply(clean_date)
            extracted['Validity'] = extracted['Validity'].apply(clean_date)
            extracted['Carrier\nRating date'] = extracted['Carrier\nRating date'].apply(clean_rating_date)
            
            for col in ["20'gp", "40'gp", "40'HQ"]:
                extracted[col] = extracted[col].apply(lambda x: f"USD {int(float(x))}" if pd.notna(x) and str(x).replace('.','').replace(',','').isdigit() else x)
            
            extracted['Surcharge'] = extracted['Surcharge'].astype(str).str.replace('EFS', '\nEFS', regex=False)
            extracted['파일명'] = t_file.name

            # 누적
            st.session_state.tariff_history = pd.concat([extracted, st.session_state.tariff_history]).drop_duplicates()

        except Exception as e:
            st.error(f"데이터 처리 오류: {e}")

    if not st.session_state.tariff_history.empty:
        carriers = sorted(st.session_state.tariff_history['Carrier'].dropna().unique())
        with col_t3: sel_carrier = st.selectbox("Carrier 선택", ["전체"] + list(carriers))

        res_df = st.session_state.tariff_history.copy()
        if sel_pod != "전체": res_df = res_df[res_df['POD'].astype(str).str.contains(sel_pod, na=False)]
        if sel_carrier != "전체": res_df = res_df[res_df['Carrier'] == sel_carrier]

        st.write("---")
        # 데이터가 존재할 때만 스타일 적용
        if not res_df.empty:
            # 안전하게 데이터프레임을 초기화하여 스타일 적용 (KeyError 방지)
            styled_df = res_df.reset_index(drop=True).style.apply(style_tariff, axis=1)
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.info("조건에 맞는 데이터가 없습니다.")
        
        if st.button("기록 초기화"):
            st.session_state.tariff_history = pd.DataFrame()
            st.rerun()
