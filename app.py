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
    t = f"{round(v,3):.3f}"
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn):
    p = "upload_log.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{now}] {fn}\n"
    with open(p, "a", encoding='utf-8') as f:
        f.write(entry)

# 페이지 설정 (전체 화면 넓게 사용)
st.set_page_config(page_title="🚢 SR Master", layout="wide")

# 상단 귀여운 배 디자인
st.markdown("<h1 style='text-align: center;'>🚢 SR 제출 자동 정리기 🚢</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: blue;'>🌊🌊🌊 오늘도 무사히 출항 준비 완료! (칼퇴 기원) 🌊🌊🌊</p>", unsafe_allow_html=True)
st.write("---")

tab1, tab2 = st.tabs(["🚀 출항 준비 (작업)", "📜 항해 일지 (로그)"])

with tab1:
    # 파일 업로드 칸을 옆으로 넓게 배치 (1:2 비율)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("⚙️ 설정")
        force_to_pkg = st.checkbox("코스코 전용: PLT -> PKG 변환")
        st.write("---")
        st.caption("팁: 엑셀 파일의 B/L 번호가 없으면 자동으로 제외됩니다.")

    with col2:
        st.subheader("📂 엑셀 파일 올리기")
        main_file = st.file_uploader("여기에 파일을 끌어다 놓으세요 (xlsx)", type=["xlsx"])

    if main_file:
        with st.spinner('🚢 열심히 화물을 정리 중입니다... 잠시만 기다려주세요!'):
            log_uploaded_filename(main_file.name)
            df = pd.read_excel(main_file)
            
            # 필요한 컬럼만 추출 및 빈 줄 제거
            cols = ['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']
            df = df[cols].copy()
            df = df.dropna(subset=['House B/L No'])
            
            # 데이터 정제
            df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]
            df['단위'] = df['단위'].fillna('PKG')

            # 데이터 계산
            total = df.groupby(['컨테이너 번호','Seal#1']).agg(
                포장갯수=('포장갯수','sum'),
                Weight=('Weight','sum'),
                Measure=('Measure','sum')
            ).reset_index()
            
            marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
            desc = df.sort_values(['컨테이너 번호','Seal#1','House B/L No'])
            
            lines = []

            # [GRAND TOTAL]
            if len(total) >= 2:
                g_pkg = int(total['포장갯수'].sum())
                g_w = format_number(total['Weight'].sum())
                g_m = format_number(total['Measure'].sum())
                lines.append("[GRAND TOTAL]")
                lines.append(f"TOTAL: {g_pkg} PKGS / {g_w} KGS / {g_m} CBM")
                lines.append("-" * 30)
                lines.append("")

            # SUMMARY
            for _, r in total.iterrows():
                pkg = int(r['포장갯수'])
                w = format_number(r['Weight'])
                m = format_number(r['Measure'])
                lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                lines.append(f"TOTAL: {pkg} PKGS / {w} KGS / {m} CBM\n")

            # <MARK> 섹션
            lines += ["<MARK>", ""]
            single = (len(total) == 1)
            for _, r in marks.iterrows():
                if not single:
                    lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}")
                # 각 B/L 번호를 한 줄에 하나씩 추가
                for hbl in sorted(r['House B/L No']):
                    lines.append(hbl)
                lines.append("")
            lines.append("")

            # <DESCRIPTION> 섹션
            lines += ["<DESCRIPTION>", ""]
            prev = (None, None)
            for _, r in desc.iterrows():
                cur = (r['컨테이너 번호'], r['Seal#1'])
                if cur != prev:
                    if prev[0] is not None:
                        lines += ["", ""]
                    if not single:
                        lines.append(f"{cur[0]} / {cur[1]}")
                        lines.append("")
                    prev = cur

                hbl_no = r['House B/L No']
                pkg_val = int(r['포장갯수'])
                unit_val = format_unit(r['단위'], r['포장갯수'], force_to_pkg)
                weight_val = format_number(r['Weight'])
                measure_val = format_number(r['Measure'])

                lines.append(f"{hbl_no}")
                lines.append(f"{pkg_val} {unit_val} / {weight_val} KGS / {measure_val} CBM")
                lines.append("")

            result = "\n".join(lines)
            
            st.success("✅ 화물 정리 완료! 선적 준비가 끝났습니다.")
            
            # 결과창 출력
            st.text_area("📋 결과 (그대로 복사해서 사용하세요):", result, height=500)
            
            st.download_button(
                label="💾 정리된 파일 다운로드 (.txt)",
                data=result,
                file_name=f"SR_DONE_{main_file.name.split('.')[0]}.txt",
                mime="text/plain"
            )

with tab2:
    st.subheader("📜 최근 항해 이력")
    if os.path.exists("upload_log.txt"):
        with open("upload_log.txt", "r", encoding='utf-8') as f:
            logs = f.read()
        st.text_area("로그 내역 (최신 업로드 순)", logs, height=400)
        st.download_button("📝 로그 파일 다운로드", logs, file_name="shipping_log.txt")
    else:
        st.info("아직 기록된 항해 이력이 없습니다.")