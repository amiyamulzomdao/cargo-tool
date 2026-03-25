import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    m = {'PK':'PKG','PL':'PLT','CT':'CTN'}
    base = 'PKG' if (force_to_pkg and unit.upper()=='PL') else m.get(unit.upper(), unit.upper())
    return base+'S' if unit.upper() in ['PK','PL','CT'] and count>1 else base

def format_number(v):
    t = f"{round(v,3):.3f}"
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn):
    p = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# 페이지 설정
st.set_page_config(page_title="🚢 SR 자동 정리기", layout="wide")

st.title("🚢 SR 제출 자동 정리기")
st.info("엑셀 파일을 업로드하면 컨테이너별로 정리해드려요. (칼퇴 기원 ✨)")

# 메인 화면을 두 개의 탭으로 분리
tab1, tab2 = st.tabs(["🚀 작업 도구", "📜 업로드 기록"])

with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("설정 및 업로드")
        force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환")
        main_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

    with col2:
        if main_file:
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            df = df[['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']].copy()
            
            # 오류 수정된 부분: .str.split() 으로 변경
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

            # 데이터 계산
            total = df.groupby(['컨테이너 번호','Seal#1']).agg(
                포장갯수=('포장갯수','sum'),
                Weight=('Weight','sum'),
                Measure=('Measure','sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
            desc = df.sort_values(['컨테이너 번호','Seal#1','House B/L No'])
            
            lines = []

            # --- [GRAND TOTAL] 추가 (컨테이너 2대 이상일 때) ---
            if len(total) >= 2:
                g_pkg = int(total['포장갯수'].sum())
                g_w = format_number(total['Weight'].sum())
                g_m = format_number(total['Measure'].sum())
                lines.append("[GRAND TOTAL]")
                lines.append(f"TOTAL: {g_pkg} PKGS / {g_w} KGS / {g_m} CBM")
                lines.append("-" * 30)
                lines.append("")

            # SUMMARY block
            for _, r in total.iterrows():
                pkg = int(r['포장갯수'])
                w = format_number(r['Weight'])
                m = format_number(r['Measure'])
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {pkg} PKGS / {w} KGS / {m} CBM\n")

            lines += ["<MARK>", ""]
            single = (len(total) == 1)
            for _, r in marks.iterrows():
                if not single:
                    lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines += sorted(r['House B/L No'])
                lines.append("")
            lines.append("")

            lines += ["<DESCRIPTION>", ""]
            prev = (None, None)
            for _, r in desc.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None: lines += ["", ""]
                    if not single:
                        lines.append(f"{cur[0]} / {cur[1]}")
                        lines.append("")
                    prev = cur

                lines.append(r['House B