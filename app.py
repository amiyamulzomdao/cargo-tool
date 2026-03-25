import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG','PL':'PLT','CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    return base + 'S' if u_str in ['PK','PL','CT'] and count > 1 else base

def format_number(v):
    t = f"{round(v, 3):.3f}"
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn):
    p = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# 페이지 설정
st.set_page_config(page_title="SR 자동 정리기", layout="wide")

st.title("SR 제출 자동 정리기")

tab1, tab2 = st.tabs(["작업 도구", "업로드 기록"])

with tab1:
    main_file = st.file_uploader("엑셀 파일을 업로드하세요 (xlsx)", type=["xlsx"])

    if main_file:
        col_in, col_res = st.columns([1, 1.5])
        
        with col_in:
            st.subheader("설정 및 정보")
            force_to_pkg = st.checkbox("코스코 PLT -> PKG 변환")
            st.info(f"파일: {main_file.name}")
            
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            
            target_cols = ['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']
            df = df[target_cols].copy()
            df = df.dropna(subset=['House B/L No'])
            
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')

            total = df.groupby(['컨테이너 번호','Seal#1']).agg(
                포장갯수=('포장갯수','sum'),
                Weight=('Weight','sum'),
                Measure=('Measure','sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
            
            sort_keys = ['컨테이너 번호','Seal#1','House B/L No']
            desc = df.sort_values(sort_keys)
            
            lines = []
            single = (len(total) == 1)

            if len(total) >= 2:
                g_p = int(total['포장갯수'].sum())
                g_w = format_number(total['Weight'].sum())
                g_m = format_number(total['Measure'].sum())
                lines.append("[GRAND TOTAL]")
                lines.append(f"TOTAL: {g_p} PKGS / {g_w} KGS / {g_m} CBM")
                lines.append("-" * 30)
                lines.append("")

            for _, r in total.iterrows():
                pkg = int(r['포장갯수'])
                w = format_number(r['Weight'])
                m = format_number(r['Measure'])
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {pkg} PKGS / {w} KGS / {m} CBM\n")

            lines += ["<MARK>", ""]
            for _, r in marks.iterrows():
                if not single:
                    lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single: 
                        lines.append("")
                
                if not single: 
                    lines.append("")
            lines.append("")

            lines += ["<DESCRIPTION>", ""]
            prev = (None, None)
            for _, r in desc.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None:
                        lines.append("")
                        lines.append("")
                    if not single:
                        lines.append(f"{cur[0]} / {cur[1]}")
                        lines.append("")
                    prev = cur

                h_no = r['House B/L No']
                p_val = int(r['포장갯수'])
                u_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                w_val = format_number(r['Weight'])
                m_val = format_number(r['Measure'])

                lines.append(f"{h_no}")
                lines.append(f"{p_val} {u_val} / {w_val} KGS / {m_val} CBM")
                lines.append("")

            result = "\n".join(lines)

        with col_res:
            res_c1, res_c2 = st.columns([2, 1])
            with res_c1:
                st.subheader("정리 결과")
            with res_c2:
                st.download_button(
                    label="💾 메모장 다운로드",
                    data=result,
                    file_name=f"SR_{main_file.name.split('.')[0]}.txt",
                    use_container_width=True
                )
            
            st.text_area("결과 데이터", result, height=600, label_visibility="collapsed")
    else:
        st.write("---")
        st.info("엑셀파일을 업로드 해주세요.")

with tab2:
    st.subheader("업로드 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            logs = f.read()
        st.text_area("로그 데이터", logs, height=400)
    else:
        st.write("기록이 없습니다.")