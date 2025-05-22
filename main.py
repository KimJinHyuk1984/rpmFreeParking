# app.py
import streamlit as st
import pandas as pd
import folium
from folium import Marker
from streamlit_folium import st_folium
import requests

# 🔑 네이버 API 인증 정보 입력 필요

# 📄 데이터 불러오기
@st.cache_data
def load_data():
    df = pd.read_excel("신한RPM(250517)_seoul.xlsx")
    df = df[['명칭', '도로명', '위도', '경도']]
    return df

df = load_data()
st.title("📍 서울 지점 지도 시각화")

# 🏠 주소 입력 + 실행 버튼 (상단에 배치)
st.subheader("🔎 주소를 입력하고 지도에서 위치 확인하기")

with st.form("address_form"):
    address = st.text_input("주소 입력 (예: 서울시 종로구 청와대로 1)")
    submitted = st.form_submit_button("📍 위치 확인")

# 🗺 지도 생성
center = [df['위도'].mean(), df['경도'].mean()]
m = folium.Map(location=center, zoom_start=12)

# 📌 엑셀 마커 추가
for _, row in df.iterrows():
    Marker(
        location=[row['위도'], row['경도']],
        tooltip=row['명칭'],
        popup=row['명칭'],
        icon=folium.Icon(color='red', icon='arrow-down', prefix='fa')
    ).add_to(m)

# 🏷 주소 마커 추가
if submitted and address:
    def geocode_address(addr):
        headers = {
            "X-Naver-Client-Id": NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
        }
        params = {"query": addr}
        res = requests.get("https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode", headers=headers, params=params)

        # 🔍 응답 상태 및 JSON 전체 출력
        st.write("🔄 응답 상태 코드:", res.status_code)
        try:
            st.json(res.json())
        except Exception as e:
            st.error(f"응답을 JSON으로 변환하지 못했습니다: {e}")
            return None, None

        if res.status_code == 200:
            items = res.json().get("addresses")
            if items:
                return float(items[0]['y']), float(items[0]['x'])
        return None, None


    user_lat, user_lon = geocode_address(address)

    if user_lat and user_lon:
        Marker(
            [user_lat, user_lon],
            popup="입력한 주소",
            icon=folium.Icon(color='red', icon='arrow-down', prefix='fa')
        ).add_to(m)

        st.success("입력한 주소 위치를 지도에 표시했습니다.")
    else:
        st.error("주소를 찾을 수 없습니다. 다시 확인해 주세요.")

# 🖼 지도 출력 (크기 축소)
st.subheader("🗺 전체 지도")
st_folium(m, width=700, height=500)
