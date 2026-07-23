"""
그늘막 쉼터 지도 페이지
지도의 마커를 클릭하면 오른쪽에 해당 쉼터의 상세정보(설치유형, 도로명주소 등)를 보여줍니다.
"""

import os

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# 이 페이지는 pages/ 폴더 안에 있으므로, 리포지토리 루트(한 단계 위)에 있는 CSV를 가리킴
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELTER_CSV_PATH = os.path.join(APP_DIR, "shade_shelters.csv")


@st.cache_data
def load_shelters() -> pd.DataFrame:
    if not os.path.exists(SHELTER_CSV_PATH):
        st.error(
            f"CSV 파일을 찾을 수 없습니다: `{SHELTER_CSV_PATH}`\n\n"
            "GitHub 리포지토리에 `shade_shelters.csv` 파일이 "
            "`main.py`와 같은 폴더(루트)에 커밋되어 있는지 확인해주세요."
        )
        st.stop()
    df = pd.read_csv(SHELTER_CSV_PATH)
    df = df.dropna(subset=["위도", "경도"])
    return df


st.set_page_config(page_title="그늘막 쉼터 지도", page_icon="🗺️", layout="wide")

shelters = load_shelters()

st.title("🗺️ 그늘막 쉼터 지도")
st.caption("마커를 클릭하면 오른쪽에 해당 쉼터의 상세정보가 표시됩니다.")

# --------------------------------------------------------------------------
# 사이드바 필터
# --------------------------------------------------------------------------
st.sidebar.header("⚙️ 지도 필터")

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
if len(filtered) > 1500:
    st.sidebar.warning("표시 개수가 많아 지도가 느려질 수 있어요. 시도/시군구를 좁혀보세요.")


# --------------------------------------------------------------------------
# 지도 생성 (필터 조합마다 한 번만 만들고 캐시)
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="지도를 그리는 중...")
def build_map(sido_key: str, gugun_key: str):
    subset = shelters
    if sido_key != "전체":
        subset = subset[subset["시도명"] == sido_key]
        if gugun_key != "전체":
            subset = subset[subset["시군구명"] == gugun_key]

    center_lat = subset["위도"].mean() if len(subset) else 36.5
    center_lon = subset["경도"].mean() if len(subset) else 127.5
    zoom = 12 if gugun_key != "전체" else (11 if sido_key != "전체" else 7)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="OpenStreetMap")

    for _, row in subset.iterrows():
        folium.CircleMarker(
            location=[row["위도"], row["경도"]],
            radius=6,
            tooltip=row["설치장소명"],
            color="#e67300",
            fill=True,
            fill_color="#ff9933",
            fill_opacity=0.9,
        ).add_to(m)

    return m


col_map, col_detail = st.columns([2, 1])

with col_map:
    m = build_map(sido, gugun_key)
    map_state = st_folium(
        m, height=650, use_container_width=True,
        returned_objects=["last_object_clicked"],
        key=f"map_{sido}_{gugun_key}",
    )

with col_detail:
    st.subheader("🏷️ 쉼터 상세정보")

    clicked = map_state.get("last_object_clicked") if map_state else None

    if not clicked:
        st.info("지도의 마커를 클릭하면 상세정보가 여기에 표시됩니다.")
    elif len(filtered) == 0:
        st.warning("현재 선택된 지역에 쉼터가 없습니다.")
    else:
        click_lat, click_lon = clicked["lat"], clicked["lng"]
        dist = ((filtered["위도"] - click_lat) ** 2 + (filtered["경도"] - click_lon) ** 2)
        row = filtered.loc[dist.idxmin()]

        st.markdown(f"### {row['설치장소명']}")
        st.caption(f"{row['시도명']} {row['시군구명']}")

        addr = row.get("소재지도로명주소")
        if pd.isna(addr) or not addr:
            addr = row.get("소재지지번주소")
        if pd.isna(addr) or not addr:
            addr = "주소 정보 없음"
        st.markdown(f"**📫 주소**  \n{addr}")

        shelter_type = row.get("그늘막유형")
        st.markdown(f"**⛱️ 설치유형**  \n{shelter_type if pd.notna(shelter_type) else '정보 없음'}")

        detail_loc = row.get("세부위치")
        if pd.notna(detail_loc):
            st.markdown(f"**📌 세부위치**  \n{detail_loc}")

        install_year = row.get("설치년도")
        if pd.notna(install_year):
            st.markdown(f"**📅 설치년도**  \n{int(install_year)}년")

        height, width = row.get("전체높이"), row.get("펼침지름")
        if pd.notna(height) or pd.notna(width):
            h_txt = f"{height}m" if pd.notna(height) else "-"
            w_txt = f"{width}m" if pd.notna(width) else "-"
            st.markdown(f"**📏 규격**  \n높이 {h_txt} / 펼침지름 {w_txt}")

        manager = row.get("관리기관명")
        phone = row.get("관리기관전화번호")
        if pd.notna(manager):
            st.markdown(f"**🏢 관리기관**  \n{manager}")
        if pd.notna(phone):
            st.markdown(f"**☎️ 연락처**  \n{phone}")

        st.caption(f"데이터 기준일자: {row.get('데이터기준일자', '-')}")
