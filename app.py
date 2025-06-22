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
    if unit.upper() in ['PK', 'PL', 'CT'] and count > 1:
        return base + 'S'
    return base


def format_number(value):
    value = round(value, 3)
    text = f"{value:.3f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def log_uploaded_filename(file_name):
    log_path = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"{now} - {file_name}\n"
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_entry)
    else:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if log_entry not in lines:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)

st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 컨테이너별 마크 및 디스크립션을 정리해드립니다.")
force_to_pkg = st.checkbox("코스코 PLT변환")
uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

if uploaded_file:
    log_uploaded_filename(uploaded_file.name)
    df = pd.read_excel(uploaded_file)
    df = df[['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

    # Aggregations
    total_summary = df.groupby(['컨테이너 번호','Seal#1']).agg({'포장갯수':'sum','Weight':'sum','Measure':'sum'}).reset_index()
    marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
    desc = df.groupby(['컨테이너 번호','Seal#1','House B/L No']).agg({'포장갯수':'sum','단위':'first','Weight':'sum','Measure':'sum'}).reset_index().sort_values(['컨테이너 번호','Seal#1','House B/L No'])

    is_single = len(total_summary) == 1

    # SUMMARY
    summary_lines = []
    for _, r in total_summary.iterrows():
        pkg = int(r['포장갯수'])
        w = format_number(r['Weight'])
        m = format_number(r['Measure'])
        summary_lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\nTOTAL: {pkg} PKGS / {w} KG / {m} CBM\n")

    # MARK
    mark_lines = ["<MARK>", ""]
    for _, r in marks.iterrows():
        if not is_single:
            mark_lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
            mark_lines.append("")
        mark_lines.extend(sorted(r['House B/L No']))
        mark_lines.append("")
    mark_lines.append("")  # end of MARK

    # DESC
    desc_lines = ["<DESC>", ""]
    prev = (None, None)
    for _, r in desc.iterrows():
        cur = (r['컨테이너 번호'], r['Seal#1'])
        if cur != prev:
            if prev[0] is not None:
                desc_lines.extend(["","",""])
            desc_lines.append(f"{cur[0]} / {cur[1]}")
            desc_lines.append("")
            prev = cur
        desc_lines.append(r['House B/L No'])
        desc_lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'], r['포장갯수'], force_to_pkg)} / {format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
        desc_lines.append("")

    # Combine
    result_text = "\n".join(summary_lines + [""] + mark_lines + ["", ""] + desc_lines)

    # 🔸 Color background for 0 CBM
    html_lines = []
    for line in result_text.split("\n"):
        if ' 0 CBM' in line:
            html_lines.append(f"<div style='background-color: #ffdddd'>{line}</div>")
        else:
            html_lines.append(f"<div>{line}</div>")
    html = "<br>".join(html_lines)
    st.markdown(html, unsafe_allow_html=True)

    # Download
    st.download_button("결과 텍스트 다운로드", result_text, file_name=os.path.splitext(uploaded_file.name)[0]+".txt")

if st.sidebar.button("📁 업로드 로그 보기"):
    if os.path.exists("upload_log.txt"):
        st.sidebar.text_area("업로드 로그", open("upload_log.txt","r",encoding="utf-8").read(), height=300)
    else:
        st.sidebar.warning("업로드 로그가 아직 없습니다.")
