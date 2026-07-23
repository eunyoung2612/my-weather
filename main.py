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

# 지역명으로 선택할 수 있도록 하는 지점코드 매핑
# (참고: 정확한 특보 지점코드표는 공공데이터포털 활용가이드에 별첨되어 있어, 실제 키로 테스트 후 필요시 조정하세요)
REGION_STN_MAP = {
    "전국(서울 대표)": "108",
    "서울": "108",
    "인천": "112",
    "경기(수원)": "119",
    "강원(강릉)": "105",
    "강원(춘천)": "101",
    "충북(청주)": "131",
    "충남(대전)": "133",
    "충남(서산)": "129",
    "전북(전주)": "146",
    "전남(광주)": "156",
    "전남(목포)": "165",
    "경북(대구)": "143",
    "경북(안동)": "136",
    "경남(부산)": "159",
    "경남(진주)": "192",
    "울산": "152",
    "제주": "184",
}


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

region_name = st.sidebar.selectbox(
    "지역 선택", list(REGION_STN_MAP.keys()), index=0,
    help="특보를 조회할 지역입니다. 내부적으로 기상청 지점코드로 변환됩니다.",
)
stn_id = REGION_STN_MAP[region_name]

date_range = st.sidebar.date_input(
    "조회 기간",
    value=(datetime.now().date(), datetime.now().date()),
    help="이 기간에 발표된 특보를 조회합니다. 기간이 길수록 결과가 많아집니다.",
)

st.sidebar.divider()
st.sidebar.caption("자료: 기상청 기상특보 조회서비스, 전국그늘막쉼터표준데이터")

# --------------------------------------------------------------------------
# 기상특보 현황
# --------------------------------------------------------------------------
st.markdown("### 🚨 기상특보 현황")

# date_input이 범위 선택 중(끝 날짜 미선택)일 때는 튜플 길이가 1일 수 있음
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

from_tmfc = start_date.strftime("%Y%m%d")
to_tmfc = end_date.strftime("%Y%m%d")
st.caption(f"{region_name} · 조회기간 {from_tmfc} ~ {to_tmfc}")

if not weather_key:
    st.info("사이드바에 기상특보 API 인증키(weather_key)를 입력하면 최근 특보 내용이 여기 표시됩니다.")
else:
    try:
        with st.spinner("특보 정보를 불러오는 중..."):
            warnings = fetch_warnings(weather_key, from_tmfc, to_tmfc, stn_id)

        if not warnings:
            st.success("조회 기간 내 발표된 기상특보가 없습니다.")
        else:
            st.caption(f"총 {len(warnings)}건")
            for idx, w in enumerate(warnings, start=1):
                # 응답 필드명 대소문자가 문서와 다를 수 있어 대소문자 구분 없이 'title' 키를 탐색
                title_key = next((k for k in w if k.lower() == "title"), None)
                title = (w.get(title_key) or "").strip() if title_key else ""

                if not title:
                    # title이 비어있으면 발표시각 등 다른 정보로 대체 제목 구성
                    tmfc_key = next((k for k in w if k.lower() in ("tmfc", "tmef")), None)
                    tmfc_val = w.get(tmfc_key, "") if tmfc_key else ""
                    title = f"특보 항목 {idx}" + (f" ({tmfc_val})" if tmfc_val else "")

                with st.expander(f"📢 {title}"):
                    for k, v in w.items():
                        if k == title_key or v in (None, ""):
                            continue
                        st.markdown(f"**{k}**: {v}")
    except Exception as e:
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

try:
    st.page_link("pages/1_지도.py", label="지도에서 쉼터 위치 보기", icon="🗺️")
except Exception:
    st.info("왼쪽 사이드바 메뉴에서 **지도** 페이지를 선택하면 위치를 지도로 볼 수 있습니다.")
