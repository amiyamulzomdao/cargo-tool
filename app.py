# Code Version: SRAuto22 - Multi‑line 품목 & HS CODE mapping with dot‑removal option
import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

def format_unit(unit, count, force_to_pkg=False):
    """
    단위 매핑 및 복수형 처리
    PK→PKG, PL→PLT, CT→CTN, 기타는 그대로.
    force_to_pkg 체크 시 PL→PKG.
    """
    m = {'PK':'PKG','PL':'PLT','CT':'CTN'}
    base = 'PKG' if (force_to_pkg and unit.upper()=='PL') else m.get(unit.upper(), unit.upper())
    return base+'S' if unit.upper() in ['PK','PL','CT'] and count>1 else base

def format_number(v):
    """소수점 3자리까지, 불필요 0 제거"""
    t = f"{round(v,3):.3f}"
    return t.rstrip('0').rstrip('.') if '.' in t else t

def log_uploaded_filename(fn):
    """업로드된 파일명만 중복 없이 기록"""
    p = "upload_log.txt"
    entry = fn + "\n"
    if os.path.exists(p):
        lines = open(p,"r",encoding='utf-8').readlines()
        if entry in lines: return
        mode='a'
    else:
        mode='w'
    with open(p, mode, encoding='utf-8') as f:
        f.write(entry)

st.set_page_config(page_title="🚢 SR 제출 자동 정리기",
                   initial_sidebar_state="collapsed")
st.title("🚢 SR 제출 자동 정리기")
st.markdown("엑셀 파일 업로드 → SR 정리 + (선택) 품목·HS CODE 매핑")
force_to_pkg = st.checkbox("코스코 PLT변환")
main_file = st.file_uploader("메인 엑셀 파일 업로드", type=["xlsx"])

# expander 안의 추가 매핑 섹션
extra_map = {}
with st.expander("품목·HS CODE 추가 (선택)", expanded=False):
    hsc_remove = st.checkbox("코스코 HSCODE 점(.) 제거")
    extra_file = st.file_uploader("추가 매핑 파일 업로드", type=["xlsx"], key="extra")
    if extra_file:
        log_uploaded_filename(extra_file.name)
        ex = pd.read_excel(extra_file)  # header row 있는 형태
        # 첫 열이 HBL, '품목' 컬럼에서 멀티라인 문자열 추출
        hbl_col = ex.columns[0]
        item_col = '품목' if '품목' in ex.columns else ex.columns[1]
        for _, row in ex.iterrows():
            hbl = str(row[hbl_col]).strip()
            text = str(row[item_col])
            if not hbl or pd.isna(text): 
                continue
            # 줄별로 분리 → HS CODE 라인(숫자/HS CODE:)은 필터링
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            mapped = []
            for ln in lines:
                # 'HS CODE:' 라인을 건너뛰고, 순수 숫자 코드도 ln 그대로 취급
                if ln.upper().startswith('HS CODE:'):
                    code = ln.split(':',1)[1].strip()
                    if hsc_remove:
                        code = code.replace('.','')
                    mapped.append(code)
                elif re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', ln):
                    code = ln
                    if hsc_remove:
                        code = code.replace('.','')
                    mapped.append(code)
                else:
                    mapped.append(ln)
            if mapped:
                extra_map[hbl] = mapped

if main_file:
    log_uploaded_filename(main_file.name)
    df = pd.read_excel(main_file)
    df = df[['House B/L No','컨테이너 번호','Seal#1','포장갯수','단위','Weight','Measure']].copy()
    df['Seal#1'] = df['Seal#1'].fillna('').astype(str).str.split('.').str[0]

    total = df.groupby(['컨테이너 번호','Seal#1']).agg(
        포장갯수=('포장갯수','sum'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum')
    ).reset_index()
    marks = df.groupby(['컨테이너 번호','Seal#1'])['House B/L No'].unique().reset_index()
    desc  = df.groupby(['컨테이너 번호','Seal#1','House B/L No']).agg(
        포장갯수=('포장갯수','sum'),
        단위=('단위','first'),
        Weight=('Weight','sum'),
        Measure=('Measure','sum')
    ).reset_index().sort_values(['컨테이너 번호','Seal#1','House B/L No'])
    single = (len(total)==1)

    lines = []
    # SUMMARY
    for _, r in total.iterrows():
        pkg, w, m = int(r['포장갯수']), format_number(r['Weight']), format_number(r['Measure'])
        lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}\nTOTAL: {pkg} PKGS / {w} KG / {m} CBM\n")

    # MARK
    lines += ["<MARK>",""]
    for _, r in marks.iterrows():
        if not single:
            lines.append(f"{r['컨테이너 번호']} / {r['Seal#1']}"); lines.append("")
        lines += sorted(r['House B/L No']); lines.append("")
    lines.append("")

    # DESC
    lines += ["<DESC>",""]
    prev = (None,None)
    for _, r in desc.iterrows():
        cur = (r['컨테이너 번호'], r['Seal#1'])
        if cur!=prev:
            if prev[0] is not None: lines+=["","",""]
            if not single:
                lines.append(f"{cur[0]} / {cur[1]}"); lines.append("")
            prev = cur
        hbl = r['House B/L No']
        lines.append(hbl)
        lines.append(f"{int(r['포장갯수'])} {format_unit(r['단위'],r['포장갯수'],force_to_pkg)} / "
                     f"{format_number(r['Weight'])} KGS / {format_number(r['Measure'])} CBM")
        # 매핑 정보 삽입
        for info in extra_map.get(hbl, []):
            lines.append(info)
        lines.append("")

    result = "\n".join(lines)
    st.text_area("📋 결과 출력:", result, height=600)
    st.download_button("결과 텍스트 다운로드", result,
                       file_name=os.path.splitext(main_file.name)[0]+".txt")

# Sidebar Log 버튼
if st.sidebar.button("Log"):
    if os.path.exists("upload_log.txt"):
        logs = open("upload_log.txt","r",encoding='utf-8').read()
        st.sidebar.text_area("Log", logs, height=300)
    else:
        st.sidebar.warning("Log가 아직 없습니다.")
