"""
그늘막 쉼터 - 메인 페이지 (통계)
지도는 왼쪽 사이드바의 '지도' 페이지(pages/1_지도.py)로 분리했습니다.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

WARN_MSG_URL = "https://apis.data.go.kr/1360000/WthrWrnInfoService/getWthrWrnMsg"


@st.cache_data(ttl=600, show_spinner=False)
def fetch_warnings(key: str, from_tmfc: str, to_tmfc: str, stn_id: str):
    """기상특보통보문조회(getWthrWrnMsg) 결과를 리스트로 반환.
    응답 필드명이 문서마다 조금씩 다를 수 있어 dict를 그대로 반환하고
    화면에서 항목을 그대로 나열하는 방식으로 처리(필드명 불일치에 안전)."""
    params = {
        "ServiceKey": key,
        "pageNo": "1",
        "numOfRows": "20",
        "dataType": "JSON",
        "fromTmFc": from_tmfc,
        "toTmFc": to_tmfc,
        "stnId": stn_id,
    }

    resp = requests.get(WARN_MSG_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    header = data["response"]["header"]
    if header["resultCode"] != "00":
        raise RuntimeError(f'{header["resultCode"]}: {header["resultMsg"]}')

    body = data["response"]["body"]
    items = body.get("items")
    if not items:
        return []
    item = items.get("item", [])
    if isinstance(item, dict):
        item = [item]
    return item


APP_DIR = os.path.dirname(os.path.abspath(__file__))
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


st.set_page_config(page_title="그늘막 쉼터", page_icon="⛱️", layout="wide")

shelters = load_shelters()

st.title("⛱️ 그늘막 쉼터")
st.caption(
    "전국 그늘막 쉼터 현황입니다. 지도에서 위치와 상세정보를 보려면 "
    "왼쪽 사이드바의 **지도** 페이지로 이동하세요."
)

# --------------------------------------------------------------------------
# 사이드바 필터
# --------------------------------------------------------------------------
st.sidebar.header("⚙️ 필터")

sido_list = ["전체"] + sorted(shelters["시도명"].unique().tolist())
default_sido_index = sido_list.index("경상남도") if "경상남도" in sido_list else 1
sido = st.sidebar.selectbox("시도 선택", sido_list, index=default_sido_index)

if sido != "전체":
    filtered = shelters[shelters["시도명"] == sido]
    gugun_list = ["전체"] + sorted(filtered["시군구명"].unique().tolist())
    gugun = st.sidebar.selectbox("시군구 선택", gugun_list, index=0)
    if gugun != "전체":
        filtered = filtered[filtered["시군구명"] == gugun]
else:
    gugun = "전체"
    filtered = shelters

st.sidebar.caption(f"선택된 지역 쉼터: {len(filtered):,}개")
st.sidebar.divider()

st.sidebar.header("🚨 기상특보 API")
try:
    default_weather_key = st.secrets["weather_key"]
except Exception:
    default_weather_key = ""

if default_weather_key:
    st.sidebar.success("✅ 특보 API 키가 Secrets에서 연결되었습니다.")
    weather_key = default_weather_key
else:
    weather_key = st.sidebar.text_input(
        "기상특보 API 인증키",
        type="password",
        help="공공데이터포털 '기상청_기상특보 조회서비스' 인증키. "
             "Streamlit Cloud Secrets에 weather_key 라는 이름으로 등록하면 자동 연결됩니다.",
    )
    if not weather_key:
        st.sidebar.caption("⚠️ 아직 인증키가 없습니다. 나중에 Secrets에 weather_key로 등록하거나 여기에 입력하세요.")

st.sidebar.divider()
st.sidebar.caption("자료: 기상청 기상특보 조회서비스, 전국그늘막쉼터표준데이터")

STN_ID = "108"       # 서울
REGION_LABEL = "서울"


def format_tmfc(raw) -> str:
    """'202607210800' 같은 발표시각 문자열을 'YYYY-MM-DD HH:MM' 형태로 변환. 형식이 다르면 원본 반환."""
    raw = str(raw)
    try:
        if len(raw) >= 12:
            return datetime.strptime(raw[:12], "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M")
        if len(raw) >= 8:
            return datetime.strptime(raw[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        pass
    return raw


# --------------------------------------------------------------------------
# 기상특보 현황 (서울, 가장 최근 1건만)
# --------------------------------------------------------------------------
today = datetime.now()
from_tmfc = (today - timedelta(days=3)).strftime("%Y%m%d")
to_tmfc = today.strftime("%Y%m%d")

if not weather_key:
    st.markdown("### 🚨 기상특보 현황")
    st.info("사이드바에 기상특보 API 인증키(weather_key)를 입력하면 최근 특보 내용이 여기 표시됩니다.")
else:
    try:
        with st.spinner("특보 정보를 불러오는 중..."):
            warnings = fetch_warnings(weather_key, from_tmfc, to_tmfc, STN_ID)

        if not warnings:
            st.markdown(f"### 📍 {REGION_LABEL} 기상특보")
            st.success("현재 발표된 기상특보가 없습니다.")
        else:
            # 발표시각(tmFc) 기준으로 가장 최근 1건만 선택
            def _tmfc_of(w):
                k = next((k for k in w if k.lower() in ("tmfc", "tmef")), None)
                return str(w.get(k, "")) if k else ""

            latest = sorted(warnings, key=_tmfc_of, reverse=True)[0]

            tmfc_key = next((k for k in latest if k.lower() in ("tmfc", "tmef")), None)
            tmfc_display = format_tmfc(latest.get(tmfc_key, "")) if tmfc_key else "시각 정보 없음"

            title_key = next((k for k in latest if k.lower() == "title"), None)
            title = (latest.get(title_key) or "").strip() if title_key else ""

            st.markdown(f"### 📍 {REGION_LABEL} · 🕒 {tmfc_display}")

            with st.container(border=True):
                if title:
                    st.markdown(f"**{title}**")
                for k, v in latest.items():
                    if k in (tmfc_key, title_key) or v in (None, ""):
                        continue
                    st.markdown(f"**{k}**: {v}")
    except Exception as e:
        st.markdown(f"### 📍 {REGION_LABEL} 기상특보")
        st.error(f"특보 정보를 불러오지 못했습니다: {e}")

st.divider()

# --------------------------------------------------------------------------
# 요약 지표
# --------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("전체 쉼터 수", f"{len(shelters):,}개")
c2.metric("선택 지역 쉼터 수", f"{len(filtered):,}개")
c3.metric("전국 시도 수", f"{shelters['시도명'].nunique()}개")

# --------------------------------------------------------------------------
# 지역별 쉼터 개수 차트
# --------------------------------------------------------------------------
st.markdown("#### 📊 지역별 쉼터 개수")
if sido == "전체":
    chart_data = shelters["시도명"].value_counts().sort_values(ascending=False)
    chart_caption = "전국 시도별 쉼터 개수"
else:
    chart_data = (
        shelters[shelters["시도명"] == sido]["시군구명"]
        .value_counts()
        .sort_values(ascending=False)
    )
    chart_caption = f"{sido} 시군구별 쉼터 개수"

st.bar_chart(chart_data)
st.caption(chart_caption)

st.divider()

# --------------------------------------------------------------------------
# 지정 8개 시도 그늘막 쉼터 통계
# --------------------------------------------------------------------------
st.markdown("### 🗾 8개 시도 그늘막 쉼터 개수")

# 사용자가 지정한 표시 이름 -> CSV의 실제 시도명(최근 행정구역 개편 반영: 강원특별자치도, 전북특별자치도 등)
REGION_MAP = {
    "서울시": "서울특별시",
    "경상북도": "경상북도",
    "경상남도": "경상남도",
    "강원도": "강원특별자치도",
    "충청북도": "충청북도",
    "충청남도": "충청남도",
    "전라남도": "전라남도",
    "전라북도": "전북특별자치도",
}

region_counts = pd.Series(
    {label: int((shelters["시도명"] == actual).sum()) for label, actual in REGION_MAP.items()}
)

st.bar_chart(region_counts)

region_df = region_counts.reset_index()
region_df.columns = ["지역", "그늘막 쉼터 개수"]
st.dataframe(region_df, use_container_width=True, hide_index=True)
