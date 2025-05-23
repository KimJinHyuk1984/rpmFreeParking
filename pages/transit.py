import streamlit as st
import pandas as pd
import folium
from folium import Marker
from streamlit_folium import st_folium
import numpy as np
import requests

# ---- 1. 엑셀 파일 불러오기 ----
excel_path = "신한RPM(250517)_seoul.xlsx"
df = pd.read_excel(excel_path)

# ---- 2. 컬럼명 고정 ----
col_name = "명칭"
col_lat = "위도"
col_lng = "경도"

st.title("신한 RPM카드 무료주차장 위치 안내(250517 기준) - 직선거리 안내")
st.write("※ 장소명 또는 건물명 또는 주소를 입력해주세요.")

# ---- 3. 카카오맵 REST API 키 ----
kakao_rest_api_key = st.secrets["KAKAO_REST_API_KEY"]

def search_places_kakao(query, kakao_rest_api_key):
    url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}"
    headers = {
        "Authorization": f"KakaoAK {kakao_rest_api_key}"
    }
    res = requests.get(url, headers=headers, verify=False)
    results = []
    if res.status_code == 200:
        data = res.json()
        for doc in data.get("documents", []):
            name = doc.get("place_name")
            address = doc.get("road_address_name") or doc.get("address_name")
            lat = float(doc.get("y"))
            lng = float(doc.get("x"))
            results.append({
                "label": f"{name} ({address})",
                "lat": lat,
                "lng": lng
            })
    return results

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    a = np.sin(d_phi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(d_lambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# ---- 4. 자동완성 입력 및 추천 ----
#st.markdown("#### [자동완성] 장소명, 건물명, 목적지명을 입력하세요")
query = st.text_input("예: 서울역, 신한은행, 강남역, 서울시청 등", key="query", help="입력 후 추천 리스트에서 선택하세요.")

# 세션 상태에 최근 선택값 저장 (자동완성 + 선택 유지)
if "auto_place_label" not in st.session_state:
    st.session_state["auto_place_label"] = None
    st.session_state["auto_place_lat"] = None
    st.session_state["auto_place_lng"] = None

start_lat, start_lng, selected_label = None, None, None

# 사용자가 1글자 이상 입력하면 자동완성 검색
if query and len(query) > 1:
    with st.spinner("카카오맵 장소 검색 중..."):
        search_results = search_places_kakao(query, kakao_rest_api_key)
    options = [item["label"] for item in search_results]
    if options:
        default_idx = options.index(st.session_state["auto_place_label"]) if st.session_state["auto_place_label"] in options else 0
        selected_label = st.selectbox("추천 리스트에서 출발지를 선택하세요", options, index=default_idx)
        selected = next(x for x in search_results if x["label"] == selected_label)
        start_lat, start_lng = selected["lat"], selected["lng"]
        # 선택된 값을 세션에 저장 (지도 리로드 시 유지)
        st.session_state["auto_place_label"] = selected_label
        st.session_state["auto_place_lat"] = start_lat
        st.session_state["auto_place_lng"] = start_lng
    else:
        st.warning("검색 결과가 없습니다. 장소명을 더 정확하게 입력하세요.")
        st.session_state["auto_place_label"] = None
        st.session_state["auto_place_lat"] = None
        st.session_state["auto_place_lng"] = None
elif st.session_state["auto_place_lat"] and st.session_state["auto_place_lng"]:
    # 입력창이 비었어도 이전 선택 유지
    start_lat, start_lng = st.session_state["auto_place_lat"], st.session_state["auto_place_lng"]
    selected_label = st.session_state["auto_place_label"]

# ---- 5. 지도 중심/마커 ----
if start_lat and start_lng:
    map_center = [start_lat, start_lng]
    zoom_lv = 16
else:
    map_center = [df[col_lat][0], df[col_lng][0]]
    zoom_lv = 12

m = folium.Map(location=map_center, zoom_start=zoom_lv)

# 엑셀 데이터: 빨간 자동차 마커
for idx, row in df.iterrows():
    Marker(
        [row[col_lat], row[col_lng]],
        tooltip=str(row[col_name]),
        icon=folium.Icon(color='red', icon='car', prefix='fa')
    ).add_to(m)

# 입력 주소: 파란 역삼각형 마커
if start_lat and start_lng and selected_label:
    Marker(
        [start_lat, start_lng],
        tooltip=selected_label,
        icon=folium.Icon(color='blue', icon='caret-down', prefix='fa')
    ).add_to(m)
    #st.success("추천 리스트에서 선택한 위치가 지도에 파란 역삼각형으로 표시되고, 해당 위치로 확대되었습니다.")

# ---- 6. 파란 점선(직선거리 연결선) 표시 ----
if start_lat and start_lng:
    df['직선거리'] = df.apply(lambda row: haversine(start_lat, start_lng, row[col_lat], row[col_lng]), axis=1)
    nearest_row = df.loc[df['직선거리'].idxmin()]
    end_lat, end_lng = nearest_row[col_lat], nearest_row[col_lng]
    nearest_name = nearest_row[col_name]
    folium.PolyLine(
        [[start_lat, start_lng], [end_lat, end_lng]],
        color="blue",
        weight=4,
        opacity=0.8,
        dash_array="10,10",
        tooltip=f"파란 마커 → {nearest_name} (직선거리)"
    ).add_to(m)
    st.info(f"출발지와 가장 가까운 무료 주차장은 '{nearest_name}' 입니다. \n 직선거리는 약 {nearest_row['직선거리']:.2f}m입니다.")

# ---- 7. 지도 출력 ----
st_folium(m, width=800, height=600)

