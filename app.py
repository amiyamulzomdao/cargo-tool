# Code Version: SRAuto19 - Extra mapping in collapsed expander
import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    unit_map = {'PK': 'PKG', 'PL': 'PLT', 'CT': 'CTN'}
    if force_to_pkg and unit.upper() == 'PL':
        base = 'PKG'
    else:
        base = unit_map.get(unit.upper(), unit.upper())
    if unit.upper() in ['PK','PL','CT'] and count > 1:
        return base + 'S'
    return base

def format_number(value):
    value = round(value, 3)
    text = f"{value:.3f}"
    return text.rstrip('0').rstrip('.') if '.' in text else text

def log_uploaded_filename(file_name):
    log_path = "upload_log.txt"
    entry = f"{file_name}\n"
    if not os.path.exists(log_path):
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(entry)
    else:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if entry not in lines:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(entry)

# 페이지 설정
st.set_page_config(page_title="🚢 SR 제출 자동 정리기",
                   initial_sidebar_state="collapsed")

# UI
st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 컨테이너별 마크 및 디스크립션을 정리해드립니다.")
force_to_pkg = st.checkbox("코스코 PLT변환")
main_file = st.file_uploader("메인 엑셀 파일 업로드", type=["xlsx"])

# expander for extra mapping
extra_map = {}
with st.expander("품목, HS CODE 추가 (선택)", expanded=False):
    extra_file = st.file_uploader("추가 엑셀 파일 업로드", type=["xlsx"], key="extra")
    if extra_file:
        log_uploaded_filename(extra_file.name)
        ex = pd.read_excel(extra_file, header=None)
        for _, row in ex.iterrows():
            hbl  = str(row[0]).strip()
            info = str(row[1]).strip() if len(row) > 1 else ''
            if hbl and info:
                extra_map[hbl] = info

if main_file:
    log_uploaded_filename(main_file.name)
    df = pd.read_excel(main_file)
    df = df[['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

    total = df.groupby(['컨테이너 번호','Seal#1']).agg(
        포장갯수=('포장갯수','sum'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum')
    ).reset_index()
    marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
    desc  = df.groupby(['컨테이너 번호','Seal#1','House B/L No']).agg(
        포장갯수=('포장갯수','sum'),
        단위=('단위','first'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum')
    ).reset_index().sort_values(['컨테이너 번호','Seal#1','House B/L No'])
    single = (len(total) == 1)

    lines = []
    # SUMMARY
    for _, r in total.iterrows():
        pkg = int(r['포장갯수']); w = format_number(r['Weight']); m = format_number(r['Measure'])
        lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\nTOTAL: {pkg} PKGS / {w} KG / {m} CBM\n")

    # <MARK>
    lines += ["<MARK>", ""]
    for _, r in marks.iterrows():
        if not single:
            lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
            lines.append("")
        lines += sorted(r['House B/L No'])
        lines.append("")
    lines.append("")

    # <DESC>
    lines += ["<DESC>", ""]
    prev = (None, None)
    for _, r in desc.iterrows():
        cur = (r['컨테이너 번호'], r['Seal#1'])
        if cur != prev:
            if prev[0] is not None:
                lines += ["", "", ""]
            if not single:
                lines.append(f"{cur[0]} / {cur[1]}")
                lines.append("")
            prev = cur

        hbl = r['House B/L No']
        lines.append(hbl)
        lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
        if hbl in extra_map:
            lines.append(extra_map[hbl])
        lines.append("")

    result = "\n".join(lines)
    st.text_area("📋 결과 출력:", result, height=600)
    st.download_button("결과 텍스트 다운로드", result,
                       file_name=os.path.splitext(main_file.name)[0] + ".txt")

# Sidebar Log button
if st.sidebar.button("Log"):
    if os.path.exists("upload_log.txt"):
        logs = open("upload_log.txt","r",encoding='utf-8').read()
        st.sidebar.text_area("Log", logs, height=300)
    else:
        st.sidebar.warning("Log가 아직 없습니다.")
