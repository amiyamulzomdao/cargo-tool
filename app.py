# Code Version: 화물4‑rev2 – ‘품목’ 컬럼 대신 2번째 컬럼(AS 등) 자동 감지
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

# expander: 매핑 파일 업로드
extra_map = {}
with st.expander("품목, HS CODE 추가 (선택)", expanded=False):
    hsc_remove = st.checkbox("코스코 HS CODE 점 제거")
    extra_file = st.file_uploader("추가 매핑 파일 업로드", type=["xlsx"], key="extra")
    if extra_file:
        log_uploaded_filename(extra_file.name)
        ex = pd.read_excel(extra_file)
        # 첫 번째 컬럼을 HBL, 두 번째 컬럼을 매핑 텍스트로 사용
        cols = list(ex.columns)
        hbl_col  = cols[0]
        info_col = cols[1] if len(cols)>1 else None

        if info_col is None:
            st.error("추가 파일에 매핑용 컬럼이 없습니다.")
        else:
            for _, row in ex.iterrows():
                hbl = str(row[hbl_col]).strip()
                raw = row[info_col]
                if not hbl or pd.isna(raw):
                    continue
                # 셀 내용이 멀티라인이면 줄별로 분리
                for ln in str(raw).splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    # HS CODE 접두어나 순수 숫자 코드 처리
                    if ln.upper().startswith("HS CODE"):
                        code = ln.split(None,2)[-1]
                        if hsc_remove:
                            code = code.replace('.','')
                        info = f"HS CODE {code}"
                    elif re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", ln):
                        code = ln.replace('.','') if hsc_remove else ln
                        info = f"HS CODE {code}"
                    else:
                        info = ln
                    extra_map.setdefault(hbl, []).append(info)

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
    # DESC
    desc = df.groupby(['컨테이너 번호','Seal#1','House B/L No']).agg(
        포장갯수=('포장갯수','sum'),
        단위=('단위','first'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum'),
    ).reset_index().sort_values(
        ['컨테이너 번호','Seal#1','House B/L No']
    )
    single = (len(total)==1)

# TOTAL summary for all containers
grand_total_pkg = int(df['포장갯수'].sum())
grand_total_w   = format_number(df['Weight'].sum())
grand_total_m   = format_number(df['Measure'].sum())
lines.append(f"TOTAL: {grand_total_pkg} PKGS / {grand_total_w} KGS / {grand_total_m} CBM")
lines.append("")  # 줄 바꿈

    lines = []
    # SUMMARY block
    for _, r in total.iterrows():
        pkg = int(r['포장갯수'])
        w   = format_number(r['Weight'])
        m   = format_number(r['Measure'])
        lines.append(
            f"{r['컨테이너 번호']} / {r['Seal#1']}\n"
            f"TOTAL: {pkg} PKGS / {w} KG / {m} CBM\n"
        )

    # <MARK>
    lines += ["<MARK>", ""]
    for _, r in marks.iterrows():
        if not single:
            lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}"); lines.append("")
        lines += sorted(r['House B/L No']); lines.append("")
    lines.append("")

    # <DESC>
    lines += ["<DESC>", ""]
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
        # extra_map 매핑 정보 삽입
        for info in extra_map.get(hbl, []):
            lines.append(info)
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
