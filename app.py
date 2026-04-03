import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
from datetime import datetime, timedelta, timezone

# --- 1. 유틸리티 함수 (카고3 불변 원칙) ---
def format_number(v):
    try:
        val = float(v)
        t = f"{round(val, 3):.3f}"
        return t.rstrip('0').rstrip('.') if '.' in t else t
    except: return str(v)

# --- 2. 메모장(TXT) 분석 엔진 ---
def parse_sr_txt(txt_content):
    """메모장 파일에서 검수에 필요한 핵심 수치들을 추출합니다."""
    data = {"containers": [], "seals": [], "hbl_list": [], "total_pkg": 0, "total_wgt": "0", "total_msr": "0"}
    
    # 1. 총계 추출 (TOTAL: 29 PKGS / 4643.2 KGS... 형식)
    pkg_match = re.search(r"TOTAL:\s*(\d+)\s*PKGS", txt_content)
    wgt_match = re.search(r"/\s*([\d.]+)\s*KGS", txt_content)
    msr_match = re.search(r"/\s*([\d.]+)\s*CBM", txt_content)
    
    if pkg_match: data["total_pkg"] = int(pkg_match.group(1))
    if wgt_match: data["total_wgt"] = wgt_match.group(1)
    if msr_match: data["total_msr"] = msr_match.group(1)
    
    # 2. 컨테이너 / 씰 추출 (상단 TOTAL 섹션의 컨/씰 정보)
    cntr_matches = re.findall(r"([A-Z]{4}\d{7})\s*/\s*([A-Z0-9]+)", txt_content)
    for c, s in cntr_matches:
        data["containers"].append(c)
        data["seals"].append(s)
        
    # 3. HBL 상세 추출 (<DESCRIPTION> 이후 섹션 분석)
    if "<DESCRIPTION>" in txt_content:
        desc_part = txt_content.split("<DESCRIPTION>")[-1]
        # HBL번호, 수량, 중량, 부피 순서로 매칭
        hbl_blocks = re.findall(r"([A-Z0-9]{8,16})\n(\d+)\s*\w+\s*/\s*([\d.]+)\s*KGS\s*/\s*([\d.]+)\s*CBM", desc_part)
        
        for hbl, pkg, wgt, msr in hbl_blocks:
            # 해당 HBL 블록 아래에서 HS CODE(0000.00 형식) 탐색
            search_area = desc_part.split(hbl)[-1].split("\n\n")[0]
            hs_match = re.search(r"(\d{4}\.\d{2})", search_area)
            data["hbl_list"].append({
                "hbl": hbl, "pkg": pkg, "wgt": wgt, "msr": msr, "hs": hs_match.group(1) if hs_match else ""
            })
    return data

# --- 3. 페이지 설정 ---
st.set_page_config(page_title="Europe Docs tool", layout="wide")
st.title("🚢 Europe Docs tool")

tab1, tab2 = st.tabs(["📄 SR 정리 (메모장 생성)", "🔍 MBL 검수 (DRAFT 대조)"])

# --- TAB 1: SR 정리 (기존 순정 로직 유지) ---
with tab1:
    st.subheader("1단계: SR 정리 및 메모장 생성")
    # 기존 SR 정리 코드 위치 (생략)
    st.info("평소처럼 엑셀을 넣어 메모장을 만드세요.")

# --- TAB 2: MBL 검수 (파일 업로드 방식 전용) ---
with tab2:
    st.subheader("2단계: 선사 DRAFT BL 검수")
    st.write("작성했던 **메모장**과 선사가 준 **DRAFT PDF**를 업로드하면 자동으로 대조합니다.")
    
    c1, c2 = st.columns(2)
    with c1:
        st.info("📋 우리가 만든 기준")
        memo_file = st.file_uploader("메모장 업로드 (.txt)", type=["txt"], key="memo_up")
    with c2:
        st.info("📄 선사가 준 결과")
        draft_pdf = st.file_uploader("선사 DRAFT BL 업로드 (.pdf)", type=["pdf"], key="draft_up")
    
    if memo_file and draft_pdf:
        try:
            # 1. 메모장 데이터 로드 및 분석
            memo_text = memo_file.read().decode("utf-8")
            sr = parse_sr_txt(memo_text)
            
            # 2. DRAFT PDF 텍스트 추출
            with pdfplumber.open(draft_pdf) as pdf:
                pdf_text = "".join([p.extract_text() for p in pdf.pages]).upper()
            
            errors = []
            st.divider()
            st.subheader("🔍 검수 결과")
            
            # [검수 항목 1: 총계]
            if str(sr["total_pkg"]) not in pdf_text: errors.append(f"❌ 총 수량 불일치: {sr['total_pkg']} PKGS")
            if sr["total_wgt"] not in pdf_text: errors.append(f"❌ 총 중량 불일치: {sr['total_wgt']} KGS")
            if sr["total_msr"] not in pdf_text: errors.append(f"❌ 총 부피 불일치: {sr['total_msr']} CBM")
            
            # [검수 항목 2: 컨테이너/씰]
            for c in set(sr["containers"]):
                if c.upper() not in pdf_text: errors.append(f"❌ 컨테이너 번호 누락/오류: {c}")
            for s in set(sr["seals"]):
                if s and s.upper() not in pdf_text: errors.append(f"❌ Seal 번호 누락/오류: {s}")
                
            # [검수 항목 3: 개별 HBL 상세 및 HS CODE]
            for item in sr["hbl_list"]:
                if item["hs"] and item["hs"] not in pdf_text:
                    errors.append(f"❌ HS CODE 불일치 ({item['hbl']}): {item['hs']}")
                if item["wgt"] not in pdf_text:
                    errors.append(f"❌ 개별 중량 불일치 ({item['hbl']}): {item['wgt']} KGS")

            # 결과 출력
            if not errors:
                st.success("✅ [검수 통과] 모든 주요 항목이 메모장 데이터와 일치합니다!")
            else:
                st.warning(f"⚠️ 총 {len(errors)}개의 불일치 항목이 발견되었습니다.")
                for err in errors: st.error(err)
                
        except Exception as e:
            st.error(f"검수 과정에서 오류가 발생했습니다: {e}")
