import streamlit as st
import pandas as pd
import os
import re
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
    entry = fn + "\n"
    if os.path.exists(p):
        lines = open(p,"r",encoding='utf-8').readlines()
        if entry in lines: return
        mode='a'
    else:
        mode='w'
    with open(p, mode, encoding='utf-8') as f:
        f.write(entry)

# 페이지 설정
st.set_page_config(
    page_title="🚢 SR 제출 자동 정리기",
    initial_sidebar_state="collapsed"
)

# UI 헤더
st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 컨테이너별로 정리해드려요(칼퇴기원✨)")

force_to_pkg = st.checkbox("코스코 PLT변환")
main_file = st.file_uploader("메인 엑셀 파일 업로드", type=["xlsx"])

# 메인 파일 처리 로직
if main_file:
    log_uploaded_filename(main_file.name)
    df = pd.read_excel(main_file)
    df = df[['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

    # SUMMARY
    total = df.groupby(['컨테이너 번호','Seal#1']).agg(
        포장갯수=('포장갯수','sum'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum')
    ).reset_index()
    
    # MARK
    marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No']\
              .unique().reset_index()
              
    # DESCRIPTION
    desc = df.groupby(['컨테이너 번호','Seal#1','House B/L No']).agg(
        포장갯수=('포장갯수','sum'),
        단위=('단위','first'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum'),
    ).reset_index().sort_values(
        ['컨테이너 번호','Seal#1','House B/L No']
    )
    single = (len(total)==1)

    lines = []
    # SUMMARY block
    for _, r in total.iterrows():
        pkg = int(r['포장갯수'])
        w   = format_number(r['Weight'])
        m   = format_number(r['Measure'])
        lines.append(
            f"{r['컨테이너 번호']} / {r['Seal#1']}\n"
            f"TOTAL: {pkg} PKGS / {w} KGS / {m} CBM\n"
        )

    # <MARK>
    lines += ["<MARK>", ""]
    for _, r in marks.iterrows():
        if not single:
            lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}"); lines.append("")
        lines += sorted(r['House B/L No']); lines.append("")
    lines.append("")

    # <DESCRIPTION>
    lines += ["<DESCRIPTION>", ""]
    prev = (None,None)
    for _, r in desc.iterrows():
        cur = (r['컨테이너 번호'], r['Seal#1'])
        if cur!=prev:
            if prev[0] is not None: lines+=["","",""]
            if not single:
                lines.append(f"{cur[0]} / {cur[1]}"); lines.append("")
            prev = cur

        hbl = r['House B/L No']
        lines.append(hbl)
        lines.append(
            f"{int(r['포장갯수'])} "
            f"{format_unit(r['단위'],r['포장갯수'],force_to_pkg)} / "
            f"{format_number(r['Weight'])} KGS / "
            f"{format_number(r['Measure'])} CBM"
        )
        # 매핑 정보 삭제로 인해 extra_map 관련 반복문 제거됨
        lines.append("")

    result = "\n".join(lines)
    st.text_area("📋 결과 출력:", result, height=600)
    st.download_button(
        "결과 텍스트 다운로드",
        result,
        file_name=f"{os.path.splitext(main_file.name)[0]}.txt"
    )

# Sidebar: Log button
if st.sidebar.button("Log"):
    if os.path.exists("upload_log.txt"):
        logs = open("upload_log.txt","r",encoding='utf-8').read()
        st.sidebar.text_area("Log", logs, height=300)
    else:
        st.sidebar.warning("Log가 아직 없습니다.")