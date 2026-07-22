"""
그늘막 쉼터 & 실시간 날씨 지도
- 지도에 전국 그늘막 쉼터 표시
- 마커 클릭 시 해당 지점의 기상청 초단기실황(현재 날씨) 조회
- 기온 33도 이상이면 폭염 이모지 표시
Streamlit Cloud 배포용 (main.py 단일 파일 + data/shade_shelters.csv)
"""

import math
import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# --------------------------------------------------------------------------
# 기본 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="그늘막 쉼터 & 실시간 날씨", page_icon="⛱️", layout="wide")

KMA_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

CATEGORY_LABELS = {
    "T1H": "기온(℃)",
    "REH": "습도(%)",
    "RN1": "1시간 강수량(mm)",
    "WSD": "풍속(m/s)",
    "VEC": "풍향(deg)",
    "PTY": "강수형태",
    "UUU": "동서바람성분(m/s)",
    "VVV": "남북바람성분(m/s)",
}

PTY_LABELS = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}


# --------------------------------------------------------------------------
# 위경도 -> 기상청 격자좌표(nx, ny) 변환 (기상청 공식 LCC 변환식)
# --------------------------------------------------------------------------
def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0        # 격자 간격(km)
    SLAT1 = 30.0       # 투영 위도1
    SLAT2 = 60.0       # 투영 위도2
    OLON = 126.0       # 기준점 경도
    OLAT = 38.0        # 기준점 위도
    XO = 43            # 기준점 X좌표(GRID)
    YO = 136           # 기준점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = ra * math.sin(theta) + XO
    y = ro - ra * math.cos(theta) + YO

    nx = int(x + 1.5)
    ny = int(y + 1.5)
    return nx, ny


def get_base_datetime() -> tuple[str, str]:
    """초단기실황은 매시 40분에 발표되므로, 40분 이전이면 이전 정시 자료를 사용"""
    now = datetime.now()
    if now.minute < 40:
        base_dt = now - timedelta(hours=1)
    else:
        base_dt = now
    return base_dt.strftime("%Y%m%d"), base_dt.strftime("%H00")


# --------------------------------------------------------------------------
# 데이터 로드
# --------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SHELTER_CSV_PATH = os.path.join(APP_DIR, "shade_shelters.csv")


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


