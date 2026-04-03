import streamlit as st
import pandas as pd
import pdfplumber
import re
import os

# --- 1. 유틸리티 및 디자인 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

def format_number(v):
    try:
        val = float(str(v).replace(',', ''))
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

# --- 2. 분석 엔진 (메모장 데이터 추출) ---
def parse_sr_txt(txt_content):
    data = {"total_msr": "0", "hbl_list": []}
    msr_match = re.search(r"TOTAL:.*?([\d.]+)\s*CBM", txt_content)
    if msr_match: data["total_msr"] = format_number(msr_match.group(1))
    
    if "<DESCRIPTION>" in txt_content:
        desc_part = txt_content.split("<DESCRIPTION>")[-1]
        # HBL번호와 해당 블록의 CBM 수치를 순서대로 추출
        blocks = re.findall(r"([A-Z0-9]{8,16})\n.*?([\d.]+)\s*CBM", desc_part, re.DOTALL)
        for hbl, msr in blocks:
            data["hbl_list"].append({"hbl": hbl, "msr": format_number(msr)})
    return data

# --- 3. 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["SR 정리", "MBL 검수", "업로드 기록"])

with tab1:
    st.info("기존 SR 정리 기능을 이용하세요.")

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1. 메모장 정보 입력**")
        input_mode = st.radio("방식 선택", ["복사 붙여넣기", "파일 업로드"], horizontal=True, label_visibility="collapsed")
        memo_content = st.text_area("내용 붙여넣기", height=250) if input_mode == "복사 붙여넣기" else ""
        if input_mode == "파일 업로드":
            m_file = st.file_uploader("메모장 파일", type=["txt"])
            if m_file: memo_content = m_file.read().decode("utf-8")
            
    with col2:
        st.markdown("**2. 선사 DRAFT BL 업로드**")
        draft_pdf = st.file_uploader("PDF 파일", type=["pdf"], key="d_up", label_visibility="collapsed")
        
        if memo_content and draft_pdf:
            try:
                sr = parse_sr_txt(memo_content)
                errors = []
                
                with pdfplumber.open(draft_pdf) as pdf:
                    for page in pdf.pages:
                        p_text = page.extract_text()
                        if not p_text: continue
                        p_text_upper = p_text.upper()
                        
                        # 각 HBL별로 해당 페이지에 있는지 확인하고 수치 대조
                        for item in sr["hbl_list"]:
                            hbl = item["hbl"]
                            if hbl in p_text_upper:
                                # MSC 특성상 HBL 번호가 있는 줄이나 근처에서 '숫자 + CU. M.' 패턴을 찾음
                                # 해당 페이지에서 0.047 같이 선사가 잘못 적은 수치와 우리 기준(1.652)을 대조
                                sr_msr = item["msr"]
                                
                                # HBL 번호 주변 텍스트 추출 (앞뒤 500자)
                                start_idx = p_text_upper.find(hbl)
                                context = p_text_upper[max(0, start_idx-100) : start_idx+600]
                                
                                # 수치 검증: 메모장의 CBM이 해당 HBL 근처에 존재하는가?
                                if sr_msr not in context:
                                    # 만약 메모장 수치가 없고 다른 수치(예: 0.047)가 보인다면 에러 추가
                                    wrong_msr_match = re.search(r"([\d.]+)\s*(?:CU\.\s*M|CBM)", context)
                                    wrong_val = wrong_msr_match.group(1) if wrong_msr_match else "수치 미상"
                                    errors.append(f"❌ 부피 불일치: {sr_msr} CBM (HBL: {hbl}) -> PDF상 {wrong_val} 기재됨")

                st.markdown("---")
                if not errors:
                    st.success("✅ 모든 항목이 정확히 일치합니다.")
                else:
                    st.warning(f"⚠️ 총 {len(errors)}건의 불일치가 발견되었습니다.")
                    # 촘촘한 결과 출력
                    for err in errors:
                        st.error(err)
            except Exception as e:
                st.error(f"검수 중 오류 발생: {e}")

with tab3:
    st.write("업로드 기록창입니다.")
