import streamlit as st
import pandas as pd
import os  # 파일명 추출용
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

force_to_pkg = st.checkbox("코스코 PLT 변환", value=False)
with st.expander("📎 품목, HS CODE 추가 (선택)", expanded=False):
    mapping_file = st.file_uploader("매핑 파일 업로드 (선택)", type=["xlsx"], key="optional")

uploaded_file = st.file_uploader("메인 엑셀 파일 업로드", type=["xlsx"], key="main")

if uploaded_file:
    log_uploaded_filename(uploaded_file.name)
    df = pd.read_excel(uploaded_file)
    df = df[['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').apply(lambda x: str(x).split('.')[0])

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

    grand_total_pkg = int(df['포장갯수'].sum())
    grand_total_w = format_number(df['Weight'].sum())
    grand_total_m = format_number(df['Measure'].sum())

    summary_lines = [
        f"TOTAL: {grand_total_pkg} PKGS / {grand_total_w} KGS / {grand_total_m} CBM", ""
    ]
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

    extra_desc_map = {}
    if mapping_file:
        map_df = pd.read_excel(mapping_file)
        for _, row in map_df.iterrows():
            hbl = str(row.iloc[0]).strip()
            content = str(row.iloc[1]).strip()
            if content:
                cleaned_lines = []
                for line in content.splitlines():
                    line = line.strip()
                    if line.upper().startswith("HS CODE"):
                        code = ''.join(filter(str.isdigit, line))
                        cleaned_lines.append(code)
                    else:
                        cleaned_lines.append(line)
                extra_desc_map[hbl] = '\n'.join(cleaned_lines)

    desc_lines = ["<DESC>", ""]
    prev_container = None
    prev_seal = None
    for i, row in desc.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbl = row['House B/L No']
        pkgs = int(row['포장갯수'])
        unit = format_unit(row['단위'], pkgs, force_to_pkg=force_to_pkg)
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])

        if not is_single_container and ((container != prev_container) or (seal != prev_seal)):
            desc_lines.extend(["", "", f"{container} / {seal}", ""])
            prev_container, prev_seal = container, seal

        desc_lines.append(f"{hbl}")
        desc_lines.append(f"{pkgs} {unit} / {weight} KGS / {measure} CBM")
        if hbl in extra_desc_map:
            desc_lines.append(extra_desc_map[hbl])

    result_text = "\n".join(summary_lines + [""] + mark_lines + ["", ""] + desc_lines)
    file_name = os.path.splitext(uploaded_file.name)[0] + ".txt"

    st.text_area("📋 결과 출력:", result_text, height=600)
    st.download_button("결과 텍스트 다운로드", result_text, file_name=file_name)
