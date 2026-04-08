import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, timezone

# --- 1. 유틸리티 함수 ---
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

# --- 2. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="Europe Docs tool (Cargo 3)", layout="wide")
st.markdown("""
    <style>
    .stTextArea textarea {
        font-family: 'Courier New', Courier, monospace !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚢 Europe Docs tool - Cargo 3")

col_up1, col_up2 = st.columns(2)
with col_up1:
    sr_file = st.file_uploader("1. SR 엑셀 파일 입력", type=["xlsx"])
    force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환", value=False)
    mark_spacing = st.checkbox("MARK 란 간격 띄우기", value=False)
with col_up2:
    item_file = st.file_uploader("2. 하우스리스트 입력", type=["xlsx"])

if sr_file:
    try:
        sr_df = pd.read_excel(sr_file)
        item_dict = {}
        empty_line_bls = [] 

        if item_file:
            item_df = pd.read_excel(item_file, header=1)
            item_df.columns = [str(c).strip() for c in item_df.columns]
            
            # 다중 품목 의심 로직
            hbl_item_counts = item_df.groupby('House B/L No')['품목'].nunique()
            empty_line_bls = hbl_item_counts[hbl_item_counts > 1].index.tolist()

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
        # ... (중략: SR 연산 로직) ...
        
        result = "\n".join(lines)
        st.subheader("정리 결과")
        if empty_line_bls: 
            st.warning(f"📢 **다중 품목 의심 B/L:** {', '.join(map(str, empty_line_bls))} -> 수기로 컨테이너 별 품목을 나눠주세요ㅎㅎ")
        st.text_area("결과창", result, height=800)
    except Exception as e: st.error(f"오류 발생: {e}")
