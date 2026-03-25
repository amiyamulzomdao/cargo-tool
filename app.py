import streamlit as st
import pandas as pd
import os
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    u_str = str(unit).upper() if pd.notna(unit) else "PKG"
    m = {'PK':'PKG', 'PL':'PLT', 'CT':'CTN'}
    base = 'PKG' if (force_to_pkg and u_str == 'PL') else m.get(u_str, u_str)
    if u_str in ['PK', 'PL', 'CT'] and count > 1:
        return base + 'S'
    return base

def format_number(v):
    try:
        val = float(v)
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except:
        return str(v)

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

        try:
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            
            cols = ['House B/L No', '컨테이너 번호', 'Seal#1', '포장갯수', '단위', 'Weight', 'Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            
            has_gt = df['단위'].fillna('').astype(str).str.upper().str.contains('GT').any()
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')

            total = df.groupby(['컨테이너 번호', 'Seal#1']).agg(
                포장갯수=('포장갯수', 'sum'),
                Weight=('Weight', 'sum'),
                Measure=('Measure', 'sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호', 'Seal#1'])['House B/L No'].unique().reset_index()
            desc_df = df.sort_values(['컨테이너 번호', 'Seal#1', 'House B/L No'])
            
            lines = []
            single = (len(total) == 1)

            if not single:
                g_p = int(total['포장갯수'].sum())
                g_w = format_number(total['Weight'].sum())
                g_m = format_number(total['Measure'].sum())
                total_line = f"TOTAL: {g_p} PKGS / {g_w} KGS / {g_m} CBM"
                lines.append("[GRAND TOTAL]")
                lines.append(total_line)
                lines.append("-" * (len(total_line) + 10))
                lines.append("")

            for _, r in total.iterrows():
                p, w, m = int(r['포장갯수']), format_number(r['Weight']), format_number(r['Measure'])
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {p} PKGS / {w} KGS / {m} CBM\n")

            lines += ["<MARK>", ""]
            for _, r in marks.iterrows():
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append("") 
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                    if single: lines.append("")
                if not single: lines.append("")
            lines.append("")

            lines += ["<DESCRIPTION>", ""]
            prev = (None, None)
            for _, r in desc_df.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None:
                        lines.append("")
                        lines.append("")
                    if not single:
                        lines.append(f"{cur[0]} / {cur[1]}")
                        lines.append("")
                    prev = cur
                
                u_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                w_val = format_number(r['Weight'])
                m_val = format_number(r['Measure'])
                lines.append(f"{r['House B/L No']}")
                lines.append(f"{int(r['포장갯수'])} {u_val} / {w_val} KGS / {m_val} CBM")
                lines.append("")

            result = "\n".join(lines)

            with col_res:
                r_c1, r_c2 = st.columns([2, 1])
                with r_c1: st.subheader("정리 결과")
                with r_c2:
                    st.download_button(
                        label="💾 메모장 다운로드",
                        data=result,
                        file_name=f"SR_{main_file.name.split('.')[0]}.txt",
                        use_container_width=True
                    )
                
                if has_gt:
                    st.error("⚠️ *GT 단위가 있습니다. 데이터 확인이 필요합니다.*")
                
                st.text_area("결과", result, height=600, label_visibility="collapsed")

        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {e}")
            
    else:
        # 수정: 파일 업로드 전 하단 안내 문구를 제거하고 빈 줄만 유지
        st.write("")

with tab2:
    st.subheader("업로드 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            logs = f.read()
        st.text_area("로그", logs, height=400)
    else:
        st.write("기록이 없습니다.")