@st.cache_data(ttl=600, show_spinner=False)
def fetch_weather(service_key: str, nx: int, ny: int, base_date: str, base_time: str):
    params = {
        "serviceKey": service_key,
        "pageNo": "1",
        "numOfRows": "10",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }
    resp = requests.get(KMA_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    header = data["response"]["header"]
    if header["resultCode"] != "00":
        raise RuntimeError(f'{header["resultCode"]}: {header["resultMsg"]}')
    items = data["response"]["body"]["items"]["item"]
    return {it["category"]: it["obsrValue"] for it in items}


# --------------------------------------------------------------------------
# 사이드바
# --------------------------------------------------------------------------
st.sidebar.header("⚙️ 설정")

default_key = st.secrets.get("KMA_API_KEY", "") if hasattr(st, "secrets") else ""
service_key = st.sidebar.text_input(
    "기상청 API 인증키 (공공데이터포털)",
    value=default_key,
    type="password",
    help="공공데이터포털에서 발급받은 Decoding 인증키를 입력하세요. "
         "Streamlit Cloud에서는 Settings > Secrets에 KMA_API_KEY로 등록하면 자동으로 채워집니다.",
)

shelters = load_shelters()

sido_list = ["전체"] + sorted(shelters["시도명"].unique().tolist())
sido = st.sidebar.selectbox("시도 선택", sido_list, index=0)

if sido != "전체":
    filtered = shelters[shelters["시도명"] == sido]
    gugun_list = ["전체"] + sorted(filtered["시군구명"].unique().tolist())
    gugun = st.sidebar.selectbox("시군구 선택", gugun_list, index=0)
    if gugun != "전체":
        filtered = filtered[filtered["시군구명"] == gugun]
else:
    filtered = shelters

st.sidebar.caption(f"표시되는 그늘막 쉼터: {len(filtered):,}개")
if len(filtered) > 3000:
    st.sidebar.warning("표시 개수가 많아 지도가 느려질 수 있어요. 시도/시군구를 좁혀보세요.")

st.sidebar.divider()
st.sidebar.caption("자료: 기상청 단기예보 조회서비스(초단기실황), 전국그늘막쉼터표준데이터")

# --------------------------------------------------------------------------
# 본문 레이아웃
# --------------------------------------------------------------------------
st.title("⛱️ 그늘막 쉼터 & 실시간 날씨")
st.caption("지도의 그늘막 쉼터 마커를 클릭하면 오른쪽에 해당 지역의 실시간 날씨가 표시됩니다.")

col_map, col_weather = st.columns([2, 1])

with col_map:
    center_lat = filtered["위도"].mean() if len(filtered) else 36.5
    center_lon = filtered["경도"].mean() if len(filtered) else 127.5
    zoom = 11 if sido != "전체" else 7

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="OpenStreetMap")
    cluster = MarkerCluster().add_to(m)

    for idx, row in filtered.iterrows():
        popup_html = (
            f"<b>{row['설치장소명']}</b><br>"
            f"{row['시도명']} {row['시군구명']}<br>"
            f"{row.get('소재지도로명주소') or row.get('소재지지번주소') or ''}<br>"
            f"유형: {row.get('그늘막유형', '-')}"
        )
        folium.Marker(
            location=[row["위도"], row["경도"]],
            tooltip=row["설치장소명"],
            popup=folium.Popup(popup_html, max_width=250),
            icon=folium.Icon(color="orange", icon="umbrella", prefix="fa"),
        ).add_to(cluster)

    map_state = st_folium(m, height=650, use_container_width=True,
                           returned_objects=["last_object_clicked"])

with col_weather:
    st.subheader("🌤️ 실시간 날씨")

    clicked = map_state.get("last_object_clicked") if map_state else None

    if not clicked:
        st.info("지도에서 그늘막 쉼터 마커를 클릭하면 날씨가 표시됩니다.")
    elif not service_key:
        st.warning("기상청 API 인증키를 사이드바에 입력해주세요.")
    else:
        click_lat, click_lon = clicked["lat"], clicked["lng"]

        # 클릭 좌표와 가장 가까운 쉼터 찾기
        dist = ((filtered["위도"] - click_lat) ** 2 + (filtered["경도"] - click_lon) ** 2)
        nearest = filtered.loc[dist.idxmin()]

        st.markdown(f"**📍 {nearest['설치장소명']}**")
        st.caption(f"{nearest['시도명']} {nearest['시군구명']}")

        nx, ny = latlon_to_grid(nearest["위도"], nearest["경도"])
        base_date, base_time = get_base_datetime()

        try:
            with st.spinner("날씨 조회 중..."):
                weather = fetch_weather(service_key, nx, ny, base_date, base_time)

            t1h = weather.get("T1H")
            if t1h is not None:
                temp_val = float(t1h)
                heat_badge = " 🥵🔥 폭염" if temp_val >= 33 else ""
                st.metric("기온", f"{t1h} ℃{heat_badge}")
                if temp_val >= 33:
                    st.error("폭염 기준(33℃) 이상입니다. 그늘막 이용을 권장합니다!")

            c1, c2 = st.columns(2)
            with c1:
                if "REH" in weather:
                    st.metric("습도", f"{weather['REH']} %")
                if "WSD" in weather:
                    st.metric("풍속", f"{weather['WSD']} m/s")
            with c2:
                pty = weather.get("PTY")
                if pty is not None:
                    st.metric("강수형태", PTY_LABELS.get(pty, pty))
                if "RN1" in weather:
                    st.metric("1시간 강수량", f"{weather['RN1']} mm")

            with st.expander("원본 관측값 보기"):
                st.json(weather)

            st.caption(f"발표시각: {base_date} {base_time} | 격자좌표: nx={nx}, ny={ny}")

        except Exception as e:
            st.error(f"날씨 조회 실패: {e}")
