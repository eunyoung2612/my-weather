"""
그늘막 쉼터 - 메인 페이지 (통계)
지도는 왼쪽 사이드바의 '지도' 페이지(pages/1_지도.py)로 분리했습니다.
"""

import os

import pandas as pd
import streamlit as st

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
st.sidebar.caption("자료: 전국그늘막쉼터표준데이터")

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

if hasattr(st, "page_link"):
    st.page_link("pages/1_지도.py", label="지도에서 쉼터 위치 보기", icon="🗺️")
else:
    st.info("왼쪽 사이드바 메뉴에서 **지도** 페이지를 선택하면 위치를 지도로 볼 수 있습니다.")
