import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG','PL':'PLT','CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    return base + 'S' if u_str in ['PK','PL','CT'] and count > 1 else base

def format_number(v):
    t = f"{round(v, 3):.3f}"
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn):
    p = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# 페이지 설정
st.set_page_config(page_title="SR 자동 정리기", layout="wide")

st.title("SR 제출 자동 정리기")

tab1, tab2 = st.tabs(["작업 도구", "업로드 기록"])

with tab1:
    main_file = st.file_uploader("엑셀 파일을 업로드하세요 (xlsx)", type=["xlsx"])

    if main_file:
        col_input, col_result = st.columns([1, 1.5])
        
        with col_input:
            st.subheader("설정 및 정보")
            force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환")
            st.info(f"파일: {main_file.name}")
            
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            
            cols = ['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')

            total = df.groupby(['컨테이너 번호','Seal#1']).agg(
                포장갯수=('포장갯수','sum'),
                Weight=('Weight','sum'),
                Measure=('Measure','sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
            desc = df.sort_values(['컨테이너 번호','Seal#1','House B/