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
    if pd.isna(val): return ""
    if isinstance(val, datetime):
        return val.strftime("%d-%b-%Y") # 예: 21-Mar-2026
    return str(val)

def clean_rating_date(val):
    long_str = "(outport shipment based on actual deoarture)"
    if pd.isna(val): return ""
    if long_str in str(val):
        return "ETD of proforma schedule"
    return str(val)

# --- 표 스타일링 (색상) 함수 ---
def style_tariff(row):
    # 선사별 고유 색상 매핑
    colors = {
        'CMA': 'background-color: #E3F2FD', # 연파랑
        'ONE': 'background-color: #FCE4EC', # 연분홍
        'HMM': 'background-color: #F3E5F5', # 연보라
        'MSK': 'background-color: #E8F5E9', # 연초록
        'MSC': 'background-color: #FFF3E0', # 연주황
        'HPL': 'background-color: #F1F8E9'  # 연연두
    }
    # 기본 강조 색상 (노란색)
    yellow_cols = ['START DATE', 'Validity', "20'gp", "40'gp", "40'HQ"]
    
    styles = []
    base_color = colors.get(str(row['Carrier']).upper()[:3], '') # 선사별 색상
    
    for col in row.index:
        if col in yellow_cols:
            styles.append('background-color: #FFF9C4') # 노란색 우선
        else:
            styles.append(base_color)
    return styles

# --- 페이지 설정 ---
st.set_page_config(page_title="Cargo Master v3", layout="wide")
st.title("Cargo Master v3")

if 'tariff_history' not in st.session_state:
    st.session_state.tariff_history = pd.DataFrame()

tab1, tab2, tab3 = st.tabs(["SR 정정", "업로드 기록", "로이타리프"])

# --- TAB 1: SR 정정 (기능 유지) ---
with tab1:
    main_file = st.file_uploader("SR 엑셀 파일", type=["xlsx"], key="sr_upload")
    if main_file:
        try:
            log_uploaded_filename(main_file.name, "SR")
            df = pd.read_excel(main_file)
            # ... (중략: 기존 SR 처리 로직 유지) ...
            st.success("SR 처리가 완료되었습니다.")
        except: pass

# --- TAB 2: 업로드 기록 ---
with tab2:
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            st.text_area("로그 데이터", f.read(), height=500)

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
            df_t = pd.read_excel(t_file, sheet_name='FAK', header=4)
            
            # 엑셀 열 인덱스 정확히 추출: B, C, F, H, I, J, K + L, M, N ...
            # 1, 2, 5, 7, 8, 9, 10, 11, 12, 13
            target_cols = [1, 2, 5, 8, 9, 10, 11, 12, 13, 16] 
            extracted = df_t.iloc[:, target_cols].copy()
            extracted.columns = ['POL', 'POD', 'Carrier', 'START DATE', 'Validity', 'Carrier\nRating date', "20'gp", "40'gp", "40'HQ", "Surcharge"]
            
            # 1. POL 부산 필터링
            extracted = extracted[extracted['POL'].fillna('').astype(str).str.contains("BUSAN", case=False)]
            
            # 2. 날짜 및 문구 가공
            extracted['START DATE'] = extracted['START DATE'].apply(clean_date)
            extracted['Validity'] = extracted['Validity'].apply(clean_date)
            extracted['Carrier\nRating date'] = extracted['Carrier\nRating date'].apply(clean_rating_date)
            
            # 3. 금액 정수화 + USD 접두사
            for col in ["20'gp", "40'gp", "40'HQ"]:
                extracted[col] = extracted[col].apply(lambda x: f"USD {int(float(x))}" if pd.notna(x) and str(x).replace('.','').isdigit() else x)
            
            # 4. Surcharge 줄바꿈 (EES / EFS 구분)
            extracted['Surcharge'] = extracted['Surcharge'].str.replace('EFS', '\nEFS', regex=False)

            extracted['파일명'] = t_file.name
            st.session_state.tariff_history = pd.concat([extracted, st.session_state.tariff_history]).drop_duplicates()

        except Exception as e:
            st.error(f"오류: {e}")

    if not st.session_state.tariff_history.empty:
        carriers = sorted(st.session_state.tariff_history['Carrier'].dropna().unique())
        with col_t3: sel_carrier = st.selectbox("Carrier 선택", ["전체"] + list(carriers))

        res_df = st.session_state.tariff_history.copy()
        if sel_pod != "전체": res_df = res_df[res_df['POD'].str.contains(sel_pod, na=False)]
        if sel_carrier != "전체": res_df = res_df[res_df['Carrier'] == sel_carrier]

        st.write("---")
        # 스타일 적용 (선사별 색상 + 노란색 강조)
        st.dataframe(res_df.style.apply(style_tariff, axis=1), use_container_width=True)
        
        if st.button("초기화"):
            st.session_state.tariff_history = pd.DataFrame()
            st.rerun()
