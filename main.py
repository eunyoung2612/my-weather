"""
그늘막 쉼터 지도
- 지도에 전국 그늘막 쉼터 표시
- 지역별(시도/시군구) 쉼터 개수 통계 차트
- 지도를 클릭해 "내 위치"를 지정하면 가까운 쉼터 목록을 거리순으로 표시
Streamlit Cloud 배포용 (main.py 단일 파일 + shade_shelters.csv, 같은 폴더)
"""

import math
import os

import numpy as np
import pandas as pd
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# --------------------------------------------------------------------------
# 기본 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="그늘막 쉼터 지도", page_icon="⛱️", layout="wide")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SHELTER_CSV_PATH = os.path.join(APP_DIR, "shade_shelters.csv")


def haversine_km(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 실제 거리(km)를 계산 (Haversine 공식).
    lat2/lon2에 pandas Series를 넣으면 벡터 연산으로 한 번에 계산됨."""
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


# --------------------------------------------------------------------------
# 데이터 로드
# --------------------------------------------------------------------------
@st.cache_data
def load_shelters() -> pd.DataFrame:
    if not os.path.exists(SHELTER_CSV_PATH):
        st.error(
            f"CSV 파일을 찾을 수 없습니다: `{SHELTER_CSV_PATH}`\n\n"
            "GitHub 리포지토리에 `shade_shelters.csv` 파일이 "
            "`main.py`와 같은 폴더에 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(SHELTER_CSV_PATH)
    df = df.dropna(subset=["위도", "경도"])
    return df


shelters = load_shelters()

# --------------------------------------------------------------------------
# 사이드바
# --------------------------------------------------------------------------
st.sidebar.header("⚙️ 설정")

sido_list = ["전체"] + sorted(shelters["시도명"].unique().tolist())
default_sido_index = sido_list.index("경상남도") if "경상남도" in sido_list else 1
sido = st.sidebar.selectbox(
    "시도 선택", sido_list, index=default_sido_index,
    help="'전체'를 선택하면 마커가 12,000개가 넘어 매우 느려집니다. 특정 시도를 권장해요.",
)

if sido != "전체":
    filtered = shelters[shelters["시도명"] == sido]
    gugun_list = ["전체"] + sorted(filtered["시군구명"].unique().tolist())
    gugun = st.sidebar.selectbox("시군구 선택", gugun_list, index=0)
    if gugun != "전체":
        filtered = filtered[filtered["시군구명"] == gugun]
else:
    gugun = "전체"
    filtered = shelters

gugun_key = gugun if sido != "전체" else "전체"

st.sidebar.caption(f"표시되는 그늘막 쉼터: {len(filtered):,}개")
if len(filtered) > 3000:
    st.sidebar.warning("표시 개수가 많아 지도가 느려질 수 있어요. 시도/시군구를 좁혀보세요.")

st.sidebar.divider()
st.sidebar.caption("자료: 전국그늘막쉼터표준데이터")

# --------------------------------------------------------------------------
# 본문 레이아웃
# --------------------------------------------------------------------------
st.title("⛱️ 그늘막 쉼터 지도")
st.caption("지도를 클릭해 내 위치를 지정하면 오른쪽에 가까운 쉼터가 거리순으로 표시됩니다.")

col_map, col_side = st.columns([2, 1])


@st.cache_resource(show_spinner="지도를 그리는 중...")
def build_map(sido_key: str, gugun_key: str):
    """선택된 시도/시군구 조합마다 한 번만 지도를 만들고 캐시해서,
    상호작용으로 스크립트가 재실행돼도 지도를 다시 그리지 않도록 함."""
    subset = shelters
    if sido_key != "전체":
        subset = subset[subset["시도명"] == sido_key]
        if gugun_key != "전체":
            subset = subset[subset["시군구명"] == gugun_key]

    center_lat = subset["위도"].mean() if len(subset) else 36.5
    center_lon = subset["경도"].mean() if len(subset) else 127.5
    zoom = 12 if gugun_key != "전체" else (11 if sido_key != "전체" else 7)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="OpenStreetMap")
    cluster = MarkerCluster(disableClusteringAtZoom=15).add_to(m)

    for _, row in subset.iterrows():
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=6,
            tooltip=row["설치장소명"],
            color="#e67300",
            fill=True,
            fill_color="#ff9933",
            fill_opacity=0.9,
        ).add_to(cluster)

    return m


def get_default_view(sido_key: str, gugun_key: str):
    subset = shelters
    if sido_key != "전체":
        subset = subset[subset["시도명"] == sido_key]
        if gugun_key != "전체":
            subset = subset[subset["시군구명"] == gugun_key]
    center_lat = subset["위도"].mean() if len(subset) else 36.5
    center_lon = subset["경도"].mean() if len(subset) else 127.5
    zoom = 12 if gugun_key != "전체" else (11 if sido_key != "전체" else 7)
    return [center_lat, center_lon], zoom


# 클릭한 "내 위치"는 지역 필터가 바뀌어도 세션에 유지
if "my_location" not in st.session_state:
    st.session_state["my_location"] = None

view_key = f"view_{sido}_{gugun_key}"
if view_key not in st.session_state:
    default_center, default_zoom = get_default_view(sido, gugun_key)
    st.session_state[view_key] = {"center": default_center, "zoom": default_zoom}

with col_map:
    view = st.session_state[view_key]
    m = build_map(sido, gugun_key)
    map_state = st_folium(
        m, height=500, use_container_width=True,
        center=view["center"], zoom=view["zoom"],
        returned_objects=["last_clicked", "center", "zoom"],
        key=f"map_{sido}_{gugun_key}",
    )

    # 사용자가 이동/확대한 위치를 세션에 저장 → 다음 재실행 때도 그 자리 유지
    if map_state and map_state.get("center") and map_state.get("zoom"):
        st.session_state[view_key] = {
            "center": [map_state["center"]["lat"], map_state["center"]["lng"]],
            "zoom": map_state["zoom"],
        }

    # 클릭 위치를 세션에 저장 → 다른 조작으로 재실행돼도 "가까운 쉼터" 목록이 사라지지 않음
    clicked = map_state.get("last_clicked") if map_state else None
    if clicked:
        st.session_state["my_location"] = (clicked["lat"], clicked["lng"])

    st.markdown("#### 📊 지역별 쉼터 개수")
    if sido == "전체":
        chart_data = shelters["시도명"].value_counts().sort_values(ascending=False)
        chart_caption = "전국 시도별 쉼터 개수"
    else:
        chart_data = shelters[shelters["시도명"] == sido]["시군구명"].value_counts().sort_values(ascending=False)
        chart_caption = f"{sido} 시군구별 쉼터 개수"
    st.bar_chart(chart_data)
    st.caption(chart_caption)

with col_side:
    st.subheader("📍 내 위치 기준 가까운 쉼터")

    my_location = st.session_state["my_location"]

    if not my_location:
        st.info("왼쪽 지도의 원하는 위치를 클릭하면 내 위치를 기준으로 가까운 쉼터를 찾아드려요.")
    else:
        my_lat, my_lon = my_location
        st.caption(f"선택한 위치: 위도 {my_lat:.5f}, 경도 {my_lon:.5f}")
        if st.button("📍 위치 초기화"):
            st.session_state["my_location"] = None
            st.rerun()

        if len(filtered) == 0:
            st.warning("현재 선택된 지역에 쉼터가 없습니다.")
        else:
            calc = filtered.copy()
            calc["거리_km"] = haversine_km(my_lat, my_lon, calc["위도"], calc["경도"])
            nearest = calc.sort_values("거리_km").head(10)

            for _, row in nearest.iterrows():
                dist_txt = (
                    f"{row['거리_km'] * 1000:.0f} m" if row["거리_km"] < 1
                    else f"{row['거리_km']:.2f} km"
                )
                st.markdown(f"**{row['설치장소명']}** — {dist_txt}")
                st.caption(f"{row['시도명']} {row['시군구명']}")

        st.caption("💡 지도를 다른 곳에서 클릭하면 목록이 새로 계산됩니다.")
