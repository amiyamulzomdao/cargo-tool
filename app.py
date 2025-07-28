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
    if unit.upper() in unit_map and count > 1:
        return base + 'S'
    return base

def format_number(value):
    value = round(value, 3)
    text = f"{value:.3f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text

st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 컨테이너별 마크 및 디스크립션을 정리해드립니다.")

with st.expander("🔧 선택 옵션", expanded=False):
    force_to_pkg = st.checkbox("코스코 PLT 변환", value=False)
    remove_dot_in_hscode = st.checkbox("코스코 HS CODE 점 제거", value=True)

main_file = st.file_uploader("📄 메인 엑셀 파일 업로드", type=["xlsx"], key="main")

extra_file = st.file_uploader("🧾 품목, HS CODE 추가 (선택)", type=["xlsx"], key="extra")

if main_file:
    df = pd.read_excel(main_file)
    df = df[['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

    total_summary = df.groupby(['컨테이너 번호', 'Seal#1']).agg({
        '포장갯수': 'sum',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index()

    marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()

    desc = df.groupby(['컨테이너 번호', 'Seal#1', 'House B/L No']).agg({
        '포장갯수': 'sum',
        '단위': 'first',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index().sort_values(by=['컨테이너 번호', 'Seal#1', 'House B/L No'])

    is_single_container = total_summary.shape[0] == 1

    mapping = {}
    if extra_file:
        extra_df = pd.read_excel(extra_file, dtype=str)
        if extra_df.shape[1] >= 2:
            for i, row in extra_df.iterrows():
                hbl = str(row[0]).strip()
                content = str(row[1]).strip()
                if hbl and content:
                    lines = []
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if "HS CODE" in line.upper():
                            code = ''.join(filter(str.isdigit, line))
                            if remove_dot_in_hscode and len(code) == 6:
                                lines.append(code)
                            elif code:
                                lines.append(code)
                        else:
                            lines.append(line)
                    mapping[hbl] = lines

    summary_lines = []
    for _, row in total_summary.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        pkgs = int(row['포장갯수'])
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])
        summary_lines.append(f"{container} / {seal}\nTOTAL: {pkgs} PKGS / {weight} KG / {measure} CBM\n")

    mark_lines = ["<MARK>", ""]
    for _, row in marks.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbls = row['House B/L No']
        if not is_single_container:
            mark_lines.append(f"{container} / {seal}")
        mark_lines.extend(sorted(hbls))
        mark_lines.append("")

    desc_lines = ["<DESC>", ""]
    prev_container, prev_seal = None, None
    for _, row in desc.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbl = row['House B/L No']
        pkgs = int(row['포장갯수'])
        unit = format_unit(row['단위'], pkgs, force_to_pkg)
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])

        if not is_single_container and (container != prev_container or seal != prev_seal):
            desc_lines.extend(["", ""])
            desc_lines.append(f"{container} / {seal}")
            desc_lines.append("")
            prev_container, prev_seal = container, seal

        desc_lines.append(f"{hbl}\n{pkgs} {unit} / {weight} KGS / {measure} CBM")
        if hbl in mapping:
            desc_lines.extend(mapping[hbl])
        desc_lines.append("")

    result_text = "\n".join(summary_lines + [""] + mark_lines + ["", ""] + desc_lines)

    file_name = os.path.splitext(main_file.name)[0] + "_SR.txt"
    st.text_area("📋 결과 출력:", result_text, height=600)
    st.download_button("📥 결과 텍스트 다운로드", result_text, file_name=file_name)
