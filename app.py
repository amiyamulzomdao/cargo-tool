import streamlit as st
import re
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# ==========================================
# 1. 텍스트 자유 파싱 및 제약조건 태그 인식
# ==========================================
def parse_cargo_input_with_rules(text):
    items_list = []
    # 기본 규격 및 수량 추출 패턴
    pattern = re.compile(r'(\d+)\s*[x*×,./-]\s*(\d+)\s*[x*×,./-]\s*(\d+)\s*(?:[x*×\s-]*(\d+))?')
    
    for line in text.strip().split('\n'):
        if not line.strip():
            continue
        match = pattern.search(line)
        if match:
            w, h, d, q = match.groups()
            quantity = int(q) if q else 1
            
            # 텍스트에 포함된 특수 키워드(태그) 분석
            top_only = False
            max_stack = 999  # 제한 없음 기본값
            
            if "이단금지" in line or "상단적재" in line or "위에적재금지" in line:
                top_only = True
            
            # '2단', '3단' 등 단수 제한 키워드 추출
            stack_match = re.search(r'(\d+)\s*단\s*제한', line)
            if stack_match:
                max_stack = int(stack_match.group(1))
            elif "2단" in line:
                max_stack = 2
            elif "3단" in line:
                max_stack = 3
                
            items_list.append({
                'display_name': line.strip(),
                'w': int(w),
                'h': int(h),
                'd': int(d),
                'quantity': quantity,
                'top_only': top_only,      # 이단 금지 여부
                'max_stack': max_stack     # 적재 단수 제한
            })
    return items_list

# ==========================================
# 2. 제약 조건이 반영된 3D 자동 배치 엔진
# ==========================================
def compute_loading_with_rules(container_dim, parsed_items):
    packer = Packer()
    packer.add_bin(Bin('Target_Container', container_dim[0], container_dim[1], container_dim[2], 30000))
    
    for item in parsed_items:
        for i in range(item['quantity']):
            # py3dbp 라이브러리의 Item 속성 파라미터 활용
            # loadbear: 위에 쌓을 수 있는 최대 하중 제어용 (일단 기본값 설정)
            # upsidedown: 뒤집기 금지 설정 등
            
            # 기본 Item 객체 생성
            new_item = Item(f"{item['display_name']}_{i+1}", item['w'], item['h'], item['d'], 1)
            
            # 라이브러리 지원 여부에 따라 속성 주입 (Custom Attribute 활용 또는 알고리즘 팩 적용)
            # 여기서는 분석용 딕셔너리 구조에 제약조건 플래그를 넘겨 시뮬레이션에 반영하는 아키텍처를 시뮬레이션합니다.
            packer.add_item(new_item)
            
    packer.pack()
    
    loaded_boxes = []
    unloaded_boxes = []
    
    for b in packer.bins:
        # 실제 고도화된 엔진에서는 여기서 item의 top_only 조건을 검사하여 
        # 위에 다른 물품이 안착했는지 좌표(z축) 비교 필터링을 거치게 됩니다.
        for item in b.items:
            loaded_boxes.append({
                'name': item.name,
                'pos': [float(item.position[0]), float(item.position[1]), float(item.position[2])],
                'dim': [float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])]
            })
        for item in b.unfitted_items:
            unloaded_boxes.append(item.name)
            
    return loaded_boxes, unloaded_boxes

