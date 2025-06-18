import streamlit as st
import pandas as pd

def format_unit(unit, count):
    unit_map = {'PK': 'PKG', 'PL': 'PLT', 'CT': 'CTN'}
    base = unit_map.get(unit.upper(), unit.upper())
    if unit.upper() in unit_map and count > 1:
        return base + 'S'
    return base

def remove_trailing_zero(value):
    if value == int(value):
        return str(int(value))
    return str(value)

st.title("🚢 화물 정보 자동 정리기")
st.markdown("엑셀 파일을 업로드하면 메모장에 붙여넣을 형식으로 자동 정리해드립니다.")

uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # 필요한 열만 추출
    df = df[['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']].copy()

    # 총합 계산을 위해 컨테이너+씰 단위로 그룹
    container_totals = df.groupby(['컨테이너 번호', 'Seal#1']).agg({
        '포장갯수': 'sum',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index()

    # HBL 단위 정리
    df_grouped = df.groupby(['컨테이너 번호', 'Seal#1', 'House B/L No']).agg({
        '포장갯수': 'sum',
        '단위': 'first',
        'Weight': 'sum',
        'Measure': 'sum'
    }).reset_index()

    # 컨테이너/씰별 TOTAL 먼저 출력
    total_summary_lines = []
    for _, row in container_totals.iterrows():
        container = row['컨테이너 번호']
        seal = str(row['Seal#1']).split('.')[0] if not pd.isna(row['Seal#1']) else ''
        total_pkgs = int(row['포장갯수'])
        total_weight = remove_trailing_zero(round(row['Weight'], 2))
        total_measure = remove_trailing_zero(round(row['Measure'], 3))
        total_summary_lines.append(f"{container} / {seal}\nTOTAL: {total_pkgs} PKGS / {total_weight} KGS / {total_measure} CBM\n")

    # 결과 조립
    output_lines = []
    current_container = None
    for _, row in df_grouped.iterrows():
        container = row['컨테이너 번호']
        seal = str(row['Seal#1']).split('.')[0] if not pd.isna(row['Seal#1']) else ''
        hbl = row['House B/L No']
        count = int(row['포장갯수'])
        unit = format_unit(row['단위'], count)
        weight = remove_trailing_zero(round(row['Weight'], 2))
        measure = remove_trailing_zero(round(row['Measure'], 3))

        if container != current_container:
            if current_container is not None:
                output_lines.append("")  # 컨테이너 구분을 위한 빈 줄
            output_lines.append(f"{container} / {seal}\n")
            current_container = container

        output_lines.append(f"{hbl}\n{count} {unit} / {weight} KGS / {measure} CBM\n")

    # 최종 결과 정리
    result_text = "\n".join(total_summary_lines + [""] + output_lines)
    st.text_area("📋 복사해서 메모장에 붙여넣으세요:", result_text, height=400)

    st.download_button("결과 텍스트 다운로드", result_text, file_name="cargo_output.txt")
