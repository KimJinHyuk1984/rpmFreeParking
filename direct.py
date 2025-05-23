import streamlit as st
import pandas as pd
import folium
from folium import Marker
from streamlit_folium import st_folium
import requests
import polyline
import numpy as np

# ---- 1. 엑셀 파일 불러오기 ----
excel_path = "신한RPM(250517)_seoul.xlsx"
df = pd.read_excel(excel_path)

col_name = "명칭"
col_lat = "위도"
col_lng = "경도"

st.title("신한 RPM카드 무료주차장 위치 안내(250517 기준) - 대중교통 경로 안내")
st.write("※ 장소명 또는 건물명 또는 주소를 입력해주세요.")

# ---- 2. 카카오맵 REST API 키 ----
kakao_rest_api_key = st.secrets["KAKAO_REST_API_KEY"]
google_api_key = st.secrets["GOOGLE_MAP_API_KEY"]

def search_places_kakao(query, kakao_rest_api_key):
    url = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={query}"
    headers = {
        "Authorization": f"KakaoAK {kakao_rest_api_key}"
    }
    res = requests.get(url, headers=headers)
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

def get_transit_steps_by_google(start_lat, start_lng, end_lat, end_lng, api_key):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={start_lat},{start_lng}&destination={end_lat},{end_lng}&mode=transit&key={api_key}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        if data["status"] == "OK":
            route = data["routes"][0]
            distance = route["legs"][0]["distance"]["value"]
            steps = route["legs"][0]["steps"]
            duration = route["legs"][0]["duration"]["text"]
            return steps, distance, duration
    return None, None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    a = np.sin(d_phi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(d_lambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def add_transit_route_on_map(m, steps):
    for step in steps:
        points = polyline.decode(step['polyline']['points'])
        mode = step['travel_mode']
        if mode == "WALKING":
            folium.PolyLine(points, color="blue", weight=6, opacity=0.7, tooltip="도보").add_to(m)
        elif mode == "TRANSIT":
            transit = step['transit_details']
            vehicle_type = transit['line']['vehicle']['type']
            if vehicle_type == "BUS":
                color = "green"
            elif vehicle_type == "SUBWAY":
                color = "purple"
            else:
                color = "orange"
            line_name = transit['line'].get('short_name', transit['line'].get('name', ''))
            dep = transit['departure_stop']['name']
            arr = transit['arrival_stop']['name']
            summary = f"{vehicle_type} {line_name}: {dep} → {arr}"
            folium.PolyLine(points, color=color, weight=6, opacity=0.8, tooltip=summary).add_to(m)

def extract_transit_info(steps):
    info = []
    for step in steps:
        if step['travel_mode'] == "TRANSIT":
            t = step['transit_details']
            vehicle = t['line']['vehicle']['type']
            line = t['line'].get('short_name', t['line'].get('name', ''))
            dep = t['departure_stop']['name']
            arr = t['arrival_stop']['name']
            headsign = t['headsign'] if 'headsign' in t else ''
            info.append({
                "구간": f"{dep} → {arr}",
                "교통수단": vehicle,
                "노선": line,
                "방면": headsign,
                "정차수": t.get('num_stops', '-')
            })
    return info

# ---- 3. 자동완성 입력 및 추천 ----
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

# ---- 4. 지도 중심/마커 ----
if start_lat and start_lng:
    map_center = [start_lat, start_lng]
    zoom_lv = 16
else:
    map_center = [df[col_lat][0], df[col_lng][0]]
    zoom_lv = 12

# ---- 5. 세션 상태 초기화 ----
if "transit_steps" not in st.session_state:
    st.session_state['transit_steps'] = None
    st.session_state['transit_distance'] = None
    st.session_state['transit_duration'] = None
    st.session_state['nearest_name'] = None
    st.session_state['end_lat'] = None
    st.session_state['end_lng'] = None

# ---- 6. 출발점(파란마커) 좌표가 유효하면 즉시 경로 탐색 및 세션 저장 ----
if start_lat and start_lng:
    df['직선거리'] = df.apply(lambda row: haversine(start_lat, start_lng, row[col_lat], row[col_lng]), axis=1)
    nearest_row = df.loc[df['직선거리'].idxmin()]
    end_lat, end_lng = nearest_row[col_lat], nearest_row[col_lng]
    nearest_name = nearest_row[col_name]

    # 이미 저장된 값과 다르면 새로 요청
    prev_info = (
        st.session_state.get('last_query_addr'),
        st.session_state.get('last_query_end_lat'),
        st.session_state.get('last_query_end_lng'),
    )
    cur_info = (selected_label, end_lat, end_lng)
    if prev_info != cur_info:
        steps, distance, duration = get_transit_steps_by_google(start_lat, start_lng, end_lat, end_lng, google_api_key)
        if steps and distance:
            st.session_state['transit_steps'] = steps
            st.session_state['transit_distance'] = distance
            st.session_state['transit_duration'] = duration
            st.session_state['nearest_name'] = nearest_name
            st.session_state['end_lat'] = end_lat
            st.session_state['end_lng'] = end_lng
            st.session_state['last_query_addr'] = selected_label
            st.session_state['last_query_end_lat'] = end_lat
            st.session_state['last_query_end_lng'] = end_lng
        else:
            st.session_state['transit_steps'] = None
            st.session_state['transit_distance'] = None
            st.session_state['transit_duration'] = None
            st.session_state['nearest_name'] = None
            st.session_state['end_lat'] = None
            st.session_state['end_lng'] = None

# ---- 7. 지도 객체 생성 ----
m = folium.Map(location=map_center, zoom_start=zoom_lv)

# 엑셀 데이터 마커
for idx, row in df.iterrows():
    Marker(
        [row[col_lat], row[col_lng]],
        tooltip=str(row[col_name]),
        icon=folium.Icon(color='red', icon='car', prefix='fa')
    ).add_to(m)

# 출발지 파란 역삼각형 마커
if start_lat and start_lng and selected_label:
    Marker(
        [start_lat, start_lng],
        tooltip=selected_label,
        icon=folium.Icon(color='blue', icon='caret-down', prefix='fa')
    ).add_to(m)
    #st.success("추천 리스트에서 선택한 위치가 지도에 파란 역삼각형으로 표시되고, 해당 위치로 이동/확대되었습니다.")

# ---- 8. session_state에 값 있으면 지도/환승정보 항상 표시 ----
if (
    st.session_state['transit_steps'] and
    st.session_state['end_lat'] and
    st.session_state['end_lng']
):
    # 도착지 마커
    Marker(
        [st.session_state['end_lat'], st.session_state['end_lng']],
        tooltip=st.session_state['nearest_name'],
        icon=folium.Icon(color='red', icon='car', prefix='fa')
    ).add_to(m)
    # 단계별 경로
    add_transit_route_on_map(m, st.session_state['transit_steps'])
    st.success(
        f"'{st.session_state['nearest_name']}'까지의 전체 경로(총거리 {st.session_state['transit_distance']/1000:.2f} km, 예상 소요 {st.session_state['transit_duration']})가 지도에 단계별로 표시되었습니다.\n 파란색은 도보 구간이며, 초록색은 버스, 보라색은 지하철 구간입니다.\n\n"
    )
    st_folium(m, width=800, height=600)

    # 환승정보 표
    info = extract_transit_info(st.session_state['transit_steps'])
    if info:
        st.markdown("### [대중교통 환승/노선 정보]")
        st.table(pd.DataFrame(info))
    else:
        st.info("대중교통 구간 없이 도보만 있는 경로입니다.")

else:
    st_folium(m, width=800, height=600)
