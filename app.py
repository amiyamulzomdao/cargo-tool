import streamlit as st
import pandas as pd
import os  # 파일명 추출용


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
    text = f"{value:.3f}"  # 항상 소수점 셋째자리까지 만들고
    if '.' in text:
        text = text.rstrip('0').rstrip('.')  # 0과 . 제거
    return text  # 쉼표 제거된 숫자 반환


st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 컨테이너별 마크 및 디스크립션을 정리해드립니다.")

force_to_pkg = st.checkbox("코스코 PLT변환")

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # 필요한 열 추출 및 정리
    df = df[['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').apply(lambda x: str(x).split('.')[0])

    # 컨+씰 기준으로 전체 합산
    total_summary = df.groupby(['컨테이너 번호', 'Seal#1']).agg({
        '포장갯수': 'sum',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index()

    # 마크 정리용 (컨+씰별로 HBL 리스트)
    marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()

    # 디스크립션 정리용 (컨+씰+HBL별로 나누기)
    desc = df.groupby(['컨테이너 번호', 'Seal#1', 'House B/L No']).agg({
        '포장갯수': 'sum',
        '단위': 'first',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index()

    is_single_container = total_summary.shape[0] == 1

    # 총합 출력
    summary_lines = []
    for _, row in total_summary.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        pkgs = int(row['포장갯수'])
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])
        summary_lines.append(f"{container} / {seal}\nTOTAL: {pkgs} PKGS / {weight} KG / {measure} CBM\n")

    # MARK 출력
    mark_lines = ["<MARK>\n"]
    for _, row in marks.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbls = row['House B/L No']
        if not is_single_container:
            mark_lines.append(f"{container} / {seal}\n")
        mark_lines.extend(hbls)
        mark_lines.append("")

    # DESC 출력
    desc_lines = ["<DESC>\n"]
    prev_container = None
    prev_seal = None
    for _, row in desc.iterrows():
        container = row['컨테이너 번호']
        seal = row['Seal#1']
        hbl = row['House B/L No']
        pkgs = int(row['포장갯수'])
        unit = format_unit(row['단위'], pkgs, force_to_pkg=force_to_pkg)
        weight = format_number(row['Weight'])
        measure = format_number(row['Measure'])

        if not is_single_container and ((container != prev_container) or (seal != prev_seal)):
            desc_lines.append(f"{container} / {seal}\n")
            prev_container, prev_seal = container, seal

        desc_lines.append(f"{hbl}\n{pkgs} {unit} / {weight} KGS / {measure} CBM\n")

    # 최종 결과 조립
    result_text = "\n".join(summary_lines + [""] + mark_lines + [""] + desc_lines)

    # 파일명 자동 설정
    file_name = os.path.splitext(uploaded_file.name)[0] + ".txt"

    st.text_area("📋 결과 출력:", result_text, height=600)
    st.download_button("결과 텍스트 다운로드", result_text, file_name=file_name)
