import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    unit_map = {'PK': 'PKG', 'PL': 'PLT', 'CT': 'CTN', 'BL': 'BL', 'CS': 'CS', 'WB': 'WB'}
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

st.title("🚢 화물2 - SR 자동 정리기")

force_to_pkg = st.checkbox("코스코 PLT 변환", value=False)

uploaded_file = st.file_uploader("📂 메인 엑셀 파일 업로드", type=["xlsx"])
mapping_file = st.file_uploader("📂 품목, HS CODE 추가 (선택)", type=["xlsx"])

if uploaded_file:
    log_uploaded_filename(uploaded_file.name)
    df = pd.read_excel(uploaded_file)
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

    # 전체 TOTAL 라인 출력
    grand = df[['포장갯수', 'Weight', 'Measure']].sum()
    total_pkgs = int(grand['포장갯수'])
    total_weight = format_number(grand['Weight'])
    total_cbm = format_number(grand['Measure'])
    summary_lines = [f"TOTAL: {total_pkgs} PKGS / {total_weight} KGS / {total_cbm} CBM", ""]

    for _, row in total_summary.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        pkgs = int(row['포장갯수'])
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])
        summary_lines.append(f"{container} / {seal}\nTOTAL: {pkgs} PKGS / {weight} KGS / {measure} CBM\n")

    # <MARK> 영역
    mark_lines = ["<MARK>", ""]
    for _, row in marks.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbls = row['House B/L No']
        if not is_single_container:
            mark_lines.append(f"{container} / {seal}")
        mark_lines.extend(sorted(hbls))
        mark_lines.append("")

    # <DESC> 영역
    mapping_dict = {}
    if mapping_file:
        map_df = pd.read_excel(mapping_file)
        map_df.columns = map_df.columns.str.strip()
        for _, row in map_df.iterrows():
            hbl = str(row.iloc[0]).strip()
            content = str(row.iloc[1]).strip()
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            if lines and "HS CODE" in lines[-1].upper():
                hs = "".join(filter(str.isdigit, lines[-1]))
                if len(hs) >= 6:
                    lines[-1] = hs
            mapping_dict[hbl] = "\n".join(lines)

    desc_lines = ["<DESC>", ""]
    prev_container = prev_seal = None
    for _, row in desc.iterrows():
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

        desc_lines.append(hbl)
        desc_lines.append(f"{pkgs} {unit} / {weight} KGS / {measure} CBM")
        if hbl in mapping_dict:
            desc_lines.append(mapping_dict[hbl])
        desc_lines.append("")

    result_lines = ["\n".join(summary_lines), "\n".join(mark_lines), "\n".join(desc_lines)]
    final_output = "\n\n".join(result_lines)

    st.download_button("📥 결과 메모장 다운로드", data=final_output, file_name="SR_정리결과.txt", mime="text/plain")
    st.text_area("📝 미리보기", value=final_output, height=600)

# 로그는 항상 접힌 상태로
with st.expander("📄 Log", expanded=False):
    log_path = "upload_log.txt"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = f.read()
        st.text_area("업로드 내역", value=logs, height=200)
    else:
        st.write("업로드 기록 없음.")