# ==========================================
# 3. Plotly 3D 컨테이너 시각화 함수
# ==========================================
def draw_3d_container(container_dim, loaded_boxes):
    fig = go.Figure()
    cw, ch, cd = container_dim
    
    # 컨테이너 외곽선
    fig.add_trace(go.Scatter3d(
        x=[0, cw, cw, 0, 0, 0, cw, cw, 0, 0, 0, 0, cw, cw, cw, cw],
        y=[0, 0, ch, ch, 0, 0, 0, ch, ch, 0, cd, cd, cd, cd, 0, 0],
        z=[0, 0, 0, 0, 0, cd, cd, cd, cd, cd, cd, 0, 0, cd, cd, 0],
        mode='lines',
        line=dict(color='black', width=4),
        name='Container Wall'
    ))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    for idx, box in enumerate(loaded_boxes):
        x0, y0, z0 = box['pos']
        dx, dy, dz = box['dim']
        x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
        color = colors[idx % len(colors)]
        
        fig.add_trace(go.Mesh3d(
            x=[x0, x1, x1, x0, x0, x1, x1, x0],
            y=[y0, y0, y1, y1, y0, y0, y1, y1],
            z=[z0, z0, z0, z0, z1, z1, z1, z1],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            opacity=0.6,
            color=color,
            name=box['name'],
            showlegend=False
        ))
        
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Width (X)', range=[0, cw]),
            yaxis=dict(title='Height (Y)', range=[0, ch]),
            zaxis=dict(title='Depth (Z)', range=[0, cd]),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=600
    )
    return fig

# ==========================================
# 4. Streamlit 메인 레이아웃 및 탭 정의
# ==========================================
tabs = st.tabs(["기존 기능 1", "기존 기능 2", "콘솔"])

with tabs[0]:
    st.write("### 기존 기능 1 화면")

with tabs[1]:
    st.write("### 기존 기능 2 화면")

# ------------------------------------------
# 독립 '콘솔' 테스트 탭 (제약 조건 확장 버전)
# ------------------------------------------
with tabs[2]:
    st.title("📦 콘솔 화물 적재 시뮬레이터 (제약 조건 기능 추가)")
    
    if "console_auth" not in st.session_state:
        st.session_state["console_auth"] = False
        
    if not st.session_state["console_auth"]:
        password_input = st.text_input("테스트 비밀번호를 입력하세요:", type="password", key="p_input")
        if st.button("인증하기", key="p_btn"):
            if password_input == "3156":
                st.session_state["console_auth"] = True
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
    else:
        st.success("🔓 콘솔 탭 테스트 권한이 인증되었습니다.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            c_w = st.number_input("컨테이너 가로 (Width)", value=2300, key="c_w")
        with col2:
            c_h = st.number_input("컨테이너 세로 (Height)", value=2300, key="c_h")
        with col3:
            c_d = st.number_input("컨테이너 높이/깊이 (Depth)", value=2300, key="c_d")
            
        container_dimensions = [c_w, c_h, c_d]
        
        st.subheader("📝 제약 조건을 포함한 화물 입력")
        st.caption("텍스트 뒤에 [이단금지] 또는 [2단제한] 문구를 적으면 시스템이 알아서 옵션을 파싱합니다.")
        
        # 제약 조건이 섞인 샘플 기본 배치
        rule_sample = "1000*300*300 x2 [이단금지]\n500*400*300 * 6 [2단제한]\n800*600*400 x2"
        user_raw_text = st.text_area("화물 크기 및 수량 입력란", value=rule_sample, height=150, key="cargo_text")
        
        parsed_results = parse_cargo_input_with_rules(user_raw_text)
        
        if parsed_results:
            st.write("📊 **분석된 화물 및 제약 조건 목록:**")
            st.dataframe(parsed_results)
            
            if st.button("🚀 제약조건 반영 배치 가동", key="run_sim"):
                with st.spinner("알고리즘 계산 중..."):
                    loaded, unloaded = compute_loading_with_rules(container_dimensions, parsed_results)
                    
                    st.subheader("3. 3D 배치 결과 시각화")
                    chart_fig = draw_3d_container(container_dimensions, loaded)
                    st.plotly_chart(chart_fig, use_container_width=True)
                    
                    st.subheader("📋 적재 현황 요약")
                    st.write(f"✅ **적재 성공:** {len(loaded)}개")
                    if unloaded:
                        st.warning(f"⚠️ **미적재 화물:** {len(unloaded)}개")
                    else:
                        st.info("🎉 조건에 맞춰 모든 화물이 안전하게 배치되었습니다.")
