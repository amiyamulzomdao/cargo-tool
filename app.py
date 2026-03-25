import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False)
    u_str = str(unit).upper() if pd.notna(unit) else PKG
    m = {'PK''PKG','PL''PLT','CT''CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    return base + 'S' if u_str in ['PK','PL','CT'] and count  1 else base

def format_number(v)
    t = f{round(v,3).3f}
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn)
    p = upload_log.txt
    now = datetime.now().strftime(%Y-%m-%d %H%M%S)
    entry = f[{now}] {fn}n
    with open(p, a, encoding='utf-8') as f
        f.write(entry)

# 페이지 설정
st.set_page_config(page_title=SR 자동 정리기, layout=wide)

st.title(SR 제출 자동 정리기)

tab1, tab2 = st.tabs([작업 도구, 업로드 기록])

with tab1
    # 파일 업로드 여부에 따라 레이아웃 변경
    if main_file_key not in st.session_state
        st.session_state.main_file_key = 0

    main_file = st.file_uploader(엑셀 파일을 업로드하세요 (xlsx), type=[xlsx])

    if main_file
        # 파일이 있을 때는 화면을 11.5 비율로 분할
        col_input, col_result = st.columns([1, 1.5])
        
        with col_input
            st.subheader(설정 및 재업로드)
            force_to_pkg = st.checkbox(코스코 PLT - PKG 변환)
            st.info(f현재 파일 {main_file.name})
            
            # 데이터 처리 로직 시작
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            
            cols = ['House BL No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House BL No'])
            
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')

            total = df.groupby(['컨테이너 번호','Seal#1']).agg(
                포장갯수=('포장갯수','sum'),
                Weight=('Weight','sum'),
                Measure=('Measure','sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호','Seal#1'])['House BL No'].unique().reset_index()
            desc = df.sort_values(['컨테이너 번호','Seal#1','House BL No'])
            
            lines = []

            # [GRAND TOTAL]
            if len(total) = 2
                g_pkg = int(total['포장갯수'].sum())
                g_w = format_number(total['Weight'].sum())
                g_m = format_number(total['Measure'].sum())
                lines.append([GRAND TOTAL])
                lines.append(fTOTAL {g_pkg} PKGS  {g_w} KGS  {g_m} CBM)
                lines.append(-  30)
                lines.append()

            # SUMMARY
            for _, r in total.iterrows()
                pkg = int(r['포장갯수'])
                w = format_number(r['Weight'])
                m = format_number(r['Measure'])
                lines.append(f{r['컨테이너 번호']}  {r['Seal#1']})
                lines.append(fTOTAL {pkg} PKGS  {w} KGS  {m} CBMn)

            # MARK
            lines += [MARK, ]
            single = (len(total) == 1)
            for _, r in marks.iterrows()
                if not single
                    lines.append(f{r['컨테이너 번호']}  {r['Seal#1']})
                for hbl in sorted(r['House BL No'])
                    lines.append(hbl)
                lines.append()
            lines.append()

            # DESCRIPTION
            lines += [DESCRIPTION, ]
            prev = (None, None)
            for _, r in desc.iterrows()
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev
                    if prev[0] is not None lines += [, ]
                    if not single
                        lines.append(f{cur[0]}  {cur[1]})
                        lines.append()
                    prev = cur

                hbl_no = r['House BL No']
                pkg_val = int(r['포장갯수'])
                unit_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                weight_val = format_number(r['Weight'])
                measure_val = format_number(r['Measure'])

                lines.append(f{hbl_no})
                lines.append(f{pkg_val} {unit_val}  {weight_val} KGS  {measure_val} CBM)
                lines.append()

            result = n.join(lines)

        with col_result
            st.subheader(정리 결과)
            st.text_area(텍스트 영역, result, height=600)
            st.download_button(
                label=결과 다운로드 (.txt),
                data=result,
                file_name=fSR_Result_{main_file.name.split('.')[0]}.txt
            )
    else
        # 파일이 없을 때는 중앙에 넓게 배치
        st.write(---)
        st.caption(작업할 엑셀 파일을 아래에 올려주세요.)

with tab2
    st.subheader(업로드 이력)
    if os.path.exists(upload_log.txt)
        with open(upload_log.txt, r, encoding='utf-8') as f
            logs = f.read()
        st.text_area(로그 내역, logs, height=400)
    else
        st.write(기록이 없습니다.)